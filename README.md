# Qwen3.8-27B-Fable-5-Coding-Distilled — local benchmark on one RTX 5080

Benchmark of **Qwen3.8-27B-Fable-5-Coding-Distilled** (GGUF, Q3_K_M, llama.cpp, ctx 16k, full offload on RTX 5080 16 GB) against **Qwen3.8-Flash-Next** (IQ3_XXS, same GPU, port 8080). Fable distill runs on port 8083. Only one model is kept on the GPU at a time; runners include watchdogs that unload/kill the other model so timings are not contaminated.

## Models

| | Fable Distill | Flash-Next |
|---|---|---|
| File | `Qwen3.8-27B-Fable-5-Coding-Distilled.i1-Q3_K_M.gguf` | `qwen3.8-flash-next` IQ3_XXS |
| Base | Qwen3.8-27B, distilled on Fable 5 coding/debugging traces | Qwen3.8 Flash-Next |
| Quant | Q3_K_M (~14 GB VRAM) | IQ3_XXS |

## Suite 1 — Phase 1: engineering one-shot

5 verifier-checked problems (propagation delay, impedance, ISR, CSV parsing, crosstalk).

| Model | Score | Total time |
|---|---|---|
| Fable Distill Q3_K_M | 5/5 | 687 s |
| Flash-Next IQ3_XXS | 5/5 | 326 s |

## Suite 2 — Extreme: hard coding, 1200 s timebox

4 problems (Dijkstra, microstrip calculator, TX engine, PDN), self-repair loop, max 4 attempts.

| Model | Score | Total time |
|---|---|---|
| Fable Distill Q3_K_M | 3/4 | 2620 s |
| Flash-Next IQ3_XXS | 2/4 | 1185 s |

## Suite 3 — Argon suite: agentic debugging (easy)

3 fixtures with a real tool loop (`read_file`, `run_cmd`, `edit_file`, `list_files`), 1200 s / 14 turns: T1 bash quoting bug, T2 billing cent rounding, T3 defective-harness root-cause test.

| Model | Score | Total time |
|---|---|---|
| Fable Distill Q3_K_M | 3/3 | 234 s |
| Flash-Next IQ3_XXS | 3/3 | 326 s |

## Suite 4 — Hard Argon suite

3 harder fixtures, 20 turns, anti-cheat scoring (verifiers + hidden tests re-run after the model finishes; editing `verify.py` = automatic fail):

- H1: multi-file inventory service — mutable default arg, off-by-one pagination, cent truncation; hidden tests catch special-casing
- H2: `JobQueue` check-then-act race under 8 threads (30 trials x 200 jobs; baseline loses/duplicates ~1400 jobs)
- H3: misleading `KeyError` behind a retry decorator; root cause is a config indirection; hidden checks reject band-aid fixes

| Model | Score | Total time |
|---|---|---|
| Fable Distill Q3_K_M | 3/3 | 532 s |
| Flash-Next IQ3_XXS | 3/3 | 486 s |

Hard-suite detail (verified from run diffs in `results/argon_hard_*.json`):

- **H1**: Flash fixed with `Decimal` + `ROUND_HALF_EVEN` + `tags=None` (stronger fix); Fable only `int()` -> `round()` (passes, keeps float arithmetic). Both preserved the pinned label format.
- **H2**: Flash rewrote with an atomic `_claim()` under a lock + `_EMPTY` sentinel; Fable added a lock around the check-then-act. Both pass 30/30 trials.
- **H3**: both found the root cause in `config.py` (`CONFIG[name]` -> `SERVICE_TABLE[CONFIG[name]]`), neither touched `verify.py`/`hidden_checks.py`. Flash was 3x faster (32 s vs 99 s).
- Hallucinated tool calls: Flash invented `run_file` twice (rejected by harness); Fable 0 errors.

Reproduce: `python scripts/bench_argon.py` / `bench_argon_hard.py` (env: `ARGON_SERVER`, `ARGON_MODEL`)

Agent-loop bench to follow.
