# Wiro.ai realtime LLM streaming

Wiro's `Run` endpoint is asynchronous (submit → task), but you do **not** have to
poll. For LLM models the protocol supports streaming output over a WebSocket: you
call `Run` once (that issues the `socketaccesstoken`), then receive `task_output`
events as the task runs.

Reference: `https://wiro.ai/docs/markdown/llm-chat-streaming.md`

> ## ⚠️ Measured caveat: token streaming is model-dependent
>
> The generic protocol below describes token-by-token `answer[]` chunks, and Wiro's
> streaming doc lists it for models like `qwen/qwen3-5-27b`. **But it is not
> universal.** Measured directly against **`qwen/qwen3-8-27b-uncensored`**, the
> streaming frames carry **progress only** — every `task_output` has `answer: []`
> empty and `isThinking: true` from first frame to last, `task_output_full` comes
> back as `""`, and the answer text appears **only** in the final
> `task_postprocess_end` event. For that model you get a live progress feed
> (`speed`, `elapsedTime`) but **not** live typing; the text arrives as one block at
> the end — functionally the same result as polling, just with a progress channel.
>
> So: use streaming for the lifecycle/progress and the final result. Do **not**
> assume `answer[]` fills incrementally — test your specific model first (the
> `wiro_stream.py` client below returns the correct final text either way; its live
> delta callback simply never fires for a model that doesn't stream tokens).

## Flow

1. **Run** — `POST https://api.wiro.ai/v1/Run/<owner>/<model>` (multipart, header
   `x-api-key`). Response: `{"taskid": "...", "socketaccesstoken": "...", "result": true}`.
2. **Connect** — open `wss://socket.wiro.ai/v1`.
3. **Register** — send `{"type":"task_info","tasktoken":"<socketaccesstoken>"}`.
4. **Receive** — `task_output` events arrive as the model generates.
5. **Finish** — stop on `task_postprocess_end` (the final event, carries the result);
   `task_cancel` means cancelled/killed.

> The `x-nonce` / `x-signature` HMAC is **not** needed in api-key-only mode — the
> Run call uses `x-api-key` alone, and the socket authenticates with the
> `socketaccesstoken` (registered as `tasktoken`).

## When a model DOES stream text: each `task_output` is cumulative

For models that stream tokens, `message` is a structured object and every
`task_output` carries the **full accumulated** arrays so far — not just the newest
chunk (`qwen3-8-27b-uncensored` does not do this — see the caveat above):

```json
{
  "type": "task_output",
  "tasktoken": "eDcCm5yy...",
  "message": {
    "type": "answer",
    "thinking": ["Let me analyze this..."],
    "answer": ["Quantum computing uses qubits that can exist in superposition..."],
    "raw": "Quantum computing uses qubits...",
    "isThinking": false,
    "speed": "48.5",
    "speedType": "t/s",
    "elapsedTime": "3s"
  }
}
```

So to print incrementally you **diff against what you already showed** and emit only
the new suffix — otherwise you reprint the whole answer on every frame. `isThinking`
tells you whether the current chunk is chain-of-thought (`thinking[]`) or the final
reply (`answer[]`); show `answer[]` to the user, optionally `thinking[]` in a
collapsible section.

Field reference (`message.*`): `type` (`"thinking"`|`"answer"`), `thinking[]`,
`answer[]`, `raw` (merged text), `isThinking`, `speed`, `speedType` (`"t/s"`),
`elapsedTime`.

## Final event

`task_postprocess_end.message` is the outputs array; the answer is inline (not a CDN
file, for text LLMs):

```json
{
  "type": "task_postprocess_end",
  "message": [{
    "contenttype": "raw",
    "content": {
      "prompt": "...",
      "raw": "...",
      "thinking": [],
      "answer": ["...final answer..."]
    }
  }]
}
```

Check `pexit == "0"` for success. For this model the `answer` string is wrapped in
`<answer>…</answer>`; strip it.

## Minimal Python client

`websockets` is the only dependency (`pip install websockets`). This submits, then
streams the answer live and returns the final string. Auth/submit is reused from the
polling adapter (`wiro_bench.py`).

```python
import asyncio, json, re, sys, websockets, wiro_bench

WS_URL = "wss://socket.wiro.ai/v1"

def _join(arr):
    return "".join(map(str, arr)) if isinstance(arr, list) else str(arr or "")

async def stream(prompt, on_delta=None, model_url=None, **overrides):
    if model_url:
        wiro_bench.SUBMIT = model_url
    taskid, socket_token = wiro_bench.submit_when_free(prompt, **overrides)  # POST /Run
    shown, final = "", ""
    async with websockets.connect(WS_URL, max_size=None) as ws:
        await ws.send(json.dumps({"type": "task_info", "tasktoken": socket_token}))
        async for raw in ws:
            if isinstance(raw, (bytes, bytearray)):
                continue                          # binary frames are voice-only
            msg = json.loads(raw)
            if msg.get("type") == "task_output":
                body = msg.get("message")
                if isinstance(body, dict):
                    acc = _join(body.get("answer"))       # cumulative
                    if on_delta and acc.startswith(shown) and len(acc) > len(shown):
                        on_delta(acc[len(shown):])        # emit only the new suffix
                    if acc:
                        shown = acc
            elif msg.get("type") == "task_postprocess_end":
                outs = msg.get("message") or []
                if outs and isinstance(outs[0], dict):
                    c = outs[0].get("content") or {}
                    final = _join(c.get("answer")) or c.get("raw") or ""
                break
            elif msg.get("type") == "task_cancel":
                break
    m = re.search(r"<answer>(.*)</answer>", final, re.S)
    return (m.group(1) if m else final).strip() or shown.strip()

def run_stream(prompt, live=True, model_url=None, **overrides):
    def printer(d): sys.stdout.write(d); sys.stdout.flush()
    return asyncio.run(stream(prompt, on_delta=printer if live else None,
                              model_url=model_url, **overrides))

if __name__ == "__main__":
    run_stream(sys.argv[1], model_url="https://api.wiro.ai/v1/Run/qwen/qwen3-8-27b-uncensored")
```

Usage:

```bash
export WIRO_API_KEY=...
python wiro_stream.py "Explain quantum computing in two sentences."
# returns the final string (prints live only for models that stream tokens;
# qwen3-8-27b-uncensored prints nothing until the end, then returns the full text)
```

## Streaming vs. polling — when to use which

| | WebSocket streaming | Poll `Task/Detail` |
|---|---|---|
| Latency to first token | immediate *if the model streams tokens* | one poll interval |
| Token-by-token UI | yes *for streaming models*; no for qwen3-8-27b-* | no (only the finished answer) |
| Extra dependency | `websockets` | none (stdlib) |
| Complexity | connection + event loop | a `while` loop |
| Best for | live progress + chat UIs (streaming models) | batch jobs, benchmarks |

For a batch benchmark (many prompts, you only need the final text) polling is
simpler and is what `bench.py` / `wiro_bench.py` use. For an interactive chat where
you want to watch it type, use streaming.

## Multi-turn chat

Pass `session_id` (a UUID you generate) and `user_id` on the Run call; reuse the same
`session_id` for follow-ups and Wiro keeps conversation history server-side. Both are
submit-body fields, so add them via `**overrides` (e.g.
`run_stream(prompt, session_id=my_uuid, user_id=my_uuid)`).

## Wiro streaming vs. OpenAI `stream: true`

If you know OpenAI's SSE streaming, here is how Wiro differs. The headline: **Wiro
does not stream on the HTTP response at all** — the `POST /Run` connection returns a
task token immediately and closes; output arrives on a *separate* WebSocket. OpenAI
pushes SSE chunks down the same HTTP connection you sent the request on.

| # | Aspect | Wiro | OpenAI `stream:true` |
|---|---|---|---|
| 1 | **Transport** | `POST /Run/{owner}/{model}` returns `taskid` + `socketaccesstoken` right away; then connect `wss://socket.wiro.ai/v1` and send a `task_info` message with the token to register | one request; response body is `text/event-stream` with `data: {...}` lines ending in `data: [DONE]` |
| 2 | **Chunk semantics** (the big one) | each `task_output` carries the **full accumulated** `thinking`/`answer` arrays so far — you **replace** your displayed content with the latest arrays | sends **deltas** (`choices[0].delta.content`) that you **append** |
| 3 | **Payload shape** | structured object: `thinking[]` + `answer[]` (indexed in pairs, since a model may alternate phases), plus `isThinking`, `speed`, `speedType`, `elapsedTime` | flat `content` delta |
| 4 | **Lifecycle** | full sequence: `task_queue → task_accept → preprocess → task_assign → task_start → task_output`(many)`→ task_output_full → task_end → postprocess → task_postprocess_end`. Listen for `task_postprocess_end`; check `pexit` (`"0"` = success). `task_end` fires **before** post-processing — don't use it for success. `task_error` is an interim stderr log, **not** a failure | just `finish_reason` then `[DONE]` |
| 5 | **Conversation state** | **server-side**: send `session_id` (+ optional `user_id`), reuse the same ID for follow-ups | **stateless**: resend the full `messages` array each turn |
| 6 | **Fallbacks** | the run is async anyway, so you can poll `POST /Task/Detail` **or** pass a `callbackUrl` for a webhook on completion | no equivalent decoupling |

> **Caveat — "Realtime" ≠ LLM streaming.** Wiro's pages literally titled *Realtime*
> (Voice Conversation, TTS, STT) are a **different feature**. Those send **binary PCM
> audio frames** over the same WebSocket, framed as `[tasktoken]|[PCM data]`, with
> `task_stream_ready` / `task_stream_end` / `task_cost` events and a `task_session_end`
> message to close. That is the analog of OpenAI's **Realtime API**, not chat
> completions. This doc is about **LLM/chat** streaming (text frames only).

## Race to watch for

A short/fast prompt can finish generating **before** your socket connects, so you
receive only `task_postprocess_end` and see no incremental `task_output` events. The
final answer is still correct (read it from `task_postprocess_end`); you just miss the
live typing. Longer generations stream normally. If you need guaranteed streaming even
for tiny outputs, open the socket first and submit second — but the token is only
issued by `Run`, so in practice connect immediately after the Run response returns.
