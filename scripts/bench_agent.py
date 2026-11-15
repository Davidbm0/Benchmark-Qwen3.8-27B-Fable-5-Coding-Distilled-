# bench_agent.py — testeaza bucla reala de agent: enunt + cod buggy -> model
# produce fisierele corectate -> verifier ruleaza -> daca pica, modelul vede
# eroarea si itereaza (max 3 runde). Timebox per runda = 300s.
#
# Ruleaza:  python bench_agent.py fable   |   python bench_agent.py flash
import json, os, re, shutil, subprocess, sys, time, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
TESTS = {
    "t1_binary_log": {"dir": "teste_fable/t1_binary_log",
                      "files": ["crc16.py", "frame.py", "log_reader.py", "demo.py"],
                      "budget": 400},
    "t2_jobqueue":   {"dir": "teste_fable/t2_jobqueue",
                      "files": ["jobs.py", "task_graph.py", "scheduler.py"],
                      "budget": 400},
}
SERVERS = {
    "fable27b":  {"base": "http://127.0.0.1:8083/v1", "model": "Qwen3.8-27B-Fable-5-Coding-Distilled"},
    "flashnext": {"base": "http://127.0.0.1:8080/v1", "model": "qwen3.8-flash-next-iq3_xxs"},
}
MAX_ROUNDS = 3

def ask(server, messages, max_tokens=8000):
    body = json.dumps({"model": server["model"], "messages": messages,
                       "max_tokens": max_tokens, "temperature": 0.2}).encode()
    req = urllib.request.Request(server["base"] + "/chat/completions",
                                 data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    r = json.loads(urllib.request.urlopen(req, timeout=900).read())
    msg = r["choices"][0]["message"]
    text = (msg.get("reasoning_content") or "") + "\n" + (msg.get("content") or "")
    return text, time.time() - t0

FENCE = re.compile(r"```([a-zA-Z]*)\n(.*?)\n```", re.S)

def extract_files(answer, allowed):
    """dintr-un raspuns, ia ultimele blocuri de cod care par fisiere permise.
    Un bloc e 'fisier' daca prima linie contine numele fisierului (comment/docstring)."""
    found = {}
    for lang, code in FENCE.findall(answer):
        if lang in ("diff", "text", "") and not code.strip().startswith(("import", "from", '"')):
            continue
        first = code.strip().splitlines()[0] if code.strip() else ""
        for f in allowed:
            stem = f[:-3]
            if f in first or stem in first or (not first.strip().startswith(("import", "from")) and f in code[:200]):
                # pastreaza cel mai mare bloc per fisier (fix harness anterior)
                if len(code) > len(found.get(f, "")):
                    found[f] = code
    return found

def run_verifier(workdir):
    p = subprocess.run([sys.executable, "test_verifier.py"], cwd=workdir,
                       capture_output=True, text=True, timeout=120)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode == 0, out[-2500:]

def prep_workdir(test_dir, files):
    wd = os.path.join(BASE, "_agent_wd")
    shutil.rmtree(wd, ignore_errors=True)
    os.makedirs(wd)
    for f in files:
        shutil.copy(os.path.join(test_dir, f), wd)
    shutil.copy(os.path.join(test_dir, "test_verifier.py"), wd)
    shutil.copy(os.path.join(test_dir, "enunt.txt"), wd)
    return wd

def run_test(server, tid, spec):
    test_dir = os.path.join(BASE, spec["dir"])
    wd = prep_workdir(test_dir, spec["files"])
    enunt = open(os.path.join(wd, "enunt.txt"), encoding="utf-8").read()
    srcs = {f: open(os.path.join(wd, f), encoding="utf-8").read() for f in spec["files"]}

    sysmsg = ("You are a coding agent. You are given buggy source files and a task statement. "
              "Fix the bugs. Output ONLY the complete fixed content of each file you change, "
              "each in its own fenced code block, with the filename as the first line of the block "
              "(e.g. '# crc16.py'). Do not output diffs. Do not change the public API. "
              "You will see the hidden test output after each attempt.")
    user1 = enunt + "\n\n=== FILES ===\n" + "\n\n".join(f"--- {f} ---\n{c}" for f, c in srcs.items())

    messages = [{"role": "system", "content": sysmsg}, {"role": "user", "content": user1}]
    t_total = 0.0
    for rnd in range(1, MAX_ROUNDS + 1):
        if t_total > spec["budget"]:
            return {"ok": False, "t": round(t_total, 1), "rounds": rnd - 1, "note": "budget"}
        try:
            ans, dt = ask(server, messages)
        except Exception as e:
            return {"ok": False, "t": round(t_total, 1), "rounds": rnd, "note": f"HTTP {e}"}
        t_total += dt
        got = extract_files(ans, spec["files"])
        if not got:
            messages.append({"role": "assistant", "content": ans[-4000:]})
            messages.append({"role": "user", "content": "No valid file blocks found. Output each fixed file in a fenced code block starting with its filename."})
            continue
        for f, code in got.items():
            open(os.path.join(wd, f), "w", encoding="utf-8").write(code)
        ok, out = run_verifier(wd)
        if ok:
            return {"ok": True, "t": round(t_total, 1), "rounds": rnd}
        messages.append({"role": "assistant", "content": ans[-4000:]})
        messages.append({"role": "user", "content": f"Tests still FAIL. Verifier output:\n\n{out}\n\nFix the remaining bugs and output the complete fixed files again."})
    return {"ok": False, "t": round(t_total, 1), "rounds": MAX_ROUNDS}

def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "fable"
    key = "fable27b" if which == "fable" else "flashnext"
    server = SERVERS[key]
    try:
        urllib.request.urlopen(server["base"].replace("/v1", "/health"), timeout=5).read()
    except Exception as e:
        print(f"server {key} nu e health: {e}"); sys.exit(1)
    results = []
    for tid, spec in TESTS.items():
        r = run_test(server, tid, spec)
        results.append({"id": tid, key: r})
        print(json.dumps({"id": tid, key: r}))
    tot = sum(r[key]["t"] for r in results)
    okn = sum(1 for r in results if r[key]["ok"])
    print(f"\n=== {key}: {okn}/{len(TESTS)} in {tot:.0f}s ===")
    json.dump(results, open(os.path.join(BASE, f"agent_{key}.json"), "w"), indent=1)
    print("Salvat: agent_" + key + ".json")

if __name__ == "__main__":
    main()
