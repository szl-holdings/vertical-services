#!/usr/bin/env python3
"""Guard-teeth receipts: prove each safety guard is load-bearing in the tests.

A green suite is not evidence that a guard is exercised (vertical-services #40
and #44 merged green on a 188-byte stub test).  For every guard declared in
tools/guard_teeth.json this harness:

1. copies the git-TRACKED files of the repo's source directories (default:
   deploy/ services/ tools/ tests/) into a fresh temporary directory -- the
   working tree is never modified; untracked files (for example another
   agent's scratch tests or a stray conftest.py) are excluded and listed in
   the receipt unless --include-untracked is given;
2. requires that the guard's "find" text occurs EXACTLY once in its file
   (otherwise the guard is MANIFEST_STALE, never silently skipped);
3. applies the mutant ("replace"), asserts the bytes changed, that the
   mutated Python still compiles, and -- when the unmutated module imports
   cleanly in the baseline copy -- that the mutated module still IMPORTS in a
   subprocess (otherwise MUTANT_INVALID: a broken mutant is never a kill);
4. runs ``<python> -m pytest -q -p no:cacheprovider -x <tests>`` with the
   environment CI uses, and records KILLED or SURVIVED.

KILLED is strict: pytest exited 1 AND at least one test-level node id
(``path::test``) is reported FAILED AND the failure is not a name-binding
error (NameError / ImportError / ModuleNotFoundError / UnboundLocalError),
which would mean the mutant broke the code rather than removed a guard.
Collection errors (pytest exit 2, file-level ERROR ids) are MUTANT_INVALID;
exit 1 with only setup ERRORs or no parsed failing id is UNPROVEN_ERROR.
Neither counts as a kill.

A kill must also REPRODUCE.  The first killing node id is re-run ALONE,
--confirm-mutant-runs times (default 2) on the mutant, each run a genuine
failure of that test, and then -- after the unmutated bytes are restored in
the same copy -- --confirm-baseline-runs times (default 3) on the baseline,
each run a pass.  A kill that does not reproduce (an order-dependent or flaky
killer) is UNPROVEN_ERROR, never KILLED; ``kill_stable`` and
``kill_confirmation`` record what happened.  Every kill also records
``kill_kind``: ``assertion`` when the test asserted the property (assert,
AssertionError, pytest.fail, pytest.raises "DID NOT RAISE") or
``exception:<Type>`` when the test crashed with an uncaught exception.
Exception kills still count, but they are totalled and listed separately so
a reviewer can see which guards are proven only by a crash.

--dry-run (read only, no tests) checks that every find still occurs exactly
once, every mutant still compiles and every listed test file exists; it is
the cheap staleness gate CI runs on every pull request.

The unmutated baseline always runs first; a red baseline exits 3.

Verdict ALL_GUARDS_KILLED means every guard in the manifest was run and
KILLED; a --only subset that is all KILLED reads SELECTED_GUARDS_KILLED.

Exit codes: 0 every selected guard KILLED; 1 at least one SURVIVED (a real
finding: that guard has no test teeth); 2 a manifest/harness problem
(MANIFEST_STALE, MUTANT_INVALID, UNPROVEN_ERROR, NO_TESTS, TIMEOUT, ERROR)
and no survivor; 3 BASELINE_RED.

Stdlib only, Python 3.11+.  Honesty: the receipt is MEASURED output of this
run.  It is not signed and does not claim anything is LIVE.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as _dt
import difflib
import hashlib
import itertools
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any, Callable

RECEIPT_SCHEMA = "szl.guard-teeth-receipt/v1"
MANIFEST_SCHEMA = "szl.guard-teeth-manifest/v1"
DEFAULT_COPY = ("deploy", "services", "tools", "tests")
CI_SIGNING_FIXTURE = "ci-contract-key-not-used-in-production"  # public CI fixture, not a secret
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "*.sqlite3", "*.sqlite3-*")
SECRETISH = re.compile(r"(TOKEN|SECRET|PASSWORD|API_KEY|ACCESS_KEY|PRIVATE_KEY|_KEY$)", re.I)
NODE_RE = re.compile(r"^(FAILED|ERROR)\s+(\S+)(?:\s+-\s+(.*))?$")
SUMMARY_RE = re.compile(r"(\d+)\s+(passed|failed|error|errors|skipped|deselected|xfailed|xpassed)")
BINDING_ERRORS = ("NameError", "ImportError", "ModuleNotFoundError", "UnboundLocalError")
DEFAULT_IMPORT_ROOTS = ("deploy", "services", ".")

KILLED = "KILLED"
SURVIVED = "SURVIVED"
STALE = "MANIFEST_STALE"
INVALID = "MUTANT_INVALID"
UNPROVEN = "UNPROVEN_ERROR"
NO_TESTS = "NO_TESTS"
TIMEOUT = "TIMEOUT"
ERROR = "ERROR"
ENV_FAULT = "ENVIRONMENT_FAULT"
ALL_STATUSES = (KILLED, SURVIVED, STALE, INVALID, UNPROVEN, ENV_FAULT, NO_TESTS, TIMEOUT, ERROR)
# Host faults that make tests fail for reasons unrelated to the mutant.  Measured on
# 2026-09-25: with C: at 0 bytes free, two mutants "failed" with
# "database or disk is full" / "assessment store unavailable"; those are not kills.
# SQLite "database is locked" is lock contention on the host, not a missing guard
# (#48's known limits measured it at 1/6480 under contention).
ENV_FAULT_RE = re.compile(r"database or disk is full|database is locked|No space left on device|ENOSPC|"
                          r"not enough space on the disk|disk quota exceeded|MemoryError", re.I)
DEFAULT_MIN_FREE_MB = 1024
# A kill is re-run alone this many times on the mutant (each must fail) and on the
# unmutated copy (each must pass) before it counts.
DEFAULT_CONFIRM_MUTANT_RUNS = 2
DEFAULT_CONFIRM_BASELINE_RUNS = 3
# Short-summary heads that mean the test ASSERTED the property: a bare `assert ...`
# (pytest's rewritten message), AssertionError, and pytest's own `Failed`
# (pytest.fail / pytest.raises "DID NOT RAISE").  Anything else is a crash.
ASSERTION_HEADS = ("AssertionError", "Failed")
EXC_NAME_RE = re.compile(r"[A-Za-z_][\w.]*")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git(repo: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", "replace").strip()


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(f"manifest schema must be {MANIFEST_SCHEMA}")
    seen: set[str] = set()
    for guard in data.get("guards", []):
        for key in ("id", "file", "find", "replace", "why", "tests"):
            if key not in guard:
                raise ValueError(f"guard {guard.get('id')!r} missing {key!r}")
        if not isinstance(guard["tests"], list) or not guard["tests"]:
            raise ValueError(f"guard {guard['id']!r} lists no tests")
        if guard["id"] in seen:
            raise ValueError(f"duplicate guard id {guard['id']!r}")
        seen.add(guard["id"])
        if guard["find"] == guard["replace"]:
            raise ValueError(f"guard {guard['id']!r} mutant is identical to its find text")
    if not data.get("guards"):
        raise ValueError("manifest declares no guards")
    return data


def child_env(repo_head: str | None, state_path: Path) -> dict[str, str]:
    """Same variables CI sets; secret-looking inherited variables are dropped."""
    env = {k: v for k, v in os.environ.items() if not SECRETISH.search(k)}
    env["SENTRA_SIGNING_KEY"] = CI_SIGNING_FIXTURE
    env["SZL_SOURCE_REVISION"] = repo_head or "0" * 40
    env["SZL_STATE_PATH"] = str(state_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["COLUMNS"] = "400"  # keep "FAILED id - ExcType: msg" summary lines untruncated
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTHONPATH", None)
    return env


def remove_tree(path: Path) -> bool:
    """Delete a temp tree, clearing read-only bits (git objects on Windows).
    Returns False if anything is left behind, so the receipt can say so."""
    def _retry(func, target, _exc):
        try:
            os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
            func(target)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_retry)
    else:
        shutil.rmtree(path, onerror=_retry)
    return not path.exists()


def git_list(repo: Path, *args: str) -> list[str] | None:
    """NUL-separated `git ls-files` output as a list, or None when git is unavailable."""
    try:
        out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z", *args], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return sorted(p for p in out.stdout.decode("utf-8", "replace").split("\0") if p)


def is_git_toplevel(repo: Path) -> bool:
    top = git(repo, "rev-parse", "--show-toplevel")
    return top is not None and Path(top).resolve() == repo.resolve()


def copy_tree(repo: Path, dest: Path, dirs: list[str], files: list[str] | None = None) -> None:
    """Copy into dest.  With `files` (git-tracked paths) only those files are
    copied (working-tree bytes); otherwise the listed directories wholesale."""
    if files is not None:
        for rel in files:
            src = repo / rel
            if src.is_file():
                (dest / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest / rel)
        return
    for name in dirs:
        src = repo / name
        if src.is_dir():
            shutil.copytree(src, dest / name, ignore=IGNORE)
        elif src.is_file():
            (dest / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / name)


def eol_adapt(text: str, file_text: str) -> str:
    if "\r\n" in file_text and "\r\n" not in text:
        return text.replace("\n", "\r\n")
    return text


def mutate(root: Path, guard: dict[str, Any]) -> dict[str, Any]:
    """Apply one mutant inside a copied tree.  Returns facts or a status."""
    target = root / guard["file"]
    facts: dict[str, Any] = {"file": guard["file"]}
    if not target.is_file():
        return {**facts, "status": STALE, "detail": "file not found"}
    before = target.read_bytes()
    facts["file_sha256_before"] = sha256_bytes(before)
    try:
        text = before.decode("utf-8")
    except UnicodeDecodeError:
        return {**facts, "status": STALE, "detail": "file is not UTF-8"}
    facts["eol"] = "CRLF" if "\r\n" in text else "LF"
    find = eol_adapt(guard["find"], text)
    replace = eol_adapt(guard["replace"], text)
    count = text.count(find)
    facts["find_occurrences"] = count
    if count != 1:
        return {**facts, "status": STALE, "detail": f"find occurs {count} times (must be exactly 1)"}
    mutated = text.replace(find, replace, 1)
    after = mutated.encode("utf-8")
    if after == before:
        return {**facts, "status": INVALID, "detail": "mutant did not change the file bytes"}
    facts["file_sha256_after"] = sha256_bytes(after)
    if target.suffix == ".py":
        try:
            compile(mutated, str(target), "exec")
        except SyntaxError as exc:
            return {**facts, "status": INVALID, "detail": f"mutant does not compile: {exc.msg} line {exc.lineno}"}
    target.write_bytes(after)
    if target.read_bytes() != after:
        return {**facts, "status": ERROR, "detail": "mutant write did not persist"}
    diff = difflib.unified_diff(
        text.replace("\r\n", "\n").splitlines(), mutated.replace("\r\n", "\n").splitlines(),
        fromfile=f"a/{guard['file']}", tofile=f"b/{guard['file']}", n=1, lineterm="")
    facts["mutant_diff"] = "\n".join(diff)
    return facts


def module_for(rel: str, roots: list[str]) -> tuple[str, str] | None:
    """Map a repo-relative .py path to (import root, dotted module name)."""
    path = PurePosixPath(rel.replace("\\", "/"))
    if path.suffix != ".py":
        return None
    for root in sorted(roots, key=lambda r: (r in ("", "."), -len(r))):
        if root in ("", "."):
            sub = path
        else:
            try:
                sub = path.relative_to(PurePosixPath(root))
            except ValueError:
                continue
        parts = list(sub.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if parts and all(p.isidentifier() for p in parts):
            return (root or "."), ".".join(parts)
    return None


PROBE_CODE = (
    "import importlib, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "try:\n"
    "    importlib.import_module(sys.argv[2])\n"
    "except BaseException as exc:\n"
    "    print('IMPORT_FAILED %s: %s' % (exc.__class__.__name__, str(exc)[:300]))\n"
    "    raise SystemExit(7)\n"
    "print('IMPORT_OK')\n"
)


def import_probe(python: str, root: Path, rel: str, roots: list[str], env: dict[str, str],
                 timeout: float = 180.0) -> dict[str, Any]:
    """Import the (possibly mutated) module in a fresh interpreter inside `root`."""
    target = module_for(rel, roots)
    if target is None:
        return {"state": "NOT_APPLICABLE"}
    import_root, module = target
    try:
        proc = subprocess.run([python, "-c", PROBE_CODE, str((root / import_root).resolve()), module],
                              cwd=str(root), env=env, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"state": "TIMEOUT", "module": module}
    out = (proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")).strip()
    if proc.returncode == 0 and "IMPORT_OK" in out:
        return {"state": "OK", "module": module}
    line = next((ln for ln in out.splitlines() if ln.startswith("IMPORT_FAILED")), tail(out, 3))
    return {"state": "FAILED", "module": module, "detail": line.replace("IMPORT_FAILED ", "", 1)}


def run_pytest(python: str, root: Path, tests: list[str], env: dict[str, str],
               timeout: float) -> dict[str, Any]:
    cmd = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-x", "-rfE",
           f"--basetemp={root / '.pytest-tmp'}", *tests]
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=str(root), env=env, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"").decode("utf-8", "replace")
        return {"exit_code": None, "timed_out": True, "seconds": round(time.monotonic() - started, 3),
                "output": out}
    out = proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")
    return {"exit_code": proc.returncode, "timed_out": False,
            "seconds": round(time.monotonic() - started, 3), "output": out}


def parse_nodes(output: str) -> list[dict[str, str]]:
    """Short-summary lines (-rfE): [{"kind": FAILED|ERROR, "id": node, "reason": text}]."""
    nodes: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for line in output.splitlines():
        match = NODE_RE.match(line.strip())
        if match and (match.group(1), match.group(2)) not in seen:
            seen.add((match.group(1), match.group(2)))
            nodes.append({"kind": match.group(1), "id": match.group(2), "reason": (match.group(3) or "").strip()})
    return nodes


def parse_failures(output: str) -> list[str]:
    ids: list[str] = []
    for node in parse_nodes(output):
        if node["id"] not in ids:
            ids.append(node["id"])
    return ids


def binding_error(reason: str) -> str | None:
    head = reason.split(":", 1)[0].strip()
    return head if head.split(".")[-1] in BINDING_ERRORS else None


def parse_summary(output: str) -> dict[str, int]:
    lines = [ln for ln in output.splitlines() if ln.strip()]
    for line in reversed(lines):
        found = SUMMARY_RE.findall(line)
        if found and (" in " in line or "passed" in line or "failed" in line):
            summary: dict[str, int] = {}
            for num, word in found:
                key = "errors" if word in ("error", "errors") else word
                summary[key] = summary.get(key, 0) + int(num)
            return summary
    return {}


def tail(output: str, lines: int = 25) -> str:
    return "\n".join(output.splitlines()[-lines:])


def classify(result: dict[str, Any]) -> tuple[str, list[str], str]:
    """Return (status, killing test ids, detail).  Only a genuine test-level
    failure is a kill; anything that merely broke the code, or a host fault
    such as a full disk, is not."""
    if result["timed_out"]:
        return TIMEOUT, [], "pytest timed out"
    code = result["exit_code"]
    if code == 0:
        return SURVIVED, [], "all listed tests passed with the guard removed"
    env = ENV_FAULT_RE.search(result["output"])
    if env:
        return ENV_FAULT, [], (f"host fault in test output ({env.group(0)!r}): failures are not attributable "
                               "to the mutant; rerun with free disk")
    if code == 5:
        return NO_TESTS, [], "pytest collected no tests"
    nodes = parse_nodes(result["output"])
    file_level = [n["id"] for n in nodes if "::" not in n["id"]]
    failed = [n for n in nodes if n["kind"] == "FAILED" and "::" in n["id"]]
    if code == 2 or file_level or "error during collection" in result["output"] \
            or "errors during collection" in result["output"]:
        return INVALID, [], (f"collection/interrupt error (pytest exit {code}); "
                             f"file-level ids {file_level or 'none'}: the mutant broke the code, it is not a kill")
    if code != 1:
        return ERROR, [], f"pytest internal/usage error (exit {code})"
    if not failed:
        errs = [n["id"] for n in nodes if n["kind"] == "ERROR"]
        return UNPROVEN, [], (f"pytest exit 1 but no test-level FAILED id parsed (setup ERRORs: {errs or 'none'}); "
                              "not counted as a kill")
    genuine = [n for n in failed if not binding_error(n["reason"])]
    if not genuine:
        kinds = sorted({binding_error(n["reason"]) or "" for n in failed})
        return INVALID, [], (f"every failing test died of a name-binding error ({', '.join(kinds)}): "
                             "the mutant broke the code rather than removed a guard")
    return KILLED, [n["id"] for n in genuine], "test-level assertion/behaviour failure"


def kill_kind(reason: str) -> str:
    """'assertion' when the killing test asserted the property, 'exception:<Type>'
    when it crashed with an uncaught exception, 'unknown' when pytest gave no
    parseable reason."""
    text = reason.strip()
    if text == "assert" or text.startswith("assert "):
        return "assertion"
    head = text.split(":", 1)[0].strip()
    if not head or not EXC_NAME_RE.fullmatch(head):
        return "unknown"
    name = head.split(".")[-1]
    return "assertion" if name in ASSERTION_HEADS else f"exception:{name}"


def confirm_kill(node: str, rerun: Callable[[str], dict[str, Any]], restore: Callable[[], bool],
                 mutant_runs: int, baseline_runs: int) -> dict[str, Any]:
    """Reproduce a kill with the killing node id ALONE: `mutant_runs` runs on the
    mutant (each must be a genuine failure of that node, as classify() defines
    it), then `restore()` puts the unmutated bytes back and `baseline_runs` runs
    must each pass.  Stops at the first run that breaks the rule."""
    runs: list[dict[str, Any]] = []
    out: dict[str, Any] = {"node": node, "mutant_runs_required": mutant_runs, "mutant_failed": 0,
                           "baseline_runs_required": baseline_runs, "baseline_passed": 0,
                           "stable": False, "environment_fault": False, "runs": runs, "detail": ""}
    for i in range(1, mutant_runs + 1):
        res = rerun(node)
        status, failing, _ = classify(res)
        runs.append({"on": "mutant", "status": status, "exit_code": res["exit_code"],
                     "seconds": res.get("seconds"), "pytest_summary": parse_summary(res["output"])})
        if status != KILLED or node not in failing:
            out["environment_fault"] = status == ENV_FAULT
            runs[-1]["output_tail"] = tail(res["output"], 15)
            out["detail"] = (f"mutant rerun {i}/{mutant_runs} of {node} alone was {status}, "
                             "not a failure of that test")
            return out
        out["mutant_failed"] += 1
    if not restore():
        out["detail"] = "the unmutated file could not be restored for the baseline reruns"
        return out
    for i in range(1, baseline_runs + 1):
        res = rerun(node)
        summary = parse_summary(res["output"])
        passed = (res["exit_code"] == 0 and not res["timed_out"] and summary.get("passed", 0) >= 1
                  and not summary.get("failed") and not summary.get("errors"))
        runs.append({"on": "baseline", "status": "PASSED" if passed else "NOT_PASSED",
                     "exit_code": res["exit_code"], "seconds": res.get("seconds"), "pytest_summary": summary})
        if not passed:
            out["environment_fault"] = bool(ENV_FAULT_RE.search(res["output"]))
            runs[-1]["output_tail"] = tail(res["output"], 15)
            out["detail"] = (f"baseline rerun {i}/{baseline_runs} of {node} alone did not pass "
                             f"(exit {res['exit_code']}, {summary or 'no summary'})")
            return out
        out["baseline_passed"] += 1
    out["stable"] = True
    out["detail"] = (f"failed {mutant_runs}/{mutant_runs} alone on the mutant, "
                     f"passed {baseline_runs}/{baseline_runs} alone on the unmutated copy")
    return out


def free_mb(path: str) -> int:
    try:
        return int(shutil.disk_usage(path).free // (1024 * 1024))
    except OSError:
        return -1


def run_guard(guard: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    before_mb = free_mb(ctx["tmp_root"])
    if 0 <= before_mb < ctx["min_free_mb"]:
        return {"id": guard["id"], "file": guard["file"], "why": guard["why"], "tests": guard["tests"],
                "status": ENV_FAULT, "killing_tests": [], "seconds": 0.0, "free_mb_before": before_mb,
                "detail": f"only {before_mb} MB free in temp (< {ctx['min_free_mb']} MB); guard not run"}
    work = Path(tempfile.mkdtemp(prefix="szl-guardteeth-", dir=ctx["tmp_root"]))
    record: dict[str, Any] = {"id": guard["id"], "file": guard["file"], "why": guard["why"],
                              "tests": guard["tests"]}
    try:
        copy_tree(ctx["repo"], work, ctx["copy"], ctx["files"])
        target = work / guard["file"]
        original = target.read_bytes() if target.is_file() else b""
        facts = mutate(work, guard)
        record.update({k: v for k, v in facts.items() if k != "file"})
        if "status" in facts:
            record["killing_tests"] = []
            return record
        env = child_env(ctx["head"], work / "state.sqlite3")
        baseline_probe = ctx["baseline_imports"].get(guard["file"], {"state": "NOT_RUN"})
        if baseline_probe.get("state") == "OK":
            probe = import_probe(ctx["python"], work, guard["file"], ctx["import_roots"], env)
            record["import_probe"] = probe
            if probe["state"] != "OK":
                record.update({"status": INVALID, "killing_tests": [],
                               "detail": f"mutant breaks import of {probe.get('module')}: "
                                         f"{probe.get('detail', probe['state'])}"})
                return record
        else:
            record["import_probe"] = {"state": "SKIPPED",
                                      "reason": f"baseline import probe {baseline_probe.get('state')}"}
        result = run_pytest(ctx["python"], work, guard["tests"], env, ctx["timeout"])
        status, failing, detail = classify(result)
        record.update({"exit_code": result["exit_code"], "pytest_seconds": result["seconds"],
                       "pytest_summary": parse_summary(result["output"])})
        if status == KILLED:
            reasons = {n["id"]: n["reason"] for n in parse_nodes(result["output"]) if n["kind"] == "FAILED"}
            record["kill_reasons"] = [reasons.get(t, "")[:240] for t in failing]
            kind = kill_kind(reasons.get(failing[0], ""))
            reruns = itertools.count(1)

            def rerun(node: str) -> dict[str, Any]:
                fresh = child_env(ctx["head"], work / f"state-confirm-{next(reruns)}.sqlite3")
                return run_pytest(ctx["python"], work, [node], fresh, ctx["timeout"])

            def restore() -> bool:
                target.write_bytes(original)
                return sha256_bytes(target.read_bytes()) == record.get("file_sha256_before")

            confirmation = confirm_kill(failing[0], rerun, restore, ctx["confirm_mutant_runs"],
                                        ctx["confirm_baseline_runs"])
            record["kill_confirmation"] = confirmation
            record["kill_stable"] = confirmation["stable"]
            if confirmation["stable"]:
                record["kill_kind"] = kind
                detail = f"test-level failure ({kind}); {failing[0]} {confirmation['detail']}"
            else:
                confirmation["first_run_kill_kind"] = kind
                record["unconfirmed_killing_tests"] = failing
                status = ENV_FAULT if confirmation["environment_fault"] else UNPROVEN
                failing, detail = [], f"kill did not reproduce: {confirmation['detail']}"
        after_mb = free_mb(ctx["tmp_root"])
        record.update({"free_mb_before": before_mb, "free_mb_after": after_mb})
        if status in (KILLED, UNPROVEN, INVALID) and 0 <= after_mb < ctx["min_free_mb"]:
            status, failing, detail = ENV_FAULT, [], (f"free disk fell to {after_mb} MB during the run "
                                                      f"(< {ctx['min_free_mb']} MB); failure not attributable")
            record.pop("kill_kind", None)
        record.update({"status": status, "killing_tests": failing if status == KILLED else [],
                       "detail": detail})
        if status != KILLED:
            record["output_tail"] = tail(result["output"])
        return record
    except Exception as exc:  # harness fault: never reported as a kill
        record.update({"status": ERROR, "detail": f"{exc.__class__.__name__}: {exc}", "killing_tests": []})
        return record
    finally:
        record["seconds"] = round(time.monotonic() - started, 3)
        if not ctx["keep"]:
            record["temp_cleaned"] = remove_tree(work)
        else:
            record["workdir"] = str(work)


def run_baseline(tests: list[str], ctx: dict[str, Any], probe_files: list[str]) -> dict[str, Any]:
    work = Path(tempfile.mkdtemp(prefix="szl-guardteeth-base-", dir=ctx["tmp_root"]))
    try:
        copy_tree(ctx["repo"], work, ctx["copy"], ctx["files"])
        env = child_env(ctx["head"], work / "state.sqlite3")
        imports: dict[str, dict[str, Any]] = {}
        if ctx["probe_imports"]:
            for rel in sorted(set(probe_files)):
                imports[rel] = import_probe(ctx["python"], work, rel, ctx["import_roots"], env)
        ctx["baseline_imports"] = imports
        result = run_pytest(ctx["python"], work, tests, env, ctx["timeout"])
        green = result["exit_code"] == 0 and not result["timed_out"]
        env_fault = ENV_FAULT_RE.search(result["output"]) if not green else None
        summary = parse_summary(result["output"])
        if green and not summary.get("passed"):
            green = False
        out = {"status": "GREEN" if green else "BASELINE_RED", "exit_code": result["exit_code"],
               "seconds": result["seconds"], "tests": tests, "pytest_summary": summary,
               "import_probes": imports, "free_mb": free_mb(ctx["tmp_root"])}
        if env_fault:
            out["environment_fault"] = env_fault.group(0)
        if not green:
            out["output_tail"] = tail(result["output"], 40)
            out["failing_tests"] = parse_failures(result["output"])
        return out
    finally:
        if not ctx["keep"]:
            remove_tree(work)


def worktree_fingerprint(repo: Path, files: list[str]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for rel in sorted(set(files)):
        path = repo / rel
        out[rel] = sha256_bytes(path.read_bytes()) if path.is_file() else None
    return out


def fingerprint_scope(repo: Path, copy: list[str], watched: list[str], git_ok: bool) -> tuple[str, list[str]]:
    """Every git-tracked file in the repo (plus guard targets); without git,
    every file under the copied directories."""
    if git_ok:
        tracked = git_list(repo)
        if tracked is not None:
            return "git ls-files (all tracked files) + guard targets", sorted(set(tracked) | set(watched))
    found: set[str] = set(watched)
    for name in copy:
        base = repo / name
        if base.is_file():
            found.add(name)
        elif base.is_dir():
            for path in base.rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    found.add(path.relative_to(repo).as_posix())
    return "all files under copied dirs + guard targets (git unavailable)", sorted(found)


def digest_of(fingerprint: dict[str, str | None]) -> str:
    return sha256_bytes(json.dumps(fingerprint, sort_keys=True).encode("utf-8"))


def python_version(python: str) -> str | None:
    try:
        out = subprocess.run([python, "-c", "import sys,pytest;print(sys.version.split()[0], pytest.__version__)"],
                             capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    parts = out.stdout.decode().split()
    return f"CPython {parts[0]} / pytest {parts[1]}" if len(parts) == 2 else None


def execute(repo: Path, manifest_path: Path, python: str, only: list[str] | None, jobs: int,
            timeout: float, keep: bool, log=print, include_untracked: bool = False,
            probe_imports: bool | None = None,
            min_free_mb: int = DEFAULT_MIN_FREE_MB,
            confirm_mutant_runs: int = DEFAULT_CONFIRM_MUTANT_RUNS,
            confirm_baseline_runs: int = DEFAULT_CONFIRM_BASELINE_RUNS) -> tuple[int, dict[str, Any]]:
    if confirm_mutant_runs < 1 or confirm_baseline_runs < 1:
        raise ValueError("a kill must be reproduced at least once on the mutant and once on the baseline")
    manifest = load_manifest(manifest_path)
    guards = manifest["guards"]
    if only:
        unknown = sorted(set(only) - {g["id"] for g in guards})
        if unknown:
            raise ValueError(f"unknown guard id(s): {', '.join(unknown)}")
        guards = [g for g in guards if g["id"] in set(only)]
    git_ok = is_git_toplevel(repo)
    head = git(repo, "rev-parse", "HEAD") if git_ok else None
    copy = list(manifest.get("copy") or DEFAULT_COPY)
    dirty = git(repo, "status", "--porcelain", "--untracked-files=no", "--", *copy) if git_ok else None
    tracked = git_list(repo, "--", *copy) if git_ok else None
    untracked = git_list(repo, "--others", "--exclude-standard", "--", *copy) if git_ok else None
    if tracked is None or include_untracked:
        copy_files, copy_mode = None, ("worktree (tracked + untracked)" if tracked is not None
                                       else "worktree (git unavailable)")
    else:
        copy_files, copy_mode = tracked, "git-tracked files only (working-tree bytes)"
    if probe_imports is None:
        probe_imports = bool(manifest.get("import_probe", True))
    tmp_root = tempfile.gettempdir()
    ctx = {"repo": repo, "python": python, "head": head, "copy": copy, "files": copy_files,
           "timeout": timeout, "keep": keep, "tmp_root": tmp_root, "probe_imports": probe_imports,
           "import_roots": list(manifest.get("import_roots") or DEFAULT_IMPORT_ROOTS), "baseline_imports": {},
           "min_free_mb": min_free_mb, "confirm_mutant_runs": confirm_mutant_runs,
           "confirm_baseline_runs": confirm_baseline_runs}
    watched = [g["file"] for g in guards]
    scope_label, scope_files = fingerprint_scope(repo, copy, watched, git_ok)
    fingerprint_before = worktree_fingerprint(repo, scope_files)
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "generated_at": utc_now(),
        "honesty": "MEASURED",
        "signature_claimed": False,
        "repo": {"path": str(repo), "head_sha": head or "UNAVAILABLE",
                 "branch": (git(repo, "rev-parse", "--abbrev-ref", "HEAD") if git_ok else None) or "UNAVAILABLE",
                 "tracked_changes_in_copied_dirs": dirty.splitlines() if dirty else ([] if dirty == "" else "UNAVAILABLE"),
                 "untracked_in_copied_dirs": untracked if untracked is not None else "UNAVAILABLE",
                 "untracked_copied": bool(copy_files is None and untracked)},
        "runner": {"python": python, "version": python_version(python) or "UNAVAILABLE",
                   "command": "<python> -m pytest -q -p no:cacheprovider -x -rfE --basetemp=<tmp> <tests>",
                   "env": {"SENTRA_SIGNING_KEY": "<public CI fixture value; not recorded>",
                           "SZL_SOURCE_REVISION": head or "0" * 40,
                           "SZL_STATE_PATH": "<per-run temp sqlite>"},
                   "copied_dirs": copy, "copy_mode": copy_mode,
                   "files_copied": len(copy_files) if copy_files is not None else "ALL (directory copy)",
                   "import_probe": {"enabled": probe_imports, "import_roots": ctx["import_roots"]},
                   "kill_rule": ("pytest exit 1 AND >=1 test-level FAILED node id whose failure is not "
                                 "NameError/ImportError/ModuleNotFoundError/UnboundLocalError; mutants that "
                                 "fail to import (baseline imports OK) or cause collection errors are MUTANT_INVALID; "
                                 "the first killing node id must then fail alone on the mutant and pass alone on the "
                                 "unmutated copy every time (kill_confirmation), otherwise UNPROVEN_ERROR"),
                   "kill_confirmation": {"mutant_runs": confirm_mutant_runs,
                                         "baseline_runs": confirm_baseline_runs,
                                         "command": "<python> -m pytest -q -p no:cacheprovider -x -rfE "
                                                    "--basetemp=<tmp> <killing node id>",
                                         "state": "fresh SZL_STATE_PATH per rerun, same temp copy"},
                   "kill_kinds": ("assertion = assert / AssertionError / pytest.fail / pytest.raises DID NOT "
                                  "RAISE; exception:<Type> = the killing test crashed with an uncaught exception"),
                   "jobs": jobs, "timeout_seconds": timeout, "min_free_mb": min_free_mb,
                   "free_mb_at_start": free_mb(tmp_root)},
        "manifest": {"path": str(manifest_path), "sha256": sha256_bytes(manifest_path.read_bytes()),
                     "guards_declared": len(manifest["guards"]), "guards_selected": len(guards)},
        "worktree_check": {"scope": scope_label, "files_hashed": len(fingerprint_before),
                           "digest_before": digest_of(fingerprint_before)},
    }

    def _untouched() -> bool:
        after = worktree_fingerprint(repo, scope_files)
        receipt["worktree_check"]["digest_after"] = digest_of(after)
        changed = sorted(k for k in after if after[k] != fingerprint_before.get(k))
        receipt["worktree_check"]["changed_files"] = changed
        receipt["worktree_sha256"] = {k: after[k] for k in sorted(set(watched))}
        return not changed

    union: list[str] = []
    for g in guards:
        for t in g["tests"]:
            if t not in union:
                union.append(t)
    what = f"copy of {head}" if head else "copy (no git HEAD)"
    log(f"[guard-teeth] baseline: {len(union)} test target(s), unmutated {what}; copy_mode={copy_mode}")
    if untracked:
        log(f"[guard-teeth] untracked in copied dirs ({'COPIED' if copy_files is None else 'excluded'}): "
            f"{', '.join(untracked)}")
    baseline = run_baseline(union, ctx, watched)
    receipt["baseline"] = baseline
    log(f"[guard-teeth] baseline {baseline['status']} exit={baseline['exit_code']} "
        f"{baseline.get('pytest_summary')} in {baseline['seconds']}s; import probes "
        f"{ {k: v.get('state') for k, v in baseline.get('import_probes', {}).items()} }")
    if baseline["status"] != "GREEN":
        receipt["guards"] = []
        receipt["totals"] = {"guards": len(guards), "baseline": "BASELINE_RED"}
        receipt["verdict"] = "BASELINE_RED"
        receipt["worktree_untouched"] = _untouched()
        return 3, receipt

    def _line(r: dict[str, Any]) -> str:
        what = r.get("killing_tests", [])[:1] + ([f"[{r['kill_kind']}]"] if r.get("kill_kind") else [])
        if r["status"] != KILLED and r.get("kill_confirmation"):
            what.append(r["detail"])
        return f"[guard-teeth] {r['status']:<15} {r['id']}  ({r['seconds']}s) {' '.join(what)}"

    results: dict[str, dict[str, Any]] = {}
    if jobs <= 1:
        for g in guards:
            results[g["id"]] = run_guard(g, ctx)
            log(_line(results[g["id"]]))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(run_guard, g, ctx): g["id"] for g in guards}
            for fut in concurrent.futures.as_completed(futures):
                r = fut.result()
                results[r["id"]] = r
                log(_line(r))
    ordered = [results[g["id"]] for g in guards]
    receipt["guards"] = ordered
    totals: dict[str, int] = {"guards": len(ordered)}
    for status in ALL_STATUSES:
        totals[status.lower()] = sum(1 for r in ordered if r["status"] == status)
    killed = [r for r in ordered if r["status"] == KILLED]
    totals["killed_by_assertion"] = sum(1 for r in killed if r.get("kill_kind") == "assertion")
    totals["killed_by_exception"] = sum(1 for r in killed if str(r.get("kill_kind")).startswith("exception:"))
    totals["killed_kind_unknown"] = len(killed) - totals["killed_by_assertion"] - totals["killed_by_exception"]
    totals["kills_not_reproduced"] = sum(1 for r in ordered if r.get("kill_stable") is False)
    totals["temp_dirs_left_behind"] = sum(1 for r in ordered if r.get("temp_cleaned") is False)
    receipt["totals"] = totals
    # Kills where the test crashed instead of asserting the property: still kills,
    # listed so a reviewer can decide whether the test should assert it directly.
    receipt["exception_kills"] = [{"id": r["id"], "kill_kind": r["kill_kind"],
                                   "killing_test": r["killing_tests"][0],
                                   "reason": (r.get("kill_reasons") or [""])[0]}
                                  for r in killed if str(r.get("kill_kind")).startswith("exception:")]
    for item in receipt["exception_kills"]:
        log(f"[guard-teeth] exception kill (test crashed, did not assert): {item['id']} "
            f"{item['kill_kind']} via {item['killing_test']}")
    receipt["worktree_untouched"] = _untouched()
    if not receipt["worktree_untouched"]:
        receipt["verdict"] = "HARNESS_ERROR_WORKTREE_CHANGED"
        return 2, receipt
    proven = all(r["status"] == KILLED and r.get("kill_stable") is True
                 and any("::" in t for t in r.get("killing_tests", [])) for r in ordered)
    if totals["environment_fault"]:
        receipt["environment_fault_ids"] = [r["id"] for r in ordered if r["status"] == ENV_FAULT]
    if ordered and proven and totals["killed"] == len(ordered):
        # A --only subset proves only the guards it ran; it never reads as the whole manifest.
        whole = len(ordered) == receipt["manifest"]["guards_declared"]
        receipt["verdict"] = "ALL_GUARDS_KILLED" if whole else "SELECTED_GUARDS_KILLED"
        return 0, receipt
    if totals["survived"]:
        receipt["verdict"] = "SURVIVORS_FOUND"
        return 1, receipt
    receipt["verdict"] = "MANIFEST_OR_HARNESS_PROBLEM"
    return 2, receipt


def check_manifest(repo: Path, manifest_path: Path, only: list[str] | None) -> list[dict[str, Any]]:
    """Read-only staleness check of every selected guard: the find occurs exactly
    once, the mutant changes and compiles, and every listed test file exists."""
    manifest = load_manifest(manifest_path)
    unknown = sorted(set(only or []) - {g["id"] for g in manifest["guards"]})
    if unknown:
        raise ValueError(f"unknown guard id(s): {', '.join(unknown)}")
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="szl-guardteeth-dry-") as tmp:
        root = Path(tmp)
        for g in manifest["guards"]:
            if only and g["id"] not in only:
                continue
            src = repo / g["file"]
            dst = root / g["file"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                shutil.copy2(src, dst)
            facts = mutate(root, g)
            status, detail = facts.get("status", "READY"), facts.get("detail", "")
            missing = sorted({t.split("::", 1)[0] for t in g["tests"]
                              if not (repo / t.split("::", 1)[0]).is_file()})
            if missing:
                status = status if status != "READY" else STALE
                detail = "; ".join(x for x in (detail, f"listed test file(s) missing: {', '.join(missing)}") if x)
            rows.append({"id": g["id"], "status": status, "occurrences": facts.get("find_occurrences"),
                         "detail": detail})
            if dst.is_file():
                dst.unlink()
    return rows


def dry_run(repo: Path, manifest_path: Path, only: list[str] | None) -> int:
    """Check every guard against the working tree without running tests (read only)."""
    rows = check_manifest(repo, manifest_path, only)
    for row in rows:
        print(f"{row['status']:<15} {row['id']}  occurrences={row['occurrences']} {row['detail']}")
    bad = sum(1 for row in rows if row["status"] != "READY")
    print(f"[guard-teeth] dry-run: {len(rows) - bad}/{len(rows)} guard(s) READY; {bad} stale or invalid "
          f"(exit {2 if bad else 0})")
    return 2 if bad else 0


# --------------------------------------------------------------------- self-test
SELFTEST_SRC = (
    "def admit(value):\r\n"
    "    if value < 0:\r\n"
    "        raise ValueError('negative evidence weight')\r\n"
    "    return value\r\n"
    "\r\n"
    "\r\n"
    "def clamp(value):\r\n"
    "    if value > 10:\r\n"
    "        value = 10\r\n"
    "    return value\r\n"
    "\r\n"
    "\r\n"
    "def scale(value):\r\n"
    "    return value * 2\r\n"
    "\r\n"
    "\r\n"
    "def weight(record):\r\n"
    "    if 'weight' not in record:\r\n"
    "        return 0\r\n"
    "    return record['weight']\r\n"
)
SELFTEST_TEST = (
    "import sys\n"
    "from pathlib import Path\n"
    "import pytest\n"
    "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deploy'))\n"
    "from guarded import admit, clamp, scale, weight\n"
    "\n"
    "def test_admit_rejects_negative():\n"
    "    with pytest.raises(ValueError):\n"
    "        admit(-1)\n"
    "\n"
    "def test_clamp_passes_small_values():\n"
    "    assert clamp(3) == 3\n"
    "\n"
    "def test_leaves_read_only_file(tmp_path):\n"
    "    import os, stat\n"
    "    ro = tmp_path / 'read-only-object'\n"
    "    ro.write_text('x')\n"
    "    os.chmod(ro, stat.S_IREAD)\n"
    "\n"
    "def test_untracked_marker_not_copied():\n"
    "    assert not (Path(__file__).resolve().parents[1] / 'deploy' / 'untracked_marker.txt').exists()\n"
    "\n"
    "_ORDER = []\n"
    "\n"
    "def test_order_a_primes():\n"
    "    _ORDER.append('a')\n"
    "\n"
    "def test_order_b_only_checks_after_a():\n"
    "    if _ORDER:  # order-dependent: vacuous when this test runs alone\n"
    "        assert scale(2) == 4\n"
    "\n"
    "def test_weight_defaults_to_zero():\n"
    "    assert weight({}) == 0\n"
)


def self_test(python: str) -> int:
    """Prove the harness on a synthetic repo: one guard KILLED by an assertion and
    one by a crash (reproduced alone on mutant and baseline, the crash listed as
    an exception kill), one SURVIVED, an order-dependent kill that does not
    reproduce alone UNPROVEN_ERROR, stale and duplicate finds MANIFEST_STALE,
    non-compiling / import-breaking / name-binding mutants MUTANT_INVALID
    (never KILLED, never ALL_GUARDS_KILLED), untracked files excluded from the
    copy, a missing test file stale in --dry-run, a red baseline exit 3, and
    the source tree untouched."""
    checks: list[tuple[str, bool]] = []
    quiet = lambda *_: None  # noqa: E731
    with tempfile.TemporaryDirectory(prefix="szl-guardteeth-selftest-", ignore_cleanup_errors=True) as tmp:
        repo = Path(tmp) / "repo"
        (repo / "deploy").mkdir(parents=True)
        (repo / "tests").mkdir()
        (repo / "deploy" / "guarded.py").write_bytes(SELFTEST_SRC.encode())
        (repo / "tests" / "test_guarded.py").write_bytes(SELFTEST_TEST.encode())
        git_repo = subprocess.run(["git", "init", "-q", str(repo)], capture_output=True).returncode == 0 \
            and subprocess.run(["git", "-C", str(repo), "add", "deploy", "tests"],
                               capture_output=True).returncode == 0
        if git_repo:
            # Untracked file whose presence in a copy turns the baseline red.
            (repo / "deploy" / "untracked_marker.txt").write_text("must not be copied\n", encoding="utf-8")
        tests = ["tests/test_guarded.py"]
        manifest = {
            "schema": MANIFEST_SCHEMA, "copy": ["deploy", "tests"], "import_roots": ["deploy"],
            "guards": [
                {"id": "admit.rejects_negative", "file": "deploy/guarded.py",
                 "find": "    if value < 0:\n        raise ValueError('negative evidence weight')\n",
                 "replace": "", "why": "negative weights admitted", "tests": tests},
                {"id": "clamp.upper_bound", "file": "deploy/guarded.py",
                 "find": "    if value > 10:\n        value = 10\n",
                 "replace": "", "why": "unbounded values", "tests": tests},
                {"id": "stale.absent", "file": "deploy/guarded.py",
                 "find": "if value >= 0:", "replace": "if True:", "why": "stale", "tests": tests},
                {"id": "stale.duplicate", "file": "deploy/guarded.py",
                 "find": "    return value\n", "replace": "    return None\n", "why": "dup", "tests": tests},
                {"id": "invalid.syntax", "file": "deploy/guarded.py",
                 "find": "def clamp(value):", "replace": "def clamp(value:", "why": "bad", "tests": tests},
                {"id": "invalid.import_name", "file": "deploy/guarded.py",
                 "find": "def admit(value):", "replace": "from os import does_not_exist_probe\ndef admit(value):",
                 "why": "compiles but ImportError at import", "tests": tests},
                {"id": "invalid.module_nameerror", "file": "deploy/guarded.py",
                 "find": "def clamp(value):", "replace": "undefined_name_probe\ndef clamp(value):",
                 "why": "compiles but NameError at import", "tests": tests},
                {"id": "invalid.runtime_nameerror", "file": "deploy/guarded.py",
                 "find": "raise ValueError('negative evidence weight')",
                 "replace": "raise ValueErr('negative evidence weight')",
                 "why": "imports but NameError at call time", "tests": tests},
                {"id": "flaky.order_dependent_kill", "file": "deploy/guarded.py",
                 "find": "    return value * 2\n", "replace": "    return value * 3\n",
                 "why": "only an order-dependent test notices; it passes alone on the mutant", "tests": tests},
                {"id": "weight.crash_kill", "file": "deploy/guarded.py",
                 "find": "    if 'weight' not in record:\n        return 0\n", "replace": "",
                 "why": "the killing test crashes with KeyError instead of asserting", "tests": tests},
            ],
        }
        mpath = Path(tmp) / "manifest.json"
        mpath.write_text(json.dumps(manifest), encoding="utf-8")
        src_before = (repo / "deploy" / "guarded.py").read_bytes()
        code, receipt = execute(repo, mpath, python, None, 2, 120.0, False, log=quiet, min_free_mb=0)
        status = {g["id"]: g for g in receipt.get("guards", [])}
        st = lambda gid: status.get(gid, {}).get("status")  # noqa: E731
        checks.append(("baseline green", receipt["baseline"]["status"] == "GREEN"))
        checks.append(("baseline import probe OK", receipt["baseline"].get("import_probes", {})
                       .get("deploy/guarded.py", {}).get("state") == "OK"))
        checks.append(("guard killed", st("admit.rejects_negative") == KILLED))
        checks.append(("killer parsed", status.get("admit.rejects_negative", {}).get("killing_tests")
                       == ["tests/test_guarded.py::test_admit_rejects_negative"]))
        checks.append(("guard survived", st("clamp.upper_bound") == SURVIVED))
        checks.append(("absent find stale", st("stale.absent") == STALE))
        checks.append(("duplicate find stale", st("stale.duplicate") == STALE))
        checks.append(("non-compiling mutant invalid", st("invalid.syntax") == INVALID))
        checks.append(("ImportError mutant invalid, not killed", st("invalid.import_name") == INVALID
                       and status["invalid.import_name"].get("import_probe", {}).get("state") == "FAILED"
                       and status["invalid.import_name"].get("killing_tests") == []))
        checks.append(("module NameError mutant invalid, not killed", st("invalid.module_nameerror") == INVALID))
        checks.append(("runtime NameError mutant invalid, not killed", st("invalid.runtime_nameerror") == INVALID))
        checks.append(("totals.killed counts only real, reproduced kills", receipt["totals"].get("killed") == 2
                       and receipt["totals"].get("mutant_invalid") == 4
                       and receipt["totals"].get("unproven_error") == 1
                       and receipt["totals"].get("kills_not_reproduced") == 1))
        admit_rec = status.get("admit.rejects_negative", {})
        admit_conf = admit_rec.get("kill_confirmation", {})
        checks.append(("assertion kill reproduced alone: fails 2/2 on mutant, passes 3/3 on baseline",
                       admit_rec.get("kill_stable") is True and admit_rec.get("kill_kind") == "assertion"
                       and admit_conf.get("node") == "tests/test_guarded.py::test_admit_rejects_negative"
                       and admit_conf.get("mutant_failed") == 2 and admit_conf.get("baseline_passed") == 3
                       and [r["on"] for r in admit_conf.get("runs", [])] == ["mutant"] * 2 + ["baseline"] * 3))
        flaky_rec = status.get("flaky.order_dependent_kill", {})
        checks.append(("order-dependent kill that passes alone on the mutant is UNPROVEN_ERROR, not KILLED",
                       st("flaky.order_dependent_kill") == UNPROVEN and flaky_rec.get("kill_stable") is False
                       and flaky_rec.get("killing_tests") == [] and "kill_kind" not in flaky_rec
                       and flaky_rec.get("unconfirmed_killing_tests")
                       == ["tests/test_guarded.py::test_order_b_only_checks_after_a"]
                       and flaky_rec.get("kill_confirmation", {}).get("mutant_failed") == 0
                       and flaky_rec.get("kill_confirmation", {}).get("baseline_passed") == 0))
        crash_rec = status.get("weight.crash_kill", {})
        checks.append(("crash kill counted, kind exception:KeyError, listed apart from assertion kills",
                       st("weight.crash_kill") == KILLED and crash_rec.get("kill_stable") is True
                       and crash_rec.get("kill_kind") == "exception:KeyError"
                       and receipt["totals"].get("killed_by_exception") == 1
                       and receipt["totals"].get("killed_by_assertion") == 1
                       and receipt["totals"].get("killed_kind_unknown") == 0
                       and [e["id"] for e in receipt.get("exception_kills", [])] == ["weight.crash_kill"]))
        checks.append(("CRLF file matched", status.get("admit.rejects_negative", {}).get("eol") == "CRLF"))
        checks.append(("sha changed", status.get("admit.rejects_negative", {}).get("file_sha256_before")
                       != status.get("admit.rejects_negative", {}).get("file_sha256_after")))
        checks.append(("exit 1 with survivor", code == 1))
        checks.append(("source untouched", (repo / "deploy" / "guarded.py").read_bytes() == src_before
                       and receipt.get("worktree_untouched") is True
                       and receipt["worktree_check"]["files_hashed"] >= 2))
        if git_repo:
            checks.append(("untracked file excluded and listed",
                           receipt["repo"]["untracked_in_copied_dirs"] == ["deploy/untracked_marker.txt"]
                           and receipt["repo"]["untracked_copied"] is False
                           and receipt["runner"]["copy_mode"].startswith("git-tracked")))
        checks.append(("read-only temp files cleaned", receipt["totals"].get("temp_dirs_left_behind") == 0
                       and all(g.get("temp_cleaned") for g in receipt["guards"])))
        checks.append(("honesty fields", receipt["honesty"] == "MEASURED" and receipt["signature_claimed"] is False))
        code_only, receipt_only = execute(repo, mpath, python, ["admit.rejects_negative"], 1, 120.0, False,
                                          log=quiet, min_free_mb=0, confirm_mutant_runs=1,
                                          confirm_baseline_runs=1)
        checks.append(("--only subset exits 0 but never claims the whole manifest",
                       code_only == 0 and receipt_only["totals"]["killed"] == 1
                       and receipt_only["verdict"] == "SELECTED_GUARDS_KILLED"))
        code_fl, receipt_fl = execute(repo, mpath, python, ["flaky.order_dependent_kill"], 1, 120.0, False,
                                      log=quiet, min_free_mb=0)
        checks.append(("a kill that does not reproduce never yields a KILLED verdict",
                       code_fl == 2 and receipt_fl["verdict"] == "MANIFEST_OR_HARNESS_PROBLEM"
                       and receipt_fl["totals"]["killed"] == 0))
        code_bad, receipt_bad = execute(repo, mpath, python, ["invalid.import_name", "invalid.module_nameerror"],
                                        1, 120.0, False, log=quiet, min_free_mb=0)
        checks.append(("import-breaking mutants never yield ALL_GUARDS_KILLED",
                       code_bad == 2 and receipt_bad["verdict"] != "ALL_GUARDS_KILLED"
                       and receipt_bad["totals"]["killed"] == 0))
        code_np, receipt_np = execute(repo, mpath, python, ["invalid.import_name"], 1, 120.0, False,
                                      log=quiet, probe_imports=False, min_free_mb=0)
        np_rec = receipt_np["guards"][0] if receipt_np.get("guards") else {}
        checks.append(("without import probe, collection error is MUTANT_INVALID",
                       code_np == 2 and np_rec.get("status") == INVALID and np_rec.get("exit_code") == 2
                       and receipt_np["totals"]["killed"] == 0))
        fake = lambda code_, out: {"timed_out": False, "exit_code": code_, "output": out}  # noqa: E731
        checks.append(("classify: exit 1 without ids is UNPROVEN_ERROR",
                       classify(fake(1, "1 failed in 0.1s"))[0] == UNPROVEN))
        checks.append(("classify: setup ERROR only is UNPROVEN_ERROR",
                       classify(fake(1, "ERROR tests/t.py::test_a - RuntimeError: boom\n1 error in 0.1s"))[0]
                       == UNPROVEN))
        checks.append(("classify: file-level ERROR is MUTANT_INVALID",
                       classify(fake(2, "ERROR tests/t.py - ImportError: x\n1 error in 0.1s"))[0] == INVALID))
        checks.append(("classify: assertion failure is KILLED",
                       classify(fake(1, "FAILED tests/t.py::test_a - AssertionError: no\n1 failed"))
                       == (KILLED, ["tests/t.py::test_a"], "test-level assertion/behaviour failure")))
        checks.append(("classify: disk-full output is ENVIRONMENT_FAULT, not KILLED",
                       classify(fake(1, "FAILED tests/t.py::test_a - sqlite3.OperationalError: database or disk "
                                        "is full\n1 failed"))[0] == ENV_FAULT))
        checks.append(("classify: sqlite 'database is locked' is ENVIRONMENT_FAULT, not KILLED",
                       classify(fake(1, "FAILED tests/t.py::test_a - sqlite3.OperationalError: database is "
                                        "locked\n1 failed"))[0] == ENV_FAULT))
        checks.append(("kill_kind: assertion vs exception:<Type>",
                       [kill_kind(r) for r in ("assert 6 == 4", "AssertionError: no",
                                               "Failed: DID NOT RAISE <class 'ValueError'>", "KeyError: 'state'",
                                               "fastapi.exceptions.HTTPException: 409: stale", "")]
                       == ["assertion", "assertion", "assertion", "exception:KeyError",
                           "exception:HTTPException", "unknown"]))
        node = "tests/t.py::test_a"
        fail_out = {"timed_out": False, "exit_code": 1, "seconds": 0.1,
                    "output": f"FAILED {node} - AssertionError: no\n1 failed in 0.1s"}
        pass_out = {"timed_out": False, "exit_code": 0, "seconds": 0.1, "output": "1 passed in 0.1s"}

        def scripted(*outs: dict[str, Any]) -> Callable[[str], dict[str, Any]]:
            queue = list(outs)
            return lambda _node: queue.pop(0)
        restored: list[bool] = []

        def restore_ok() -> bool:
            restored.append(True)
            return True
        ok = confirm_kill(node, scripted(fail_out, fail_out, pass_out, pass_out, pass_out), restore_ok, 2, 3)
        checks.append(("confirm_kill: 2/2 mutant failures + 3/3 baseline passes is stable",
                       ok["stable"] is True and ok["mutant_failed"] == 2 and ok["baseline_passed"] == 3
                       and restored == [True]))
        restored.clear()
        once = confirm_kill(node, scripted(fail_out, pass_out), restore_ok, 2, 3)
        checks.append(("confirm_kill: mutant rerun that passes is unstable; baseline never run",
                       once["stable"] is False and once["mutant_failed"] == 1 and restored == []
                       and [r["on"] for r in once["runs"]] == ["mutant", "mutant"]))
        red_base = confirm_kill(node, scripted(fail_out, fail_out, pass_out, fail_out), restore_ok, 2, 3)
        checks.append(("confirm_kill: killer failing alone on the baseline is unstable",
                       red_base["stable"] is False and red_base["baseline_passed"] == 1
                       and "baseline rerun 2/3" in red_base["detail"]))
        binding = {"timed_out": False, "exit_code": 1, "seconds": 0.1,
                   "output": f"FAILED {node} - NameError: name 'x' is not defined\n1 failed"}
        checks.append(("confirm_kill: a rerun dying of NameError is not a reproduced kill",
                       confirm_kill(node, scripted(binding), restore_ok, 2, 3)["stable"] is False))
        other = {"timed_out": False, "exit_code": 1, "seconds": 0.1,
                 "output": "FAILED tests/t.py::test_other - AssertionError: no\n1 failed"}
        checks.append(("confirm_kill: a different test failing is not a reproduced kill",
                       confirm_kill(node, scripted(other), restore_ok, 2, 3)["stable"] is False))
        locked = {"timed_out": False, "exit_code": 1, "seconds": 0.1,
                  "output": f"FAILED {node} - sqlite3.OperationalError: database is locked\n1 failed"}
        env_conf = confirm_kill(node, scripted(fail_out, locked), restore_ok, 2, 3)
        checks.append(("confirm_kill: host fault in a rerun is flagged as environment_fault",
                       env_conf["stable"] is False and env_conf["environment_fault"] is True))
        checks.append(("confirm_kill: an unrestorable file is unstable",
                       confirm_kill(node, scripted(fail_out, fail_out), lambda: False, 2, 3)["stable"] is False))
        dry_manifest = json.loads(mpath.read_text(encoding="utf-8"))
        dry_manifest["guards"][0]["tests"] = tests + ["tests/test_renamed_away.py"]
        dry_path = Path(tmp) / "manifest-dry.json"
        dry_path.write_text(json.dumps(dry_manifest), encoding="utf-8")
        dry = {r["id"]: r for r in check_manifest(repo, dry_path, None)}
        checks.append(("dry-run: a listed test file that no longer exists is MANIFEST_STALE",
                       dry["admit.rejects_negative"]["status"] == STALE
                       and "tests/test_renamed_away.py" in dry["admit.rejects_negative"]["detail"]
                       and dry["clamp.upper_bound"]["status"] == "READY"
                       and dry["stale.absent"]["status"] == STALE))
        code_disk, receipt_disk = execute(repo, mpath, python, ["admit.rejects_negative"], 1, 120.0, False,
                                          log=quiet, min_free_mb=10 ** 12)
        checks.append(("low free disk gate: ENVIRONMENT_FAULT, never ALL_GUARDS_KILLED",
                       code_disk == 2 and receipt_disk["guards"][0]["status"] == ENV_FAULT
                       and receipt_disk["verdict"] != "ALL_GUARDS_KILLED"))
        (repo / "tests" / "test_guarded.py").write_bytes(
            (SELFTEST_TEST + "\ndef test_red():\n    assert False\n").encode())
        code_red, receipt_red = execute(repo, mpath, python, None, 1, 120.0, False, log=quiet, min_free_mb=0)
        checks.append(("red baseline exits 3", code_red == 3 and receipt_red["verdict"] == "BASELINE_RED"
                       and receipt_red["guards"] == []))
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f"[self-test] {'ok ' if ok else 'FAIL'} {name}")
    print(f"[self-test] {len(checks) - len(failed)}/{len(checks)} checks passed")
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", default=str(here.parents[1]), help="repo root (default: this file's repo)")
    parser.add_argument("--python", default=sys.executable, help="interpreter that has the test deps")
    parser.add_argument("--manifest", default=str(here.with_suffix(".json")))
    parser.add_argument("--only", action="append", help="guard id (repeatable or comma separated)")
    parser.add_argument("--json-out", help="write the receipt JSON here (default: stdout)")
    parser.add_argument("--jobs", type=int, default=1, help="parallel temp dirs (default 1)")
    parser.add_argument("--timeout", type=float, default=900.0, help="per pytest run, seconds")
    parser.add_argument("--keep", action="store_true", help="keep temp dirs for inspection")
    parser.add_argument("--dry-run", action="store_true", help="only check find/replace; run no tests")
    parser.add_argument("--self-test", action="store_true", help="prove the harness on a synthetic repo")
    parser.add_argument("--include-untracked", action="store_true",
                        help="also copy untracked files of the copied dirs (default: git-tracked only)")
    parser.add_argument("--min-free-mb", type=int, default=DEFAULT_MIN_FREE_MB,
                        help="refuse to run a guard (ENVIRONMENT_FAULT) below this much free temp disk")
    parser.add_argument("--no-import-probe", action="store_true",
                        help="skip the pre-pytest import probe (collection errors still count as MUTANT_INVALID)")
    parser.add_argument("--confirm-mutant-runs", type=int, default=DEFAULT_CONFIRM_MUTANT_RUNS,
                        help="times the killing test is re-run alone on the mutant; each must fail (min 1)")
    parser.add_argument("--confirm-baseline-runs", type=int, default=DEFAULT_CONFIRM_BASELINE_RUNS,
                        help="times the killing test is re-run alone on the unmutated copy; each must pass (min 1)")
    args = parser.parse_args(argv)
    if args.confirm_mutant_runs < 1 or args.confirm_baseline_runs < 1:
        parser.error("--confirm-mutant-runs and --confirm-baseline-runs must be at least 1")
    only = [x for item in (args.only or []) for x in item.split(",") if x] or None
    if args.self_test:
        return self_test(args.python)
    repo = Path(args.repo).resolve()
    manifest = Path(args.manifest).resolve()
    if args.dry_run:
        return dry_run(repo, manifest, only)
    code, receipt = execute(repo, manifest, args.python, only, max(1, args.jobs), args.timeout, args.keep,
                            log=lambda msg: print(msg, file=sys.stderr, flush=True),
                            include_untracked=args.include_untracked,
                            probe_imports=False if args.no_import_probe else None,
                            min_free_mb=args.min_free_mb, confirm_mutant_runs=args.confirm_mutant_runs,
                            confirm_baseline_runs=args.confirm_baseline_runs)
    blob = json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.json_out:
        Path(args.json_out).write_text(blob, encoding="utf-8", newline="\n")
        print(f"[guard-teeth] receipt written: {args.json_out}", file=sys.stderr)
    else:
        sys.stdout.write(blob)
    print(f"[guard-teeth] verdict={receipt.get('verdict')} totals={receipt.get('totals')} exit={code}",
          file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
