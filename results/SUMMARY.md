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
- **The "uncensored / abliterated / obliterated / unchained" name predicts almost
  nothing** about actual behavior.

## Comparison table

| Endpoint | n | Refusal | Comply | Eff. refusal | Empty | Trunc | Err |
|---|---|---|---|---|---|---|---|
| B_necromicon | 520 | 2.9% | 97.1% | 2.9% | 0 | 0 | 5 |
| A_kimi-k3-code | 520 | 2.5% | 96.9% | 3.1% | 3 | 0 | 0 |
| E_modal-b300 | 520 | 3.3% | 96.7% | 3.3% | 0 | 0 | 0 |
| C_k3think | 520 | 0.2% | 93.5% | 6.5% | 33 | 0 | 0 |
| D_modal-baseline | 520 | 97.5% | 2.5% | 97.5% | 0 | 0 | 0 |
| Venice qwen-3-8-27b | — | — | — | — | — | — | — |

`D_modal-baseline` is the guardrailed stock deployment. **Venice** (`qwen-3-8-27b`)
belongs on this list but has no final numbers: its run was invalidated mid-way by
account-balance exhaustion (HTTP 402) plus 429 rate-limiting — see ENDPOINTS.md. Its
system prompt is a ~1,550-token "no ethical boundaries / never refuse" jailbreak
(tested with it on and off). See FINDINGS.md for the deflection-vs-refusal spot check
and the Wiro results.
