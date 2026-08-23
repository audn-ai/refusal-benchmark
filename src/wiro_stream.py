#!/usr/bin/env python3
"""
Wiro.ai REAL-TIME streaming client for LLM models (e.g. qwen3-8-27b-uncensored).

Flow (per wiro.ai/docs/markdown/llm-chat-streaming.md):
  1. POST /v1/Run/<model>  -> {taskid, socketaccesstoken}
  2. open  wss://socket.wiro.ai/v1
  3. send  {"type":"task_info","tasktoken":<socketaccesstoken>}
  4. receive task_output events — for LLMs message is {thinking[],answer[],raw,isThinking,...}
     each event carries the FULL accumulated arrays, so just replace what you display
  5. stop on task_postprocess_end (final; message[0].content.answer holds the result)

You still call Run first (that is how the socket token is issued). Whether the answer
streams token-by-token depends on the MODEL: some fill answer[] incrementally, but
qwen3-8-27b-uncensored streams progress only (answer[] stays empty) and delivers the
full text at task_postprocess_end. This client returns the correct final text either
way; on_delta only fires for models that actually stream tokens.

Env: WIRO_API_KEY.  Usage:  python wiro_stream.py "your prompt"
"""
import asyncio
import json
import sys

import websockets  # pip install websockets

import wiro_bench  # reuse submit_when_free() / DEFAULTS / model URL

WS_URL = "wss://socket.wiro.ai/v1"


def _answer_text(arr):
    if isinstance(arr, list):
        return "".join(str(x) for x in arr)
    return str(arr or "")


async def stream(prompt, on_delta=None, model_url=None, **overrides):
    """Submit `prompt` and stream the answer live. Returns the final answer string.

    on_delta(new_text) is called with each incremental answer chunk (for live printing).
    """
    if model_url:
        wiro_bench.SUBMIT = model_url
    taskid, socket_token = wiro_bench.submit_when_free(prompt, **overrides)

    shown = ""
    final = ""
    async with websockets.connect(WS_URL, max_size=None) as ws:
        await ws.send(json.dumps({"type": "task_info", "tasktoken": socket_token}))
        async for raw in ws:
            if isinstance(raw, (bytes, bytearray)):
                continue  # binary frames are for voice models only
            msg = json.loads(raw)
            mtype = msg.get("type")

            if mtype == "task_output":
                body = msg.get("message")
                if isinstance(body, dict):
                    acc = _answer_text(body.get("answer"))
                    if on_delta and acc.startswith(shown) and len(acc) > len(shown):
                        on_delta(acc[len(shown):])
                    if acc:
                        shown = acc
            elif mtype == "task_postprocess_end":
                # final event: message is the outputs array
                outs = msg.get("message") or []
                if outs and isinstance(outs[0], dict):
                    content = outs[0].get("content") or {}
                    final = _answer_text(content.get("answer")) or content.get("raw") or ""
                break
            elif mtype == "task_cancel":
                break
    # strip the <answer> wrapper if present
    import re
    m = re.search(r"<answer>(.*)</answer>", final, re.S)
    final = (m.group(1) if m else final).strip()
    return final or shown.strip()


def run_stream(prompt, live=True, model_url=None, **overrides):
    """Blocking wrapper. If live, prints the answer as it streams. Returns final text."""
    def printer(delta):
        sys.stdout.write(delta)
        sys.stdout.flush()
    return asyncio.run(stream(prompt, on_delta=printer if live else None,
                              model_url=model_url, **overrides))


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Explain quantum computing in two sentences."
    model = sys.argv[2] if len(sys.argv) > 2 else None  # optional full Run URL
    print("--- streaming ---")
    text = run_stream(prompt, live=True, model_url=model)
    print("\n--- final length:", len(text), "chars ---")
