# Runner suita grea. Mod: fable | flash
# fable: asigura ca Fable e pe 8083, unload Flash, watchdog anti-Flash
# flash: opreste Fable (kill llama-server 8083), warm Flash, watchdog anti-Fable
import json, os, subprocess, sys, time, urllib.request, threading

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
MODE = sys.argv[1] if len(sys.argv) > 1 else "fable"
stop_flag = threading.Event()

def log(m): print(m, flush=True)

def port_alive(port):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=4).read()
        return True
    except Exception:
        return False

def unload_flash():
    try:
        req = urllib.request.Request("http://127.0.0.1:8080/unload", data=b"{}",
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).read()
        return True
    except Exception as e:
        log(f"[watchdog] unload flash esuat: {e}"); return False

def kill_fable_server():
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | "
            "Where-Object { $_.CommandLine -match '8083' } | Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=30)
        for pid in [int(x) for x in out.stdout.split()]:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=30)
            log(f"[watchdog] am oprit llama-server pid {pid} (Fable 8083)")
    except Exception as e:
        log(f"[watchdog] kill fable esuat: {e}")

def watchdog():
    while not stop_flag.is_set():
        time.sleep(45)
        if stop_flag.is_set():
            break
        if MODE == "fable":
            try:
                if json.loads(urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=4).read()).get("loaded"):
                    log("[watchdog] Flash incarcat -> unload")
                    unload_flash()
            except Exception:
                pass
        else:
            if port_alive(8083):
                log("[watchdog] Fable inapoi pe GPU -> il opresc")
                kill_fable_server()

if MODE == "fable":
    if not port_alive(8083):
        log("PREFLIGHT ESUAT: Fable (8083) nu raspunde. Porneste llama-server inainte.")
        sys.exit(2)
    unload_flash()
    time.sleep(8)
    target_port, target_model = 8083, "Qwen3.8-27B-Fable-5-Coding-Distilled"
    out_file, run_prefix = "argon_hard_fable.json", "_run_hard_fable"
else:
    if port_alive(8083):
        kill_fable_server()
        time.sleep(8)
    target_port, target_model = 8080, "qwen3.8-flash-next-iq3_xxs"
    out_file, run_prefix = "argon_hard_flash.json", "_run_hard_flash"

body = json.dumps({"model": target_model,
                   "messages": [{"role": "user", "content": "Raspunde scurt: warm"}],
                   "max_tokens": 300}).encode()
for i in range(2):
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{target_port}/v1/chat/completions",
                                     data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=300).read()
        log(f"[runner] warm {i+1} OK")
    except Exception as e:
        log(f"[runner] warm {i+1} esuat: {e}")

threading.Thread(target=watchdog, daemon=True).start()
log(f"[runner] watchdog pornit (mod={MODE})")

env = dict(os.environ,
           ARGON_SERVER=f"http://127.0.0.1:{target_port}/v1",
           ARGON_MODEL=target_model,
           ARGON_OUT=out_file,
           ARGON_RUN_PREFIX=run_prefix)
p = subprocess.run([sys.executable, "bench_argon_hard.py"], capture_output=True, text=True,
                   timeout=5400, env=env)
stop_flag.set()
log(p.stdout[-5000:] if p.stdout else "(stdout gol)")
if p.returncode != 0:
    log(f"[runner] EXIT {p.returncode}; stderr: {p.stderr[-1500:]}")
log("[runner] DONE")
