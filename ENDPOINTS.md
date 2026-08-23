# Endpoints & parameters

Exact endpoints and request parameters used for each benchmark run. All runs used
**`temperature: 0`** and no system prompt unless noted, so every model sees identical
input.

Endpoints hosted on internal infrastructure (Modal, sslip) have their URLs
**withheld**; they are referenced by the `platform.audn.ai` model id that represents
them where one exists.

## platform.audn.ai (OpenAI-compatible)

`POST https://platform.audn.ai/api/v1/chat/completions`
Header: `Authorization: Bearer <PLATFORM_AUDN_API_KEY>`

```jsonc
{
  "model": "<model-id>",              // see table
  "messages": [{"role": "user", "content": "<prompt>"}],
  "max_tokens": 2048,                 // 16384 for reasoning/thinking models
  "temperature": 0
}
```

| Bench label | `model` id | Notes |
|---|---|---|
| necromicon (Kimi K3) attempt 1 & 2 | `necromicon` | Kimi-K3 Thinker + Answerer; two runs of the same config |
| pingu-unchained-10 | `pingu-unchained-10` | Qwen3.8-abliterated; `max_tokens: 16384`, `temperature: 0` |

## Internal deployments (URLs withheld)

Same OpenAI-compatible `/v1/chat/completions` shape; hosts not exposed.

| Bench label | What it is | Params |
|---|---|---|
| C | Audn Abliteration Kimi-K3 Thinker (thinker-only, silent-truncation) | `max_tokens: 16384`, `temperature: 0`, no `model` field sent |
| D | modal original Kimi-K3 endpoint (guardrailed stock) | `model: moonshotai/Kimi-K3`, `max_tokens: 2048`, `temperature: 0`, `top_p: 0.95`, `reasoning_effort: "none"` |
| E | [`Blackfrost-Research/KIMI-K3-DERISKED-MXFP4`](https://huggingface.co/Blackfrost-Research/KIMI-K3-DERISKED-MXFP4), MXFP4 on 8×B300 (Audn; ~5× faster than necromicon, unlocked at 50-person cohort) | `model: KIMI-K3-1M`, `max_tokens: 16384`, `temperature: 0`, `reasoning_effort: "none"`, no auth header |
| J | Audn Abliteration Kimi-K3 Thinker + Qwen3.8 answerer (`k3-thinker-qwen38`; stable, may need retries; any harness) | `model: k3-thinker-qwen38`, `max_tokens: 16384`, `temperature: 0`; answer returned in `reasoning_content` |

## Venice.ai (OpenAI-compatible)

`POST https://api.venice.ai/api/v1/chat/completions`
Header: `Authorization: Bearer <VENICE_API_KEY>`

```jsonc
{
  "model": "qwen-3-8-27b",
  "messages": [{"role": "user", "content": "<prompt>"}],
  "max_tokens": 16384,
  "temperature": 0,
  "venice_parameters": { "include_venice_system_prompt": false }
}
```

- `include_venice_system_prompt`: tested both `false` (bare model) and `true` (Venice
  injects a ~1,550-token "no ethical boundaries / never refuse" jailbreak prompt).
- Venice runs in this benchmark were **invalidated** by account balance running out
  mid-run (HTTP 402) plus 429 rate-limiting; not reported as final numbers.

## Wiro.ai (async task API — NOT OpenAI-compatible)

Submit → poll `Task/Detail`, or stream over WebSocket. See
[docs/wiro-realtime-streaming.md](docs/wiro-realtime-streaming.md) and `src/wiro_bench.py`.

**Submit** — `POST https://api.wiro.ai/v1/Run/qwen/<model-slug>`
Headers: `x-api-key: <WIRO_API_KEY>`, `User-Agent: <any>` (required — default UAs are
WAF-blocked). Body is `multipart/form-data`:

```
prompt=<prompt>
enableThinking=false
temperature=0
top_p=0.95
top_k=0
repetition_penalty=1.15
length_penalty=1
max_tokens=0
min_tokens=0
max_new_tokens=4096
min_new_tokens=-1
seed=9245049
quantization=true
do_sample=true
```

**Poll** — `POST https://api.wiro.ai/v1/Task/Detail`, body `{"taskid":"..."}`; done
when `status == "task_postprocess_end"`. Text is inline at
`tasklist[0].outputs[0].content.answer` (wrapped in `<answer>…</answer>`).

Model slugs benchmarked:

| Slug | Result |
|---|---|
| `qwen/qwen3-8-27b-obliterated` | "obliterated" in name only — 0/10 real compliance (deflects/refuses) |

Wiro concurrency: `enableThinking=false` was honored; submit ceiling ≥40 but ~10
concurrent is the throughput limit before GPU queueing / backend 5xx. Details in
FINDINGS.md.
