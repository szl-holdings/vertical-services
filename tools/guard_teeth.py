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
from typing import Any

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
ENV_FAULT_RE = re.compile(r"database or disk is full|No space left on device|ENOSPC|"
                          r"not enough space on the disk|disk quota exceeded|MemoryError", re.I)
DEFAULT_MIN_FREE_MB = 1024


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
        after_mb = free_mb(ctx["tmp_root"])
        record.update({"free_mb_before": before_mb, "free_mb_after": after_mb})
        if status in (KILLED, UNPROVEN, INVALID) and 0 <= after_mb < ctx["min_free_mb"]:
            status, failing, detail = ENV_FAULT, [], (f"free disk fell to {after_mb} MB during the run "
                                                      f"(< {ctx['min_free_mb']} MB); failure not attributable")
        record.update({"status": status, "killing_tests": failing if status == KILLED else [],
                       "exit_code": result["exit_code"], "pytest_seconds": result["seconds"],
                       "pytest_summary": parse_summary(result["output"]), "detail": detail})
        if status == KILLED:
            record["kill_kind"] = "test_failure"
            record["kill_reasons"] = [n["reason"][:240] for n in parse_nodes(result["output"])
                                      if n["id"] in failing]
        else:
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
            min_free_mb: int = DEFAULT_MIN_FREE_MB) -> tuple[int, dict[str, Any]]:
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
           "min_free_mb": min_free_mb}
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
                                 "fail to import (baseline imports OK) or cause collection errors are MUTANT_INVALID"),
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

    results: dict[str, dict[str, Any]] = {}
    if jobs <= 1:
        for g in guards:
            results[g["id"]] = run_guard(g, ctx)
            r = results[g["id"]]
            log(f"[guard-teeth] {r['status']:<15} {g['id']}  ({r['seconds']}s) {', '.join(r.get('killing_tests', [])[:1])}")
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(run_guard, g, ctx): g["id"] for g in guards}
            for fut in concurrent.futures.as_completed(futures):
                r = fut.result()
                results[r["id"]] = r
                log(f"[guard-teeth] {r['status']:<15} {r['id']}  ({r['seconds']}s) {', '.join(r.get('killing_tests', [])[:1])}")
    ordered = [results[g["id"]] for g in guards]
    receipt["guards"] = ordered
    totals: dict[str, int] = {"guards": len(ordered)}
    for status in ALL_STATUSES:
        totals[status.lower()] = sum(1 for r in ordered if r["status"] == status)
    totals["temp_dirs_left_behind"] = sum(1 for r in ordered if r.get("temp_cleaned") is False)
    receipt["totals"] = totals
    receipt["worktree_untouched"] = _untouched()
    if not receipt["worktree_untouched"]:
        receipt["verdict"] = "HARNESS_ERROR_WORKTREE_CHANGED"
        return 2, receipt
    proven = all(r["status"] == KILLED and r.get("kill_kind") == "test_failure"
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


def dry_run(repo: Path, manifest_path: Path, only: list[str] | None) -> int:
    """Check every find/replace against the working tree without running tests (read only)."""
    manifest = load_manifest(manifest_path)
    bad = 0
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
            status = facts.get("status", "READY")
            bad += status != "READY"
            print(f"{status:<15} {g['id']}  occurrences={facts.get('find_occurrences')} {facts.get('detail', '')}")
            if dst.is_file():
                dst.unlink()
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
)
SELFTEST_TEST = (
    "import sys\n"
    "from pathlib import Path\n"
    "import pytest\n"
    "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deploy'))\n"
    "from guarded import admit, clamp\n"
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
)


def self_test(python: str) -> int:
    """Prove the harness on a synthetic repo: one guard KILLED, one SURVIVED,
    stale and duplicate finds MANIFEST_STALE, non-compiling / import-breaking /
    name-binding mutants MUTANT_INVALID (never KILLED, never ALL_GUARDS_KILLED),
    untracked files excluded from the copy, a red baseline exit 3, and the
    source tree untouched."""
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
        checks.append(("totals.killed counts only real kills", receipt["totals"].get("killed") == 1
                       and receipt["totals"].get("mutant_invalid") == 4))
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
                                          log=quiet, min_free_mb=0)
        checks.append(("--only subset exits 0 but never claims the whole manifest",
                       code_only == 0 and receipt_only["totals"]["killed"] == 1
                       and receipt_only["verdict"] == "SELECTED_GUARDS_KILLED"))
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
    args = parser.parse_args(argv)
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
                            min_free_mb=args.min_free_mb)
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
