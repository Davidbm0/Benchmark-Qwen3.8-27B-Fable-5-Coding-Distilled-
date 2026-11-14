# Suita grea (H1-H3): bug multi-fișier + testuri ascunse, race condition, traceback inselator.
# Foloseste bucla de agent din bench_argon.py; scorers separate cu anti-cheat (verify.py nu poate fi modificat).

import json, os, subprocess, sys

import bench_argon as ba

BASE = ba.BASE
OUTFILE = os.environ.get("ARGON_OUT", "argon_hard_fable.json")
RUN_PREFIX = os.environ.get("ARGON_RUN_PREFIX", "_run_hard")

ba.MAX_TURNS = int(os.environ.get("ARGON_MAX_TURNS", "20"))


def _verify(proj):
    try:
        r = subprocess.run([sys.executable, "verify.py"], cwd=proj, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return False, "verify.py TIMEOUT (180s)"
    out = r.stdout + r.stderr
    if len(out) > 4000:
        out = out[:2000] + "...[truncated]..." + out[-2000:]
    return "TEST PASS" in r.stdout, out


def _verify_untouched(proj, orig):
    return proj_orig(proj, orig) == orig["verify.py"]

def proj_orig(proj, orig):
    p = os.path.join(proj, "verify.py")
    return open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""


def score_h1(proj, orig):
    ok, out = _verify(proj)
    cheat = not _verify_untouched(proj, orig)
    api = open(os.path.join(proj, "inventory/api.py"), encoding="utf-8").read()
    pinned = '"body"' in api and '"count"' in api and '"total_cents"' in api
    why = ("verify.py MODIFICAT (cheat)" if cheat else
           f"verify={'PASS' if ok else 'FAIL'} pinned={'ok' if pinned else 'BROKEN'}")
    return {"ok": ok and pinned and not cheat, "why": why}


def score_h2(proj, orig):
    ok, out = _verify(proj)
    cheat = not _verify_untouched(proj, orig)
    q = open(os.path.join(proj, "queue.py"), encoding="utf-8").read()
    has_sync = ("Lock" in q) or ("queue" in q.lower() and "import queue" in q) or ("deque" in q)
    why = ("verify.py MODIFICAT (cheat)" if cheat else
           f"verify={'PASS' if ok else 'FAIL'} sync={'da' if has_sync else 'indiciu: fara lock/queue'}")
    return {"ok": ok and not cheat, "why": why}


def score_h3(proj, orig):
    ok, out = _verify(proj)
    cheat = not _verify_untouched(proj, orig) or not _hc_untouched(proj, orig)
    why = ("verify/hidden_checks MODIFICATE (cheat)" if cheat else
           f"verify+hidden={'PASS' if ok else 'FAIL'}")
    return {"ok": ok and not cheat, "why": why}

def _hc_untouched(proj, orig):
    p = os.path.join(proj, "hidden_checks.py")
    return (open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else "") == orig["hidden_checks.py"]


H1 = """CI is red on our inventory service. The failing harness is `verify.py` (run: python verify.py). Its output:

```
CI FAIL:
 - paginate(items,1,3) -> ['n3','n4','n5'], expected ['n0','n1','n2']
 - tag leak: b.tags=['x']
 - total_cents(3x1.00, 15%) -> 254, expected 255
```

There may be more than one root cause, in more than one file. Inspect the whole project before editing.
IMPORTANT constraints:
- The dict keys returned by handle() in inventory/api.py ("body", "count", "total_cents") are consumed by a legacy parser - do not change them.
- Do NOT modify verify.py - it is the CI harness. Fix the source code only.
Apply the fixes with edit_file, then verify with `python verify.py`."""

H2 = """Our nightly batch runner intermittently processes jobs twice or crashes with IndexError under load. It passes when run single-threaded but fails in CI which runs 8 workers.

Project files: queue.py (the queue implementation) and verify.py (CI harness, run: python verify.py - it runs 30 trials).

Reproduce the failure first, find the real root cause, then fix it. Do NOT modify verify.py. Do not just catch the exception - fix the underlying defect. Verify with `python verify.py`."""

H3 = """Our job runner crashes in CI with:

```
KeyError: 'backup_service'
```

The traceback points into runner.py (the retry helper). Project files: runner.py, config.py, verify.py (run: python verify.py).

Careful: the exception being raised is not necessarily where the bug is. Inspect all files, reproduce, find the root cause, and fix it properly. Do NOT modify verify.py or hidden_checks.py. Verify with `python verify.py`."""

if __name__ == "__main__":
    only = os.environ.get("ARGON_ONLY", "")
    results = []
    for name, prompt, fx, scorer in [
        ("h1_inventory", H1, os.path.join(BASE, "argon_tests/h1_inventory"), score_h1),
        ("h2_race", H2, os.path.join(BASE, "argon_tests/h2_race"), score_h2),
        ("h3_traceback", H3, os.path.join(BASE, "argon_tests/h3_traceback"), score_h3),
    ]:
        if only and only not in name:
            continue
        print(f"=== {name} ===", flush=True)
        r = ba.run_test(name, prompt, fx, scorer)
        r["test"] = name
        results.append(r)
        print(json.dumps(r), flush=True)
    n_ok = sum(1 for r in results if r["ok"])
    print(f"\n=== {ba.MODEL} HARD suite: {n_ok}/3 in {sum(r['t'] for r in results):.0f}s ===")
    json.dump(results, open(os.path.join(BASE, OUTFILE), "w"), indent=2)
    print(f"Salvat: {OUTFILE}")
