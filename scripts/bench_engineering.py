# Bench Qwen3.8-27B-UD (Q3_K_XL) vs Qwen3.8-Flash-Next — time-boxed, 5 probleme ingineresti
# Mod: python bench_engineering.py
#
# Regula: buget de timp egal per problema — al doilea model are la fel de mult timp
# cat a folosit primul pe aceeasi problema, cu self-repair iterativ in buget.
#
# Inainte de rulare:
#   - Flash-Next pe 8080 (deja e, ruleaza prin Strata)
#   - Fable-27B importat in Strata si incarcat pe un port (ex. 8083) — vezi SERVERS mai jos
#   - Atentie: Fable ~15 GB VRAM + KV => Strata trebuie sa descarce Flash-Next pt bench.

import json, re, time, urllib.request

SERVERS = {
    "flashnext": {"base": "http://127.0.0.1:8080/v1", "model": "qwen3.8-flash-next"},
    "fable27b":  {"base": "http://127.0.0.1:8083/v1", "model": "Qwen3.8-27B-UD-Q3_K_XL"},
}
TIMEBOX_CAP = 600          # secunde max per problema per model
MAX_ATTEMPTS = 3           # self-repair: max 3 incercari in buget

def floats(text):
    return [float(x) for x in re.findall(r"\d+\.?\d*", text.replace(",", "."))]

def near(text, target, tol=0.15):
    return any(abs(v - target) <= target * tol for v in floats(text))

# ------------------------------------------------------------------
# 5 probleme ingineresti (SI/PCB, embedded, SerDes, cod, diagnosticare)
# Verificarea = keyword structural + valoare numerica cu toleranta.
# ------------------------------------------------------------------
PROBLEMS = [
    ("si1_delay",
     "Urmeaza strict regula 50 Ohm single-ended. Un urma PCB pe FR4 (er eficient 4.3) are lungimea 10 cm. "
     "Calculeaza delay-ul de propagare in ns (t_pd = 333 ps/cm / sqrt(er_eff)). Arata calculul pas cu pas.",
     lambda r: near(r, 1.61, 0.12) and "ns" in r.lower()),

    ("si2_impedance",
     "Microstrip pe stratul de sus: FR4 er=4.3, grosime dielectric h=1.6 mm, latime urma w=0.3 mm. "
     "Aproxima impedanta caracteristica cu formula microstrip Z0 = (87/sqrt(er+1.41))*ln(5.87h/w). "
     "Spune valoarea in Ohmi si daca e OK pentru un semnal single-ended de 3.3V.",
     lambda r: near(r, 125, 0.15) and "ohm" in r.lower()),

    ("emb1_isr",
     "In C embedded, un flag global setat intr-un ISR (signal handler) nu e vazut de bucla principala "
     "cu -O2. Care e cauza si care e fix-ul exact? Da codul corectat, minimal, fara explicatii lungi.",
     lambda r: "volatile" in r and "static" in r.lower()),

    ("cod_csv",
     "Scrie o functie Python care citeste un CSV cu coloanele pret,data si calculeaza media mobila pe 7 zile, "
     "fara pandas, sortand dupa data. Doar cod, fara explicatii.",
     lambda r: "def " in r and "csv" in r.lower() and ("7" in r or "deque" in r.lower())),

    ("diag_crosstalk",
     "Doua urme paralele pe acelasi strat, lungime paralela 5 cm, spacing 0.2 mm, crosstalk măsurat prea mare. "
     "Propune exact 3 masuri de corectie, fiecare cu mecanismul fizic (nu liste vagi). "
     "Include si distanta minima recomandata spacing/sau crosstalk control (regula 3W sau echivalent).",
     lambda r: ("3w" in r.lower() or "spacing" in r.lower()) and
               ("ground" in r.lower() or "gnd" in r.lower() or "return" in r.lower() or "twisted" in r.lower() or "guard" in r.lower()) and
               len(re.findall(r"\d[\.\)]", r)) >= 3),
]

def ask(server, prompt, max_tokens=8000):
    body = json.dumps({
        "model": server["model"], "max_tokens": max_tokens, "temperature": 0.3,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(server["base"] + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        d = json.loads(resp.read())
    msg = d["choices"][0]["message"]
    # Strata intoarce reasoning in 'reasoning_content' si poate lasa content None
    # daca bugetul de tokeni s-a epuizat in reasoning.
    text = (msg.get("content") or "") + "\n" + (msg.get("reasoning_content") or "")
    return text, time.time() - t0

import sys

def preflight(arm):
    srv = SERVERS[arm]
    try:
        urllib.request.urlopen(srv["base"].replace("/v1", "") + "/health", timeout=10).read()
    except Exception as e:
        print(f"PREFLIGHT ESUAT: {arm} ({srv['base']}) nu raspunde: {e}")
        print("Nu masuram nimic — porneste serverul si reia.")
        return False
    return True

def run_phase(arm, budget_file=None):
    """2 faze: Flash (8080) si Fable (8083) nu incap pe 5080 deodata.
    Faza 1 masoara Flash + bugetele; faza 2 masoara Fable cu timpul facut de Flash."""
    if not preflight(arm):
        return
    saved = {}
    if budget_file:
        try:
            rows = json.load(open(budget_file))
            saved = {r["id"]: r["flashnext"]["t"] for r in rows
                     if r.get("flashnext", {}).get("ok") and r["flashnext"].get("t", 0) > 5}
        except Exception:
            print(f"Nu gasesc {budget_file} — rulez cu bugetul fix {TIMEBOX_CAP}")
    results = []
    for pid, prompt0, check in PROBLEMS:
        row = {"id": pid}
        srv = SERVERS[arm]
        budget = saved.get(pid, TIMEBOX_CAP) if budget_file else TIMEBOX_CAP
        budget = min(budget, TIMEBOX_CAP)
        t_total, ok, attempts = 0.0, False, 0
        t_start = time.time()
        cur_prompt = prompt0
        while attempts < MAX_ATTEMPTS and time.time() - t_start < budget:
            attempts += 1
            try:
                ans, dt = ask(srv, cur_prompt)
                t_total += dt
                ok = check(ans)
                if ok:
                    break
                cur_prompt = prompt0 + "\n\n(Raspunsul anterior NU a trecut verificarea. Reia si corecteaza.)"
            except Exception as e:
                t_total = time.time() - t_start
                row["err"] = str(e)[:80]
                break
        row[arm] = {"ok": ok, "t": round(t_total, 1), "attempts": attempts}
        results.append(row)
        print(json.dumps(row))
    print(f"\n=== {arm}: {sum(1 for r in results if r[arm]['ok'])}/5 ===")
    out = "phase_flash.json" if arm == "flashnext" else "phase_fable.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Salvat: {out}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "flash":
        run_phase("flashnext")
    elif mode == "fable":
        run_phase("fable27b", budget_file="phase_flash.json")
    else:
        print("Folosire (2 faze, pe rand pe 5080):")
        print("  1) python bench_engineering.py flash   (Fable NU trebuie sa fie pornit)")
        print("  2) swap: /unload 8080 + Fable pe 8083, apoi python bench_engineering.py fable")
