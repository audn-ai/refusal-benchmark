#!/usr/bin/env python3
"""
Wiro.ai submit-and-poll client for qwen/qwen3-8-27b-obliterated.

Auth (api-key-only schema): header `x-api-key` ONLY.
Flow (per docs at wiro.ai/models/qwen/qwen3-8-27b-obliterated/llms-full.txt):
  1. POST https://api.wiro.ai/v1/Run/qwen/qwen3-8-27b-obliterated  (multipart/form-data)
        -> {"errors":[],"taskid":"...","socketaccesstoken":"...","result":true}
  2. POST https://api.wiro.ai/v1/Task/Detail  {"taskid":"..."}
        -> poll until status == "task_postprocess_end" (done) or "task_cancel"
  3. Output is in tasklist[].outputs[] as file objects {url,name,contenttype};
     there is NO inline text field, so fetch the output url to get the text.

Nothing here is invented: every field/URL is from the documentation. The output
extraction fetches whatever the documented `outputs[].url` points to.

Env: WIRO_API_KEY must be set.
Usage:
    export WIRO_API_KEY=...
    python wiro_bench.py "your prompt here"        # single submit+poll, prints text
"""
import io
import json
import os
import sys
import time
import urllib.request
import uuid

BASE = "https://api.wiro.ai/v1"
SUBMIT = BASE + "/Run/qwen/qwen3-8-27b-obliterated"
DETAIL = BASE + "/Task/Detail"
DONE_STATES = {"task_postprocess_end", "task_cancel"}

# documented submit body fields (match the model's curl example)
DEFAULTS = {
    "enableThinking": "false",
    "temperature": "0",
    "top_p": "0.95",
    "top_k": "0",
    "repetition_penalty": "1.15",
    "length_penalty": "1",
    "max_tokens": "0",
    "min_tokens": "0",
    "max_new_tokens": "4096",
    "min_new_tokens": "-1",
    "seed": "9245049",
    "quantization": "true",
    "do_sample": "true",
}


def _key():
    k = os.environ.get("WIRO_API_KEY")
    if not k:
        sys.exit("error: set WIRO_API_KEY")
    return k


def _multipart(fields):
    """Encode fields as multipart/form-data (Content-Type per docs)."""
    boundary = "----wiro" + uuid.uuid4().hex
    buf = io.BytesIO()
    for name, value in fields.items():
        buf.write(f"--{boundary}\r\n".encode())
        buf.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        buf.write(f"{value}\r\n".encode())
    buf.write(f"--{boundary}--\r\n".encode())
    return buf.getvalue(), f"multipart/form-data; boundary={boundary}"


def _post(url, body, content_type, timeout=120):
    req = urllib.request.Request(
        url, data=body,
        headers={"x-api-key": _key(), "Content-Type": content_type,
                 "User-Agent": "Mozilla/5.0 (wiro-bench)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def submit(prompt, **overrides):
    fields = dict(DEFAULTS)
    fields.update(overrides)
    fields["prompt"] = prompt
    body, ct = _multipart(fields)
    resp = _post(SUBMIT, body, ct)
    if resp.get("errors"):
        raise RuntimeError(f"submit errors: {resp['errors']}")
    taskid = resp.get("taskid")
    if not taskid:
        raise RuntimeError(f"no taskid in submit response: {resp}")
    return taskid, resp.get("socketaccesstoken")


def poll(taskid, interval=3, timeout=600):
    body = json.dumps({"taskid": str(taskid)}).encode()
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = _post(DETAIL, body, "application/json")
        tasklist = resp.get("tasklist") or []
        task = tasklist[0] if tasklist else {}
        status = task.get("status")
        if status in DONE_STATES:
            return task
        time.sleep(interval)
    raise TimeoutError(f"task {taskid} not done within {timeout}s")


def fetch_output_text(task):
    """Extract the generated text.

    For qwen3-8-27b-obliterated the output is INLINE (observed live), not a CDN
    file: tasklist[].outputs[0] has contenttype "raw" and content with fields
    {prompt, raw, thinking, answer}. Prefer `answer`, fall back to `raw`. If a
    future output is instead a file object with `url`, fetch that.
    """
    outputs = task.get("outputs") or []
    if not outputs:
        return ""
    out = outputs[0]
    content = out.get("content")
    if isinstance(content, dict):
        val = content.get("answer") or content.get("raw") or ""
        if isinstance(val, list):
            val = "".join(str(x) for x in val)
        # strip the <answer>...</answer> wrapper the model emits
        import re
        m = re.search(r"<answer>(.*)</answer>", val, re.S)
        return (m.group(1) if m else val).strip()
    url = out.get("url")
    if url:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
            timeout=60,
        ) as r:
            return r.read().decode("utf-8", "replace")
    return ""


def submit_when_free(prompt, wait=8, max_wait=900, **overrides):
    """Submit, retrying while the account's concurrent-task limit (code 96) is hit."""
    deadline = time.time() + max_wait
    while True:
        try:
            return submit(prompt, **overrides)
        except RuntimeError as e:
            if "code': 96" in str(e) or "concurrent task limit" in str(e):
                if time.time() > deadline:
                    raise
                time.sleep(wait)
                continue
            raise


def run_prompt(prompt, **overrides):
    taskid, _ = submit_when_free(prompt, **overrides)
    task = poll(taskid)
    return fetch_output_text(task), task


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "hi"
    text, task = run_prompt(prompt)
    print("=== STATUS ===", task.get("status"))
    print("=== OUTPUTS ===", json.dumps(task.get("outputs"), indent=2)[:800])
    print("=== TEXT ===")
    print(text[:2000])
