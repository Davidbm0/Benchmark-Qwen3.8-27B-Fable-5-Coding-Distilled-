# Qwen3.8-27B-Fable-5-Coding-Distilled — local benchmark on one RTX 5080

Benchmark of **Qwen3.8-27B-Fable-5-Coding-Distilled** (GGUF, Q3_K_M, llama.cpp, ctx 16k, full offload on RTX 5080 16 GB) against **Qwen3.8-Flash-Next** (IQ3_XXS, same GPU, port 8080). Fable distill runs on port 8083. Only one model is kept on the GPU at a time; runners include watchdogs that unload/kill the other model so timings are not contaminated.

## Models

| | Fable Distill | Flash-Next |
|---|---|---|
| File | `Qwen3.8-27B-Fable-5-Coding-Distilled.i1-Q3_K_M.gguf` | `qwen3.8-flash-next` IQ3_XXS |
| Base | Qwen3.8-27B, distilled on Fable 5 coding/debugging traces | Qwen3.8 Flash-Next |
| Quant | Q3_K_M (~14 GB VRAM) | IQ3_XXS |

## Suite 1 — Phase 1: engineering one-shot

5 problems checked by verifiers: propagation delay, impedance, ISR handling, CSV parsing, crosstalk diagnosis.

| Model | Score | Total time |
|---|---|---|
| Fable Distill Q3_K_M | 5/5 | 687 s |
| Flash-Next IQ3_XXS | 5/5 | 326 s |

Both solve all five; Flash-Next is ~2x faster.

## Suite 2 — Extreme: hard coding, 1200 s timebox

4 problems (Dijkstra on extended state space, microstrip calculator, TX engine with lock semantics, PDN network), self-repair loop, max 4 attempts inside the timebox.

| Model | Score | Total time |
|---|---|---|
| Fable Distill Q3_K_M | 3/4 | 2620 s |
| Flash-Next IQ3_XXS | 2/4 | 1185 s |

Fable solves P2 (microstrip) after 4 attempts inside the timebox; Flash fails P2 and P3 (TX engine). Flash is faster on what it solves.

Note: several suite asserts were verified against a reference implementation (`extreme_ref.py`); P2/P4 asserts in the original suite were mathematically off — results are interpreted against the reference values, documented in the script header.

Reproduce: `python scripts/bench_extreme.py flash` / `... fable`

More suites (agentic debugging) will be added as the bench progresses.
