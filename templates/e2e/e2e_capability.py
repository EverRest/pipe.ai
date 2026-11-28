"""Playwright wrapper for an exec capability. Stdlib only.

Use: python3 e2e_capability.py /abs/path/e2e.json   (the owner writes this file)
stdin: {"goal", "task", "payload": {"env"?, "filter"?}}. stdout: one JSON result.
It runs the tests of the owner's local checkout against a deployed environment.
It never checks out or builds a branch.
Exit 0: `done`, or `failed` for failed tests. Non-zero: bad setup or input; no tests result.
"""

import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

CLI = "node_modules/@playwright/test/cli.js"
NAME = re.compile(r"[a-z0-9-]{1,32}")
# a test file filter: starts with a letter or digit, so never an option or an absolute path
FILTER = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,99}")
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# ponytail: pattern-based redaction; it cannot know every secret, and not those in screenshots
SECRET = re.compile(
    r"xox[a-z]-\S+|xapp-\S+|glpat-\S+|eyJ[\w-]+\.[\w-]+\.[\w-]+"
    r"|(?:Bearer|Basic)\s+\S+|(?<=://)[^/\s]+@"
    r"|(?:authorization|cookie|password|passwd|secret|token|api[_-]?key)[\"']?\s*[:=]\s*[^\n]+",
    re.I,
)
LOG_TAIL = 200_000
MAX_SHOTS = 5
MAX_FILE = 10 * 1024 * 1024
NOTE = (
    "Tests: the owner's local checkout. Target: the deployed environment.\n"
    "No branch was checked out. A change is tested only after its branch is deployed there.\n"
)


def scrub(s):
    return SECRET.sub("[redacted]", ANSI.sub("", s))


def check_url(u):
    p = urlparse(u) if isinstance(u, str) else None
    local = p and p.scheme == "http" and p.hostname in ("localhost", "127.0.0.1")
    return bool(p and (p.scheme == "https" or local) and p.hostname and "@" not in p.netloc)


def check_config(c):
    """An error sentence for a bad owner file, else None."""
    if not isinstance(c, dict):
        return "the owner file must be a JSON object"
    for k in ("checkout", "node"):
        if not (isinstance(c.get(k), str) and os.path.isabs(c[k])):
            return f"{k} must be an absolute path"
    envs = c.get("envs")
    if not (isinstance(envs, dict) and envs):
        return "envs must be a non-empty object of name to URL"
    if not all(NAME.fullmatch(n) and check_url(u) for n, u in envs.items()):
        return "envs: a name is [a-z0-9-], a URL is https (http for localhost), no user name"
    if c.get("default_env") not in envs:
        return "default_env must be a name in envs"
    t = c.get("timeout_s", 540)
    if not (isinstance(t, int) and t > 0):
        return "timeout_s must be a positive integer"
    return None


def runner(argv, env, cwd, timeout, log_path):
    with open(log_path, "wb") as log:
        p = subprocess.Popen(  # noqa: S603 (argv list, no shell)
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            return p.wait(timeout)
        finally:
            if p.poll() is None:  # timeout: stop the workers and browsers too
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()


def run(inp, cfg, run_dir, run_cmd=runner, environ=os.environ):
    """Return (exit_code, result dict). `run_dir` is the directory for the output files."""
    stop = lambda rc, text: (rc, {"text": text})  # noqa: E731
    if err := check_config(cfg):
        return stop(2, err)
    payload = inp.get("payload") if isinstance(inp, dict) else None
    payload = payload if isinstance(payload, dict) else {}
    name = payload.get("env", cfg["default_env"])
    if not (isinstance(name, str) and name in cfg["envs"]):
        return stop(2, "env is not in the allowlist")
    flt = payload.get("filter")
    if flt is not None and not (isinstance(flt, str) and FILTER.fullmatch(flt) and ".." not in flt):
        return stop(2, "filter must be a relative test file path [A-Za-z0-9_./-]")
    cli = Path(cfg["checkout"], CLI)
    if not cli.is_file():
        return stop(2, "Playwright is not installed in the checkout")
    run_dir = Path(run_dir).resolve()
    out_dir, log = run_dir / "test-results", run_dir / "playwright.log"
    argv = [cfg["node"], str(cli), "test", "--reporter=line", f"--output={out_dir}"]
    argv += [flt] if flt else []
    env = {
        "HOME": environ.get("HOME", ""),
        "PATH": f"{os.path.dirname(cfg['node'])}:/usr/bin:/bin",
        "BASE_URL": cfg["envs"][name],
        "CI": "1",
    }
    try:
        rc = run_cmd(argv, env, cfg["checkout"], cfg.get("timeout_s", 540), log)
        data = log.read_bytes()[-LOG_TAIL:]
    except subprocess.TimeoutExpired:
        return stop(1, "the test run timed out")
    except OSError as e:
        return stop(1, f"the test run did not start: {type(e).__name__}")
    finally:
        log.unlink(missing_ok=True)  # the raw log is not redacted
    if rc not in (0, 1):  # Playwright: 0 passed, 1 failed
        return stop(1, f"Playwright stopped with code {rc}")
    status, word = ("done", "passed") if rc == 0 else ("failed", "failed")
    head = f"E2E tests {word}. Environment: {name}. Filter: {flt or 'none'}.\n{NOTE}"
    body = scrub(data.decode(errors="replace"))
    (run_dir / "report.txt").write_text(f"{head}\n{body}")
    shots = [
        str(f.relative_to(run_dir))
        for f in sorted(out_dir.rglob("*.png"))
        if not f.is_symlink() and f.stat().st_size <= MAX_FILE
    ]
    text = f"{head}\n{body[-1500:]}"
    return 0, {"status": status, "text": text, "files": ["report.txt", *shots[:MAX_SHOTS]]}


def main(argv, run_cmd=runner):
    try:
        cfg = json.loads(Path(argv[0]).read_text())
        inp = json.load(sys.stdin)
    except (IndexError, OSError, ValueError) as e:
        rc, out = 2, {"text": f"cannot read the owner file or the input: {type(e).__name__}"}
    else:
        rc, out = run(inp, cfg, Path.cwd(), run_cmd)
    if rc:
        print(out["text"], file=sys.stderr)
    print(json.dumps(out))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
