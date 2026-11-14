# Runner argon-suite pentru Qwen Flash: opreste serverul Fable (eliberare GPU),
# warm Flash, watchdog anti-Fable, ruleaza bench_argon.py impotriva 8080.
import json, os, signal, subprocess, sys, time, urllib.request, threading

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
stop_flag = threading.Event()

def log(m): print(m, flush=True)

def fable_loaded():
    try:
        urllib.request.urlopen("http://127.0.0.1:8083/health", timeout=4).read()
        return True
    except Exception:
        return False

def kill_fable_server():
    # gaseste pid-ul llama-server cu port 8083 si opreste-l
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | "
            "Where-Object { $_.CommandLine -match '8083' } | Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=30)
        pids = [int(x) for x in out.stdout.split()]
        for pid in pids:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=30)
            log(f"[runner] am oprit llama-server pid {pid} (Fable 8083)")
        return bool(pids)
    except Exception as e:
        log(f"[runner] kill fable esuat: {e}")
        return False

def watchdog():
    while not stop_flag.is_set():
        time.sleep(45)
        if not stop_flag.is_set() and fable_loaded():
            log("[watchdog] Fable incarcat inapoi pe GPU -> il opresc")
            kill_fable_server()

if fable_loaded():
    kill_fable_server()
    time.sleep(8)
log(f"[runner] fable_loaded acum = {fable_loaded()}")

body = json.dumps({"model": "qwen3.8-flash-next-iq3_xxs",
                   "messages": [{"role": "user", "content": "Raspunde scurt: warm"}],
                   "max_tokens": 300}).encode()
for i in range(2):
    try:
        req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                                     data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=300).read()
        log(f"[runner] warm flash {i+1} OK")
    except Exception as e:
        log(f"[runner] warm flash {i+1} esuat: {e}")

threading.Thread(target=watchdog, daemon=True).start()
log("[runner] watchdog pornit (anti-Fable)")

env = dict(os.environ,
           ARGON_SERVER="http://127.0.0.1:8080/v1",
           ARGON_MODEL="qwen3.8-flash-next-iq3_xxs",
           ARGON_OUT="argon_flash.json",
           ARGON_RUN_PREFIX="_run_flash")
p = subprocess.run([sys.executable, "bench_argon.py"], capture_output=True, text=True,
                   timeout=5400, env=env)
stop_flag.set()
log(p.stdout[-5000:] if p.stdout else "(stdout gol)")
if p.returncode != 0:
    log(f"[runner] EXIT {p.returncode}; stderr: {p.stderr[-1500:]}")
log("[runner] DONE")
