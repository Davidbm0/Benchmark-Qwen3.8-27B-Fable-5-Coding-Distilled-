# Qwen3.8-27B-Fable-5-Coding-Distilled — local benchmark on one RTX 5080

Benchmark of **Qwen3.8-27B-Fable-5-Coding-Distilled** (GGUF, Q3_K_M, llama.cpp, ctx 16k, full offload on RTX 5080 16 GB) against **Qwen3.8-Flash-Next** (IQ3_XXS, same GPU, served on port 8080). Fable distill runs on port 8083. Only one model is kept on the GPU at a time; runners include watchdogs that unload/kill the other model so timings are not contaminated.

## Models

| | Fable Distill | Flash-Next |
|---|---|---|
| File | `Qwen3.8-27B-Fable-5-Coding-Distilled.i1-Q3_K_M.gguf` | `qwen3.8-flash-next` IQ3_XXS |
| Base | Qwen3.8-27B, distilled on Fable 5 coding/debugging traces | Qwen3.8 Flash-Next |
| Quant | Q3_K_M (~14 GB VRAM) | IQ3_XXS |

## Test suites

1. **Phase 1 — engineering one-shot** (`bench_engineering.py`): 5 problems (propagation delay, impedance, ISR, CSV parsing, crosstalk diagnosis), verifier-checked.
2. **Extreme — hard coding, 1200 s timebox** (`bench_extreme.py`): 4 problems (Dijkstra, microstrip calculator, TX engine, PDN), self-repair loop, max 4 attempts.
3. **Argon suite — agentic debugging** (`bench_argon.py`): 3 fixtures with a real tool loop (`read_file`, `run_cmd`, `edit_file`, `list_files`), 1200 s / 14 turns:
   - T1: bash `[ ]` quoting bug in a CI deploy script (stderr must be empty)
   - T2: float rounding in a billing cent calculation (naive float gives 254 instead of 255)
   - T3: defective test harness — the source is correct, the mock is wrong (root-cause test)
4. **Hard Argon suite** (`bench_argon_hard.py`): 3 harder fixtures, 20 turns, anti-cheat scoring (verifiers + hidden tests re-run after the model finishes; editing `verify.py` = automatic fail):
   - H1: multi-file inventory service — mutable default arg, off-by-one pagination, cent truncation; hidden tests catch special-casing
   - H2: `JobQueue` check-then-act race under 8 threads (30 trials x 200 jobs; baseline loses/duplicates ~1400 jobs)
   - H3: misleading `KeyError` behind a retry decorator; root cause is a config indirection; hidden checks reject band-aid fixes
5. **Agent loop bench** (`bench_agent.py`): 2 debugging tasks, 3 rounds of tool feedback.

## Results (all runs on RTX 5080, warm model, one model on GPU)

| Suite | Fable Distill Q3_K_M | Flash-Next IQ3_XXS |
|---|---|---|
| Phase 1 (5 problems) | 5/5 in 687 s | 5/5 in 326 s |
| Extreme (4 problems, 1200 s) | 3/4 in 2620 s | 2/4 in 1185 s |
| Argon easy (3 fixtures) | 3/3 in 234 s | 3/3 in 326 s |
| Argon hard (3 fixtures) | 3/3 in 532 s | 3/3 in 486 s |
| Agent loop (2 tasks) | 1/2 in 1059 s | 0/2 in 653 s |

Hard-suite detail (verified from run diffs, `results/argon_hard_*.json`):

- **H1**: Flash fixed with `Decimal` + `ROUND_HALF_EVEN` + `tags=None` (stronger fix); Fable only `int()` -> `round()` (passes, keeps float arithmetic). Both preserved the pinned label format.
- **H2**: Flash rewrote with an atomic `_claim()` under a lock + `_EMPTY` sentinel; Fable added a lock around the check-then-act. Both pass 30/30 trials.
- **H3**: both found the root cause in `config.py` (`CONFIG[name]` -> `SERVICE_TABLE[CONFIG[name]]`), neither touched `verify.py`/`hidden_checks.py`. Flash was 3x faster (32 s vs 99 s).
- Hallucinated tool calls: Flash invented `run_file` twice (rejected by harness); Fable 0 errors.

## Verdict

- Correctness: tie on both Argon suites (3/3). Fable wins the extreme self-repair suite (3/4 vs 2/4) and the agent loop.
- Speed: Flash-Next is faster overall (486 s vs 532 s hard suite; 326 s vs 687 s phase 1) and produced higher-quality fixes on H1/H2.
- Discipline: Fable uses fewer turns (8-10 vs 12-16), zero tool errors, deeper reasoning; Flash occasionally invents tools.
- The most interesting result: a much smaller, more aggressively quantized model (Flash-Next IQ3_XXS) keeps pace with a 27B Q3_K_M distill on agentic debugging.

## Methodology notes

- Same fixtures, same tools, same 1200 s timebox for both models; temperature 0.2.
- Runners (`scripts/run_*.py`) stop the other model before each run (unload API / kill llama-server) and warm the target model twice.
- Anti-cheat: scorers diff the fixture against the run copy; modifying `verify.py` or hidden tests = automatic fail.
- Harness bugs found and fixed during the campaign (documented in commit history): WSL `/usr/bin/bash` alias vs Git Bash on Windows, 406 KB traceback flooding the context, orphaned subprocesses on timeout.

## Layout

```
scripts/    bench + runner scripts
fixtures/   argon_tests/  T1-T3 + H1-H3 fixtures (defective on purpose)
results/    JSON results for both models
```

To reproduce: serve a model (llama.cpp, `-ngl 99`), point `ARGON_SERVER` / `ARGON_MODEL` at it, run `python scripts/bench_argon.py` or `bench_argon_hard.py`.
