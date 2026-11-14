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

3 fixtures with a real tool loop (`read_file`, `run_cmd`, `edit_file`, `list_files`), 1200 s / 14 turns:

- T1: bash `[ ]` quoting bug in a CI deploy script (stderr must be empty)
- T2: float rounding in a billing cent calculation (naive float gives 254 instead of 255)
- T3: defective test harness — the source is correct, the mock is wrong (root-cause test)

| Model | Score | Total time |
|---|---|---|
| Fable Distill Q3_K_M | 3/3 | 234 s |
| Flash-Next IQ3_XXS | 3/3 | 326 s |

Tie on correctness. Fable is more turn-disciplined on T1 (6 turns, calls `done`); Flash produced the stronger T2 fix (`Decimal` + `ROUND_HALF_EVEN` vs `int()` -> `round()`). Both passed the T3 harness trap (left the correct source untouched, fixed the mock).

Reproduce: `python scripts/bench_argon.py` (env: `ARGON_SERVER`, `ARGON_MODEL`)

Hard agentic suite and agent-loop bench to follow.
