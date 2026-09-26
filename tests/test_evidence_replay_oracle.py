"""Stateful differential replay oracle for the evidence withdrawal latch.

A small reference model, written from docs/CORRECTION_REPLAY.md and the
documented reason codes (not by calling the implementation), is driven in
lock-step with the real ObservationStore on real SQLite files in tmp_path.
The same seeded operation sequence is applied to both. After every step the
persisted assessment latch (state, reasons, last check) is compared, as are the
public reads (resolve_payloads withdrawn bit and latest row, cached()) for the
touched scope; all scopes are swept every FULL_EVERY steps and at the end.
Every register/status/withdraw result is compared at the step that produced it.

Model semantics (per canonical vertical and session scope, keyed by payload
digest):
  * observations are receipts; the latest is max observed_at, then min receipt_id;
  * re-putting identical bytes changes nothing and preserves CURRENT;
  * a put whose latest receipt or normalized summary differs from an assessment
    dependency latches that assessment immediately (change-then-restore stays
    invalid);
  * withdrawal is all-or-nothing (a mixed-missing request changes nothing),
    idempotent, survives re-observation and restart, and latches dependents;
  * a status read latches expiry and clock regression; latches are terminal
    and keep their first recorded reasons;
  * nothing crosses (vertical, session_scope).

Status reads mutate the latch, so the per-step comparison of the latch reads
the two documented persisted tables with a plain SELECT (no public read-only
accessor exists); every other comparison uses public store methods. Time is
injected the same way the existing tests do it: an explicit ``now`` for the
assessment API and a monkeypatched ``time`` module for ``cached()``.

On divergence the failure prints the seed and a greedily shrunk op trace.
Source tests only: this does not establish production admission or runtime
health.
"""
from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import pytest

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))

import szl_verticals.store as store_module  # noqa: E402
from szl_verticals.evidence import resolve_evidence  # noqa: E402
from szl_verticals.store import ObservationStore  # noqa: E402

START = 10_000.0
FRESHNESS = 100.0
STEPS = 25
FULL_EVERY = 5
SEEDS = list(range(1, 41))
# Seeds on which the STORE (not the model) was shown wrong: {seed: reason}.
# Each stays xfail(strict=True) with its printed minimal repro until fixed.
KNOWN_STORE_DIVERGENCES: dict[int, str] = {}

SCOPES = (("finance", "oracle-session-one"), ("finance", "oracle-session-two"),
          ("counsel", "oracle-session-one"))
CONNECTOR_FOR = {"finance": "oracle-finance-feed", "counsel": "oracle-counsel-feed"}
CONNECTORS = {cid: SimpleNamespace(id=cid, vertical=vertical, freshness_seconds=FRESHNESS)
              for vertical, cid in CONNECTOR_FOR.items()}
DIGESTS = ("1" * 64, "2" * 64, "3" * 64)
QUERY_HASH = "e" * 64
SUMMARIES = ({"fixture_text": "original bytes"}, {"fixture_text": "changed once"},
             {"fixture_text": "changed twice"})
WITHDRAWN, MISSING, NOT_FRESH = "EVIDENCE_WITHDRAWN", "EVIDENCE_MISSING", "EVIDENCE_NOT_FRESH"
RECORD_CHANGED, SUMMARY_CHANGED = "EVIDENCE_RECORD_CHANGED", "EVIDENCE_SUMMARY_CHANGED"
CLOCK_REGRESSED = "ASSESSMENT_CLOCK_REGRESSED"


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def make_receipt(scope: int, digest: str, observed: float) -> dict:
    vertical, session = SCOPES[scope]
    receipt = {
        "schema": "szl.connector-observation/v2", "vertical": vertical,
        "connector_id": CONNECTOR_FOR[vertical], "session_scope": session,
        "query_hash": QUERY_HASH, "source_url": "https://oracle.fixture.test/feed",
        "http_status": 200, "payload_sha256": digest, "observed_at": float(observed),
        "expires_at": float(observed) + FRESHNESS, "state": "OBSERVED",
        "truth_label": "REPORTED",
    }
    receipt["receipt_id"] = hashlib.sha256(_canonical(receipt).encode("utf-8")).hexdigest()
    return receipt


# ---------------------------------------------------------------- reference model
class Model:
    def __init__(self) -> None:
        self.clock = START
        self.rows: dict[tuple[int, str], dict[str, list]] = {}  # -> {receipt_id: [observed, variant]}
        self.withdrawn: set[tuple[int, str]] = set()
        self.assessments: dict[str, dict] = {}
        self.attempted: list[str] = []

    def latest(self, sc, d):
        recs = self.rows.get((sc, d))
        if not recs:
            return None
        rid = min(recs, key=lambda r: (-recs[r][0], r))
        return rid, recs[rid][0], recs[rid][1]

    def reason(self, sc, d, dep, now):
        rid, variant, observed, expires = dep
        cur = self.latest(sc, d)
        if (sc, d) in self.withdrawn:
            return WITHDRAWN
        if cur is None:
            return MISSING
        if not observed <= now < expires:
            return NOT_FRESH
        if cur[0] != rid:
            return RECORD_CHANGED
        if cur[2] != variant:
            return SUMMARY_CHANGED
        return None

    def _latch_dependents(self, sc, d):
        # Writes latch immediately, judged at the dependency's own observation time.
        for a in self.assessments.values():
            if a["scope"] == sc and not a["latched"] and d in a["deps"]:
                reason = self.reason(sc, d, a["deps"][d], a["deps"][d][2])
                if reason:
                    a["latched"], a["reasons"] = True, [{"payload_sha256": d, "reason": reason}]

    def put(self, sc, d, rid, observed, variant):
        self.rows.setdefault((sc, d), {})[rid] = [observed, variant]
        self._latch_dependents(sc, d)

    def withdraw(self, sc, digests):
        if any(not self.rows.get((sc, d)) for d in digests):
            return "NOT_FOUND"  # atomic: a mixed-missing request changes nothing
        for d in sorted(set(digests)):
            self.withdrawn.add((sc, d))
            self._latch_dependents(sc, d)
        return "WITHDRAWN"

    def admissible(self, sc, d, now):
        cur = self.latest(sc, d)
        return (cur is not None and (sc, d) not in self.withdrawn
                and cur[1] <= now < cur[1] + FRESHNESS)

    def register(self, aid, sc, kind, digests):
        self.attempted.append(aid)
        if not all(self.admissible(sc, d, self.clock) for d in digests):
            return None
        deps = {}
        for d in digests:
            rid, observed, variant = self.latest(sc, d)
            deps[d] = (rid, variant, observed, observed + FRESHNESS)
        self.assessments[aid] = {"scope": sc, "kind": kind, "deps": deps, "last": self.clock,
                                 "latched": False, "reasons": []}
        return ("CURRENT", [])

    def status(self, aid, sc):
        a, now = self.assessments.get(aid), self.clock
        if a is None or a["scope"] != sc:
            return None
        if not a["latched"]:
            changes = [{"payload_sha256": d, "reason": r} for d in sorted(a["deps"])
                       if (r := self.reason(sc, d, a["deps"][d], now))]
            if now < a["last"]:
                changes.append({"payload_sha256": None, "reason": CLOCK_REGRESSED})
            a["latched"], a["reasons"] = bool(changes), changes
        a["last"] = max(a["last"], now)
        return ("REVALIDATION_REQUIRED" if a["latched"] else "CURRENT", list(a["reasons"]))

    def cached(self, sc):
        best = None
        for (s, d), recs in self.rows.items():
            for rid, (observed, _variant) in recs.items():
                if s == sc and (best is None or (-observed, rid) < best[0]):
                    best = ((-observed, rid), d, rid, observed)
        if best is None:
            return None
        _, d, rid, observed = best
        if (sc, d) in self.withdrawn or not observed <= self.clock < observed + FRESHNESS:
            return None
        return rid


# ---------------------------------------------------------------- op generation
KINDS = ("fetch", "reput", "mutate", "restore", "withdraw", "restart", "advance",
         "rollback", "register", "status")
WEIGHTS = (16, 9, 7, 7, 9, 4, 9, 6, 15, 18)


def generate(rng: random.Random, model: Model, seed: int, step: int) -> tuple:
    known = sorted(key for key, recs in model.rows.items() if recs)
    kind = rng.choices(KINDS, WEIGHTS)[0]
    if kind in ("reput", "mutate", "restore"):
        if known:
            sc, d = rng.choice(known)
            return (kind, sc, d)
        kind = "fetch"
    live = sorted(aid for aid, a in model.assessments.items() if not a["latched"])
    if kind == "fetch":
        if live and rng.random() < 0.35:  # refetch a live dependency (new or same receipt)
            a = model.assessments[rng.choice(live)]
            return ("fetch", a["scope"], rng.choice(sorted(a["deps"])), rng.choice((0, 0, 1, 2)))
        return ("fetch", rng.randrange(len(SCOPES)), rng.choice(DIGESTS), rng.choice((0, 0, 1, 2)))
    if kind == "withdraw":
        if live and rng.random() < 0.6:  # aim at a live dependency, sometimes mixed
            a = model.assessments[rng.choice(live)]
            picked = {rng.choice(sorted(a["deps"]))}
            if rng.random() < 0.4:
                picked.add(rng.choice(DIGESTS))
            return ("withdraw", a["scope"], tuple(sorted(picked)))
        return ("withdraw", rng.randrange(len(SCOPES)),
                tuple(sorted(rng.sample(DIGESTS, rng.choice((1, 1, 2))))))
    if kind == "restart":
        return ("restart",)
    if kind == "advance":
        return ("advance", rng.choice((1.0, 7.0, 30.0, 60.0, 150.0)))
    if kind == "rollback":
        return ("rollback", rng.choice((1.0, 5.0, 40.0)))
    if kind == "status" and model.attempted:
        registered = sorted(model.assessments)
        aid = rng.choice(registered if registered and rng.random() < 0.85 else model.attempted)
        a = model.assessments.get(aid)
        sc = a["scope"] if a and rng.random() < 0.85 else rng.randrange(len(SCOPES))
        return ("status", aid, sc)
    # register (also the fallback for a status with nothing to query)
    ready = sorted({s for (s, d) in known if model.admissible(s, d, model.clock)})
    sc = rng.choice(ready) if ready and rng.random() < 0.8 else rng.randrange(len(SCOPES))
    admissible = [d for d in DIGESTS if model.admissible(sc, d, model.clock)]
    pool = admissible if admissible and rng.random() < 0.8 else list(DIGESTS)
    digests = tuple(sorted(rng.sample(pool, min(len(pool), rng.choice((1, 1, 2))))))
    aid = hashlib.sha256(f"oracle:{seed}:{step}".encode()).hexdigest()
    return ("register", aid, sc, rng.choice(("hatun-review", "intelligence-plan")), digests)


def fmt(op: tuple) -> str:
    def short(value):
        if isinstance(value, str) and len(value) == 64:
            return value[:6]
        if isinstance(value, tuple):
            return "[" + ",".join(short(v) for v in value) + "]"
        return str(value)
    return op[0] + "(" + ", ".join(short(v) for v in op[1:]) + ")"


# ---------------------------------------------------------------- lock-step driver
class Divergence(AssertionError):
    pass


def expect(ok: bool, detail: str) -> None:
    if not ok:
        raise Divergence(detail)


def apply_model(op: tuple, model: Model):
    """Model-only application; returns the model's observable result."""
    kind = op[0]
    if kind in ("fetch", "reput", "mutate", "restore"):
        sc, d = op[1], op[2]
        if kind == "fetch":
            observed, variant = model.clock, op[3]
        else:
            cur = model.latest(sc, d)
            if cur is None:
                return None
            _rid, observed, current = cur
            variant = {"reput": current, "mutate": (current + 1) % 3, "restore": 0}[kind]
        receipt = make_receipt(sc, d, observed)
        model.put(sc, d, receipt["receipt_id"], observed, variant)
        return (receipt, variant)
    if kind == "withdraw":
        return model.withdraw(op[1], op[2])
    if kind == "advance":
        model.clock += op[1]
    elif kind == "rollback":
        model.clock = max(0.0, model.clock - op[1])
    elif kind == "register":
        return model.register(op[1], op[2], op[3], op[4])
    elif kind == "status":
        return model.status(op[1], op[2])
    return None


def apply_store(op: tuple, model: Model, store: ObservationStore, clock: list):
    kind = op[0]
    vertical, session = SCOPES[op[2] if kind in ("register", "status") else op[1]] \
        if kind not in ("restart", "advance", "rollback") else (None, None)
    now = model.clock  # captured before the model steps
    want = apply_model(op, model)
    clock[0] = model.clock
    if kind in ("fetch", "reput", "mutate", "restore"):
        if want is not None:
            receipt, variant = want
            store.put(receipt, SUMMARIES[variant])
    elif kind == "withdraw":
        try:
            store.withdraw_payloads(vertical=vertical, session_scope=session,
                                    payload_digests=list(op[2]), now=now)
            got = "WITHDRAWN"
        except LookupError:
            got = "NOT_FOUND"
        expect(got == want, f"withdraw result store={got} model={want}")
    elif kind == "restart":
        store = ObservationStore()
        expect(store.error is None, f"restart failed: {store.error}")
    elif kind == "register":
        snapshot = resolve_evidence(store, vertical=vertical, session_scope=session,
                                    digests=list(op[4]), connectors=CONNECTORS, now=now)
        expect((snapshot.state == "COMPLETE") == (want is not None),
               f"admission store={snapshot.state}{list(snapshot.blockers)} "
               f"model={'COMPLETE' if want else 'NOT_ADMISSIBLE'}")
        try:
            result = store.register_assessment(vertical=vertical, session_scope=session,
                                               assessment_id=op[1], kind=op[3],
                                               snapshot=snapshot, now=now)
            got = (result["state"], result["changed_dependencies"])
        except ValueError:
            got = None
        expect(got == want, f"register store={got} model={want}")
    elif kind == "status":
        result = store.assessment_status(vertical=vertical, session_scope=session,
                                         assessment_id=op[1], now=now, connectors=CONNECTORS)
        got = None if result is None else (result["state"], result["changed_dependencies"])
        expect(got == want, f"status store={got} model={want}")
        if result is not None:
            a = model.assessments[op[1]]
            decision = "REVIEW" if a["kind"] == "hatun-review" else "READY_FOR_INFERENCE"
            expect(result["checked_at"] == now and result["original_decision"] == decision
                   and result["can_execute"] is False and result["automatic_replay"] is False,
                   f"status envelope {result}")
    return store


def touched(op: tuple) -> tuple[int, ...]:
    if op[0] in ("register", "status"):
        return (op[2],)
    if op[0] in ("fetch", "reput", "mutate", "restore", "withdraw"):
        return (op[1],)
    return tuple(range(len(SCOPES)))  # restart / clock moves affect every scope


def compare(model: Model, store: ObservationStore, peek: sqlite3.Connection, scopes=None) -> None:
    for sc in range(len(SCOPES)) if scopes is None else scopes:
        vertical, session = SCOPES[sc]
        rows = {row["payload_sha256"]: row for row in store.resolve_payloads(
            vertical=vertical, session_scope=session, payload_digests=list(DIGESTS))}
        for d in DIGESTS:
            cur, row = model.latest(sc, d), rows.get(d)
            want = None if cur is None else (cur[0], (sc, d) in model.withdrawn, SUMMARIES[cur[2]])
            got = None if row is None else (row["receipt_id"], bool(row["withdrawn"]),
                                            json.loads(row["summary_json"]))
            expect(got == want, f"latest row scope={sc} digest={d[:6]} store={got} model={want}")
        hit = store.cached(vertical=vertical, connector_id=CONNECTOR_FOR[vertical],
                           session_scope=session, query_hash=QUERY_HASH)
        got_hit = None if hit is None else hit["receipt_id"]
        expect(got_hit == model.cached(sc), f"cached scope={sc} store={got_hit} model={model.cached(sc)}")
    stored = {row[0]: (SCOPES.index((row[1], row[2])), bool(row[3]), json.loads(row[4]), row[5])
              for row in peek.execute(
                  "SELECT assessment_id, vertical, session_scope, invalidated, reasons_json, "
                  "last_checked_at FROM evidence_assessments")}
    modeled = {aid: (a["scope"], a["latched"], a["reasons"], a["last"])
               for aid, a in model.assessments.items()}
    for aid in sorted(set(stored) | set(modeled)):
        expect(stored.get(aid) == modeled.get(aid),
               f"latch {aid[:6]} store={stored.get(aid)} model={modeled.get(aid)}")


def run(tmp_path: Path, monkeypatch, *, seed: int, ops=None, tag: str = "run"):
    """Returns (trace, None) or (trace, divergence) with trace ending at the failing op."""
    db_path = tmp_path / f"{tag}.sqlite3"
    monkeypatch.setenv("SZL_STATE_PATH", str(db_path))
    model, clock = Model(), [START]
    monkeypatch.setattr(store_module, "time", SimpleNamespace(time=lambda: clock[0]))
    store = ObservationStore()
    assert store.error is None, store.error
    rng, trace = random.Random(seed), []
    count = STEPS if ops is None else len(ops)
    # One idle read connection held for the run keeps SQLite from deleting and
    # recreating the WAL/SHM files on every store call (the dominant Windows
    # cost). It only runs SELECTs outside any transaction, so it never blocks or
    # changes the store's writes. It is also the read-only view of the latch.
    with closing(sqlite3.connect(db_path)) as peek:
        for step in range(count):
            op = generate(rng, model, seed, step) if ops is None else ops[step]
            trace.append(op)
            try:
                store = apply_store(op, model, store, clock)
                # Every assessment latch is compared after every step; observation
                # reads cover the touched scope each step and all scopes every
                # FULL_EVERY steps and at the end.
                full = step == count - 1 or step % FULL_EVERY == FULL_EVERY - 1
                compare(model, store, peek, None if full else touched(op))
            except Divergence as exc:
                return trace, f"step {step} {fmt(op)}: {exc}"
    return trace, None


def shrink(tmp_path: Path, monkeypatch, seed: int, trace: list, budget: int = 200):
    """Greedy one-op-at-a-time removal while any divergence still reproduces."""
    detail, attempt, changed = None, 0, True
    while changed and attempt < budget:
        changed = False
        for index in range(len(trace)):
            attempt += 1
            candidate = trace[:index] + trace[index + 1:]
            got, why = run(tmp_path, monkeypatch, seed=seed, ops=candidate, tag=f"shrink{attempt}")
            if why is not None:
                trace, detail, changed = got, why, True
                break
            if attempt >= budget:
                break
    return trace, detail


def assert_no_divergence(tmp_path, monkeypatch, seed, ops=None):
    trace, why = run(tmp_path, monkeypatch, seed=seed, ops=ops)
    if why is None:
        return
    small, small_why = shrink(tmp_path, monkeypatch, seed, trace)
    lines = "\n".join(f"  {i}: {fmt(op)}" for i, op in enumerate(small))
    pytest.fail(f"replay oracle divergence seed={seed}\nfirst: {why}\n"
                f"minimal trace ({len(small)} ops): {small_why or why}\n{lines}\n"
                f"repro ops={small!r}", pytrace=False)


# ---------------------------------------------------------------- tests
@pytest.mark.parametrize("seed", [
    pytest.param(seed, marks=pytest.mark.xfail(strict=True, reason=KNOWN_STORE_DIVERGENCES[seed]))
    if seed in KNOWN_STORE_DIVERGENCES else seed for seed in SEEDS])
def test_store_matches_reference_model(seed, tmp_path, monkeypatch):
    assert_no_divergence(tmp_path, monkeypatch, seed)


A, B, C = DIGESTS
AID = hashlib.sha256(b"oracle:named").hexdigest()
NAMED = {
    "change_then_restore_stays_invalid": [
        ("fetch", 0, A, 0), ("register", AID, 0, "hatun-review", (A,)),
        ("mutate", 0, A), ("restore", 0, A), ("status", AID, 0)],
    "identical_reobservation_preserves_current": [
        ("fetch", 0, A, 0), ("register", AID, 0, "intelligence-plan", (A,)),
        ("reput", 0, A), ("restart",), ("reput", 0, A), ("status", AID, 0)],
    "mixed_missing_withdrawal_is_atomic": [
        ("fetch", 0, A, 0), ("register", AID, 0, "hatun-review", (A,)),
        ("withdraw", 0, (A, B)), ("status", AID, 0), ("withdraw", 0, (A,)),
        ("withdraw", 0, (A,)), ("reput", 0, A), ("restart",), ("status", AID, 0)],
    "scope_isolation": [
        ("fetch", 0, A, 0), ("fetch", 1, A, 0), ("fetch", 2, A, 0),
        ("register", AID, 1, "hatun-review", (A,)), ("withdraw", 0, (A,)),
        ("mutate", 2, A), ("status", AID, 0), ("status", AID, 2), ("status", AID, 1)],
    "expiry_then_rollback_is_terminal": [
        ("fetch", 0, A, 0), ("register", AID, 0, "hatun-review", (A,)),
        ("advance", 150.0), ("status", AID, 0), ("rollback", 40.0), ("rollback", 40.0),
        ("rollback", 40.0), ("status", AID, 0)],
    "clock_regression_is_terminal": [
        ("fetch", 0, A, 0), ("advance", 7.0), ("register", AID, 0, "hatun-review", (A,)),
        ("rollback", 1.0), ("status", AID, 0), ("advance", 7.0), ("status", AID, 0)],
    "withdrawn_latest_does_not_resurrect_older_cache": [
        ("fetch", 0, B, 0), ("advance", 7.0), ("fetch", 0, A, 0), ("withdraw", 0, (A,)),
        ("restart",), ("fetch", 0, A, 0)],
}


@pytest.mark.parametrize("name", sorted(NAMED))
def test_named_traces_match_reference_model(name, tmp_path, monkeypatch):
    assert_no_divergence(tmp_path, monkeypatch, seed=0, ops=NAMED[name])


def test_seed_corpus_exercises_the_latch_paths():
    """Model-only replay of the exact generated corpus: proves the seeds reach each path."""
    seen: dict[str, int] = {}
    seeds_with: dict[str, set] = {}

    def note(key):
        seen[key] = seen.get(key, 0) + 1
        seeds_with.setdefault(key, set()).add(seed)

    for seed in SEEDS:
        model, rng = Model(), random.Random(seed)
        for step in range(STEPS):
            op = generate(rng, model, seed, step)
            live = {aid for aid, a in model.assessments.items() if not a["latched"]}
            partial = op[0] == "withdraw" and any(model.rows.get((op[1], d)) for d in op[2])
            result = apply_model(op, model)
            note(op[0])
            if op[0] == "withdraw" and result == "NOT_FOUND" and partial:
                note("withdraw_mixed_missing")
            if op[0] == "register":
                note("register_admitted" if result else "register_refused")
            if op[0] == "status" and result and result[0] == "CURRENT":
                note("status_current")
            if op[0] == "status" and result is None and op[1] in model.assessments:
                note("status_foreign_scope")
            if op[0] == "reput" and live and all(
                    not model.assessments[aid]["latched"] for aid in live):
                note("reput_preserves_live")
            for aid in live:
                if model.assessments[aid]["latched"]:
                    for change in model.assessments[aid]["reasons"]:
                        note(f"latch:{op[0]}:{change['reason']}")
    required = {"restart", "rollback", "withdraw_mixed_missing", "register_admitted",
                "register_refused", "status_current", "status_foreign_scope",
                "reput_preserves_live", f"latch:withdraw:{WITHDRAWN}",
                f"latch:mutate:{SUMMARY_CHANGED}", f"latch:fetch:{RECORD_CHANGED}",
                f"latch:status:{NOT_FRESH}", f"latch:status:{CLOCK_REGRESSED}"}
    missing = sorted(required - set(seen))
    assert not missing, f"seed corpus never reaches {missing}; coverage={seen}"
    # The withdrawal latch is the point of this oracle: many seeds must hit it.
    assert len(seeds_with[f"latch:withdraw:{WITHDRAWN}"]) >= 10, seeds_with
