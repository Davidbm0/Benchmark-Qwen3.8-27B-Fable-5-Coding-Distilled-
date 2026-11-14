# Runner argon-suite: unload Flash, warm Fable, watchdog anti-Flash, bench_argon.py
import json, os, subprocess, sys, time, urllib.request, threading

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
stop_flag = threading.Event()

def log(m): print(m, flush=True)

def flash_loaded():
    try:
        return json.loads(urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=5).read()).get("loaded", False)
    except Exception:
        return False

def unload_flash():
    try:
        req = urllib.request.Request("http://127.0.0.1:8080/unload", data=b"{}",
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).read()
        return True
    except Exception as e:
        log(f"[watchdog] unload esuat: {e}"); return False

def watchdog():
    while not stop_flag.is_set():
        time.sleep(45)
        if not stop_flag.is_set() and flash_loaded():
            log("[watchdog] Flash incarcat -> unload")
            unload_flash()

log("[runner] sleep 90s (astept reload model pe GPU)")
time.sleep(90)
unload_flash()
time.sleep(10)

body = json.dumps({"model": "Qwen3.8-27B-Fable-5-Coding-Distilled",
                   "messages": [{"role": "user", "content": "Raspunde scurt: warm"}],
                   "max_tokens": 300}).encode()
for i in range(2):
    try:
        req = urllib.request.Request("http://127.0.0.1:8083/v1/chat/completions",
                                     data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=300).read()
        log(f"[runner] warm {i+1} OK")
    except Exception as e:
        log(f"[runner] warm {i+1} esuat: {e}")

threading.Thread(target=watchdog, daemon=True).start()
log("[runner] watchdog pornit")

p = subprocess.run([sys.executable, "bench_argon.py"], capture_output=True, text=True, timeout=5400)
stop_flag.set()
log(p.stdout[-5000:] if p.stdout else "(stdout gol)")
if p.returncode != 0:
    log(f"[runner] EXIT {p.returncode}; stderr: {p.stderr[-1500:]}")
log("[runner] DONE")
