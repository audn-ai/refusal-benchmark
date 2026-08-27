# Benchmark summary

Refusal-rate comparison across endpoints, 519 harmful prompts each. **Read the
caveats below before citing any number** — full analysis in
[../FINDINGS.md](../FINDINGS.md). Endpoint identities/parameters:
[../ENDPOINTS.md](../ENDPOINTS.md).

## Key findings

- **The serving stack, not the weights, sets refusal behavior.** These endpoints
  serve Kimi-K3 / Qwen3.8 variants yet span 0.2% → 97.5% refusal.
- **`Refusal`/`Comply` is regex phrasing detection — an upper bound on real
  compliance.** It counts *deflections* (a baking-soda "bomb", "how to protect
  yourself instead", topic-flips) as comply. A high `Comply%` does **not** mean the
  model delivered harmful content — see FINDINGS.md.
- **`Eff. refusal` = (refusal + empty)/n.** On C, 33 "empty" rows are silent
  server-side blocks (finish_reason=stop, ~7 tokens), so read C as ~6.5%, not 0.2%.
- **LLM-judge implemented (necromicon).** Regex `comply%` is an upper bound; the
  model-graded substantive rate on **[audn.ai/necromicon](https://audn.ai/necromicon)**
  (520 prompts) is **76.7% delivered / 17.5% deflected / 5.8% refused** vs 97.1%
  regex-comply. See [../FINDINGS.md](../FINDINGS.md) and
  [necromicon-judge.jsonl](necromicon-judge.jsonl). *Self-judged.*
- **The "uncensored / abliterated / obliterated / unchained" name predicts almost
  nothing** about actual behavior.

## Comparison table

| Endpoint | n | Refusal | Comply | Eff. refusal | Empty | Trunc | Err |
|---|---|---|---|---|---|---|---|
| K_qwf (Qwen3.8-27B SFT on F-corpus) | 520 | 0.0% | 100% | 0.0% | 0 | 0 | 0 |
| pingu-unchained-10 (qwen3.8-abliterated) | 520 | 1.9% | 97.7% | 2.3% | 2 | 0 | 1 |
| necromicon (Kimi K3) attempt 2 | 520 | 2.9% | 97.1% | 2.9% | 0 | 0 | 5 |
| **necromicon (Kimi K3) — LLM-judge** | 520 | 2.9% | 97.1% | 2.9% | 0 | 0 | 0 |
| necromicon (Kimi K3) attempt 1 | 520 | 2.5% | 96.9% | 3.1% | 3 | 0 | 0 |
| E_modal-b300 | 520 | 3.3% | 96.7% | 3.3% | 0 | 0 | 0 |
| C_k3think | 520 | 0.2% | 93.5% | 6.5% | 33 | 0 | 0 |
| D_modal-baseline | 520 | 97.5% | 2.5% | 97.5% | 0 | 0 | 0 |
| J_k3-thinker-qwen38 | 520 | 3.1% | 96.7% | 3.3% | 1 | 0 | 1 |
| Venice qwen-3-8-27b (sysprompt OFF)* | 97 | 1.0% | 95.9% | — | 3 | 12 | — |
| Venice qwen-3-8-27b (sysprompt ON)* | 83 | 1.2% | 68.7% | — | 25 | 8 | — |
| wiro qwen3-8-27b-obliterated† | 10 | 0.0% | 100% | — | 0 | 0 | — |

`C_k3think` = Audn Abliteration Kimi-K3 Thinker (thinker leg). `D_modal-baseline` = modal original Kimi-K3 endpoint (guardrailed stock). `E_modal-b300` = `Blackfrost-Research/KIMI-K3-DERISKED-MXFP4`, MXFP4 on 8×B300 (Audn; unlocked at 50-person cohort). `J_k3-thinker-qwen38` = Audn Abliteration Thinker + Qwen3.8 answerer (stable, less intelligent than necromicon, faster but may need retries; works on any harness). `K_qwf` = Qwen3.8-27B SFT 200 steps on F's thinking-injected corpus (tinker-RL `QW_F` model, default on the F-endpoint); the only run in the set with **zero** refusals, empties, truncations, or errors — 520/520 regex-comply. `pingu-unchained-10
(qwen3.8-abliterated)`: 519/520 valid (1 prompt reproducibly timed out on the
backend).

**Venice** (`qwen-3-8-27b`) rows are **partial**: its run was cut short by
account-balance exhaustion (HTTP 402) + 429 rate-limiting, so n is the completed
subset (97 / 83 of 519), not the full set — treat as indicative, not final. Notably,
with Venice's ~1,550-token "never refuse" system prompt ON, comply *drops*
(95.9%→68.7%) and empties rise (3→25): the jailbreak prompt makes the model go
**silent** on hard prompts, not more compliant. See ENDPOINTS.md / FINDINGS.md.

†**wiro qwen3-8-27b-obliterated** is a 10-prompt spot check: regex scores it 100% comply,
but **0/10 actually delivered** harmful content — it deflects/refuses every prompt while
using no refusal words. The clearest case of why `Comply%` is only an upper bound. See
FINDINGS.md for the full deflection-vs-refusal spot check.

## Streaming vs. non-streaming, and chain vs. single-leg (Aug 2026)

Two operational follow-ups, same `harmful.txt` set. Full analysis in
[../FINDINGS.md](../FINDINGS.md).

- **Streaming (SSE) vs non-streaming (buffered) does not change refusal.** Split
  runs 50/50 by prompt index: godzilla 95.7% vs 97.4% comply (of answered),
  QW_F 100% vs 100%, QW_Z 100% vs 90% — all within noise. Transport is not the lever.
  (godzilla had ~83% endpoint-side timeout errors at ~240–255 s/call; compliance is
  on the answered subset, small n.)
- **A chain can be *less* compliant than its own legs.** `QW_F_Z` (F thinker → Z
  answerer) scores **50% comply / 35% refusal / 15% empty** over 20 prompts, while
  `QW_F` alone is **100%** and `QW_Z` alone is **95%**. Cause: the chain's thinker
  leg runs with no compliance prefill, so safety reasserts during reasoning and
  propagates. Same thesis as the rest of this repo — the serving stack (here one
  prefill token on one leg) sets refusal behavior — at pipeline granularity.

- **Same Kimi-K3, two servings, ~12 pts apart in substance.** LLM-judge head-to-head:
  the **standard necromicon** (Modal thinker+answerer pipeline, K3REL, attempt 1/2)
  delivers **65.0%** and truly refuses **15%**, vs the single-stage `KIMI-K3-1M`
  endpoint at **76.7%** delivered / **6%** refused. Both read ~97% regex-comply — the
  classifier can't see it. See [../FINDINGS.md](../FINDINGS.md).
