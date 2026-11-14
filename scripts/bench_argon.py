# Bench "Argon Suite" — teste de agentic debugging (anti-speculatie, chirurgie in cod,
# root-cause in test harness) pentru Qwen3.8-27B-Fable-5-Coding-Distilled pe 8083.
# Modelul primeste tool-uri reale: list_files / read_file / run_cmd / edit_file / done.
# Scoring: verify extern + disciplina (citit inainte de edit, patch chirurgical, halucinatiuni).

import json, os, re, shutil, subprocess, sys, time, urllib.request

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures")
SERVER = os.environ.get("ARGON_SERVER", "http://127.0.0.1:8083/v1")
MODEL = os.environ.get("ARGON_MODEL", "Qwen3.8-27B-Fable-5-Coding-Distilled")
OUTFILE = os.environ.get("ARGON_OUT", "argon_fable.json")
RUN_PREFIX = os.environ.get("ARGON_RUN_PREFIX", "_run")
BASH_EXE = os.environ.get("ARGON_BASH", "bash")
TIMEBOX = 1200          # secunde / test
MAX_TURNS = int(os.environ.get("ARGON_MAX_TURNS", "20"))
MAX_TOKENS_TURN = 6000

TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List all files in the project (relative paths).",
     "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file. Returns numbered lines.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "run_cmd", "description": "Run a shell command in the project dir (bash/python). 30s limit.",
     "parameters": {"type": "object", "properties": {"cmd": {"type": "string"}}, "required": ["cmd"]}}},
    {"type": "function", "function": {"name": "edit_file", "description": "Replace EXACT text old->new in a file (old must appear verbatim, exactly once).",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}}, "required": ["path", "old", "new"]}}},
    {"type": "function", "function": {"name": "done", "description": "Call when the task is finished. Include a 1-2 sentence summary.",
     "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}}},
]

SYSTEM = (
    "You are an autonomous coding agent with real tools. You operate on a real project directory.\n"
    "Rules:\n"
    "- Inspect before acting: use list_files/read_file/run_cmd BEFORE proposing or applying any edit.\n"
    "- Make surgical edits: change only the lines that are actually wrong. Do not rewrite files.\n"
    "- Respect pinned constraints stated by the user (exact output strings, dict keys, signatures).\n"
    "- If the real bug is in the test harness rather than the source, say so and fix the harness, not the source.\n"
    "- When finished, call the done tool with a short summary.\n"
    "Call exactly one tool per response, as a JSON object: {\"tool\": \"name\", \"args\": {...}}. "
    "You may include brief reasoning text before the JSON. Never invent file contents — read them."
)

def call_model(messages):
    body = json.dumps({"model": MODEL, "messages": messages, "tools": TOOLS,
                       "max_tokens": MAX_TOKENS_TURN, "temperature": 0.2}).encode()
    req = urllib.request.Request(SERVER + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    for attempt in range(2):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=300).read())
            break
        except Exception:
            if attempt == 1:
                raise
            time.sleep(5)
    ch = d["choices"][0]
    msg = ch["message"]
    native = None
    for tc in (msg.get("tool_calls") or []):
        fn = tc.get("function", {})
        try:
            native = {"tool": fn.get("name"), "args": json.loads(fn.get("arguments") or "{}")}
            break
        except Exception:
            continue
    return msg.get("content") or "", msg.get("reasoning_content") or "", native

def parse_tool_call(text):
    # find last JSON object with "tool" key
    best = None
    for m in re.finditer(r"\{[\s\S]*?\}\s*$|\{\"tool\"[\s\S]*?\}(?=\s*$|\s*\{)", text):
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict) and "tool" in obj:
                best = obj
        except Exception:
            # try progressive brace matching
            depth = 0
            for i, c in enumerate(m.group(0)):
                if c == "{": depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = json.loads(m.group(0)[:i+1])
                            if isinstance(obj, dict) and "tool" in obj:
                                best = obj
                        except Exception:
                            pass
                        break
    if best is None:
        # fallback: scan whole text for a balanced {...} containing "tool"
        idx = text.rfind('{"tool"')
        if idx == -1: idx = text.rfind('{ "tool"')
        if idx >= 0:
            depth = 0
            for i in range(idx, len(text)):
                if text[i] == "{": depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = json.loads(text[idx:i+1])
                            if isinstance(obj, dict) and "tool" in obj:
                                best = obj
                        except Exception:
                            pass
                        break
    return best

def exec_tool(proj, call):
    name = call["tool"]; args = call.get("args", {}) or {}
    if name == "list_files":
        out = []
        for root, dirs, files in os.walk(proj):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for f in files:
                out.append(os.path.relpath(os.path.join(root, f), proj).replace("\\", "/"))
        return "\n".join(sorted(out)) or "(empty)"
    if name == "read_file":
        p = os.path.join(proj, args.get("path", ""))
        if not os.path.isfile(p):
            return f"ERROR: file not found: {args.get('path')}"
        lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
        return "\n".join(f"{i+1:4d}| {l}" for i, l in enumerate(lines))
    if name == "run_cmd":
        try:
            p = subprocess.Popen([BASH_EXE, "-c", args.get("cmd", "")], cwd=proj,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 stdin=subprocess.DEVNULL)
            try:
                out_b, err_b = p.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"],
                               capture_output=True, timeout=20)
                try:
                    out_b, err_b = p.communicate(timeout=10)
                except Exception:
                    out_b, err_b = "", ""
                return "ERROR: command timed out (60s), killed"
            out = (out_b or "") + (("\n[stderr]\n" + err_b) if err_b else "")
            if len(out) > 6000:
                out = out[:3000] + f"\n...[{len(out)} chars total, TRUNCATED]...\n" + out[-3000:]
            return out + f"\n[exit {p.returncode}]"
        except Exception as e:
            return f"ERROR: run_cmd failed: {e}"
    if name == "edit_file":
        p = os.path.join(proj, args.get("path", ""))
        if not os.path.isfile(p):
            return f"ERROR: file not found: {args.get('path')}"
        src = open(p, encoding="utf-8").read()
        old, new = args.get("old", ""), args.get("new", "")
        if old not in src:
            return "ERROR: 'old' text not found verbatim in file. Read the file and copy the exact text."
        if src.count(old) > 1:
            return "ERROR: 'old' text appears more than once; provide more context to make it unique."
        open(p, "w", encoding="utf-8").write(src.replace(old, new, 1))
        return "EDIT APPLIED."
    if name == "done":
        return None
    return f"ERROR: unknown tool '{name}'"

def run_test(name, user_prompt, fixture_dir, scorer):
    proj = os.path.join(BASE, f"{RUN_PREFIX}_{name}")
    if os.path.isdir(proj): shutil.rmtree(proj)
    shutil.copytree(fixture_dir, proj)
    orig = {}
    for root, _, files in os.walk(proj):
        for f in files:
            p = os.path.join(root, f)
            orig[os.path.relpath(p, proj).replace("\\", "/")] = open(p, encoding="utf-8", errors="replace").read()

    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_prompt}]
    t0 = time.time()
    reads, edits, hallucinations, tool_calls, done_called = 0, 0, 0, 0, False
    edited_files, reasoning_chars = set(), 0
    last_err = ""
    for turn in range(MAX_TURNS):
        if time.time() - t0 > TIMEBOX:
            last_err = "timebox"
            break
        try:
            content, reasoning, native = call_model(messages)
        except Exception as e:
            last_err = f"server error: {e}"
            break
        reasoning_chars += len(reasoning)
        call = native or parse_tool_call(content)
        if native:
            messages.append({"role": "assistant", "content": content,
                             "tool_calls": [{"id": "call_0", "type": "function",
                                             "function": {"name": native["tool"],
                                                          "arguments": json.dumps(native.get("args", {}))}}]})
        else:
            messages.append({"role": "assistant", "content": content})
        if call is None:
            messages.append({"role": "user", "content": "No valid tool call found. Reply with exactly one tool call JSON: {\"tool\": ..., \"args\": ...} or call done."})
            continue
        tool_calls += 1
        tool = call["tool"]
        if tool == "done":
            done_called = True
            break
        if tool == "read_file" or tool == "list_files":
            reads += 1
            if tool == "read_file" and not os.path.isfile(os.path.join(proj, call.get("args", {}).get("path", ""))):
                hallucinations += 1
        if tool == "edit_file":
            if reads == 0:
                hallucinations += 1  # edit without ever reading/listing = speculation
            edits += 1
            edited_files.add(call.get("args", {}).get("path", ""))
        result = exec_tool(proj, call)
        if result is not None:
            if result.startswith("ERROR"): last_err = result
            if native:
                messages.append({"role": "tool", "tool_call_id": "call_0", "content": result})
            else:
                messages.append({"role": "user", "content": f"[tool {tool} result]\n{result}"})
    elapsed = time.time() - t0

    # diff discipline
    changed = []
    for rel, before in orig.items():
        p = os.path.join(proj, rel)
        after = open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
        if after != before:
            changed.append(rel)
    score = scorer(proj, orig)
    return {"test": name, "ok": score["ok"], "why": score.get("why", ""),
            "t": round(elapsed, 1), "turns": tool_calls, "reads": reads, "edits": edits,
            "edited_files": sorted(edited_files), "changed_files": sorted(changed),
            "hallucinations": hallucinations, "done_called": done_called,
            "reasoning_chars": reasoning_chars, "last_err": last_err[:200]}

# ---------------- scorers ----------------
def score_t1(proj, orig):
    r = subprocess.run([BASH_EXE, "tests/test_deploy.sh"], cwd=proj, capture_output=True, text=True, timeout=60)
    ok = "TEST PASS" in r.stdout
    dep = open(os.path.join(proj, "scripts/deploy.sh"), encoding="utf-8").read()
    pinned_ok = (dep.count('echo "$LOG_PREFIX') >= 30 and 'DEPLOY OK env=$DEPLOY_ENV' in dep
                 and 'LOG_PREFIX="[deploy]"' in dep)
    return {"ok": ok and pinned_ok, "why": f"harness={'PASS' if ok else 'FAIL'} pinned={'ok' if pinned_ok else 'BROKEN'}"}

def score_t2(proj, orig):
    r = subprocess.run([sys.executable, "verify.py"], cwd=proj, capture_output=True, text=True, timeout=60)
    ok = "TEST PASS" in r.stdout
    return {"ok": ok, "why": (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout+r.stderr).strip() else "no output"}

def score_t3(proj, orig):
    src_now = open(os.path.join(proj, "src/config.py"), encoding="utf-8").read()
    src_untouched = src_now == orig["src/config.py"]
    r = subprocess.run([sys.executable, "tests/test_config.py"], cwd=proj, capture_output=True, text=True, timeout=60)
    test_ok = "TEST PASS" in r.stdout
    # corect = harness fixat SAU explicat, cu sursa atinsa
    return {"ok": src_untouched and test_ok, "why": f"src_untouched={src_untouched} test={'PASS' if test_ok else 'FAIL'}"}

# ---------------- prompts ----------------
T1 = """Our GitHub Actions CI pipeline is failing at the `deploy-check` step with the following error:

```
./scripts/deploy.sh: line 42: [: too many arguments
Error: Expected exit code 0, got 2 in tests/test_deploy.bats
```

Fix the bug so the CI passes. IMPORTANT: Do not alter the exact stdout log format because our monitoring parser depends on the pinned output strings (every `[deploy] ...` line and the final `DEPLOY OK env=...` line). The test harness `tests/test_deploy.sh` is runnable via run_cmd: `bash tests/test_deploy.sh`."""

T2 = """Here is a legacy Python function used in our billing pipeline, along with its failing test output.

File `billing/processor.py` exists in this project. The failing test harness is `verify.py` (run it with: python verify.py). Its output:

```
AssertionError: format_invoice_line("Widget", 3, 1.00, discount_pct=15)
Expected net_cents: 255, Got: 254
  Note: Tax compliance rule requires half-to-even (banker's rounding) at the cent level.
```

Propose and APPLY the minimal diff to fix `billing/processor.py` without breaking downstream compatibility: do not change the function signature, the return type, or the dict keys ("raw_label", "net_cents", "flags"). Verify with `python verify.py`."""

T3 = """A developer complains:

"My implementation of `parse_config()` in `src/config.py` works locally when I run the app, but it fails in CI with FileNotFoundError on defaults.ini. I think the fix is to make parse_config() search absolute paths like /etc/defaults.ini. Please fix src/config.py."

Before editing any code, inspect the project: read src/config.py, src/defaults.ini, tests/test_config.py, and run `python tests/test_config.py` to reproduce. Then do whatever is actually correct — which may mean NOT touching src/config.py if the real bug is elsewhere. Explain your root cause in the done summary."""

if __name__ == "__main__":
    results = []
    for name, prompt, fx, scorer in [
        ("t1_ci_debug", T1, os.path.join(BASE, "argon_tests/t1_ci_debug"), score_t1),
        ("t2_billing", T2, os.path.join(BASE, "argon_tests/t2_billing"), score_t2),
        ("t3_harness", T3, os.path.join(BASE, "argon_tests/t3_harness"), score_t3),
    ]:
        print(f"=== {name} ===", flush=True)
        r = run_test(name, prompt, fx, scorer)
        results.append(r)
        print(json.dumps(r), flush=True)
        # cleanup run dir but keep for inspection
    n_ok = sum(1 for r in results if r["ok"])
    print(f"\n=== {MODEL} argon-suite: {n_ok}/3 in {sum(r['t'] for r in results):.0f}s ===")
    json.dump(results, open(os.path.join(BASE, OUTFILE), "w"), indent=2)
    print(f"Salvat: {OUTFILE}")
