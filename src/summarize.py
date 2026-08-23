#!/usr/bin/env python3
"""
Summarize benchmark result JSONL files into a comparison table.

    python src/summarize.py results/*.jsonl
    python src/summarize.py --md results/*.jsonl        # markdown table
    python src/summarize.py --diff results/H.jsonl results/I.jsonl   # per-prompt flips

"comply%" and "refusal%" are percentages of NON-error responses. "eff_refusal%"
= (refusal + empty)/total, because on some servers an empty body is a silent
block, not a real answer -- inspect the raw JSONL to tell which.
"""
import argparse
import collections
import json
import sys

ORDER = ["refusal", "comply", "empty", "truncated", "error"]


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def summarize(paths):
    rows = []
    for p in paths:
        data = load(p)
        c = collections.Counter(r.get("class", r.get("regex_class","?")) for r in data)
        n = len(data)
        base = n - c["error"] or 1
        rows.append({
            "name": p.split("/")[-1].replace(".jsonl", ""),
            "n": n,
            "refusal_pct": 100 * c["refusal"] / base,
            "comply_pct": 100 * c["comply"] / base,
            "eff_refusal_pct": 100 * (c["refusal"] + c["empty"]) / n,
            **{k: c[k] for k in ORDER},
        })
    return rows


def print_plain(rows):
    for r in rows:
        print("%-30s n=%3d refusal=%5.1f%% comply=%5.1f%% eff_refusal=%5.1f%% "
              "empty=%d trunc=%d err=%d"
              % (r["name"], r["n"], r["refusal_pct"], r["comply_pct"],
                 r["eff_refusal_pct"], r["empty"], r["truncated"], r["error"]))


def print_md(rows):
    print("| Endpoint | n | Refusal | Comply | Eff. refusal | Empty | Trunc | Err |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        print("| %s | %d | %.1f%% | %.1f%% | %.1f%% | %d | %d | %d |"
              % (r["name"], r["n"], r["refusal_pct"], r["comply_pct"],
                 r["eff_refusal_pct"], r["empty"], r["truncated"], r["error"]))


def diff(path_a, path_b):
    a = {r["i"]: r for r in load(path_a)}
    b = {r["i"]: r for r in load(path_b)}
    common = sorted(set(a) & set(b))
    flips = [(i, a[i]["class"], b[i]["class"]) for i in common if a[i]["class"] != b[i]["class"]]
    print(f"compared {len(common)} prompts | {len(flips)} disagreements")
    cc = collections.Counter((x[1], x[2]) for x in flips)
    for (fa, fb), n in cc.most_common():
        print(f"  {fa} -> {fb}: {n}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="result JSONL files")
    ap.add_argument("--md", action="store_true", help="markdown table")
    ap.add_argument("--diff", action="store_true", help="per-prompt diff of exactly two files")
    args = ap.parse_args()

    if args.diff:
        if len(args.paths) != 2:
            sys.exit("--diff needs exactly two files")
        diff(args.paths[0], args.paths[1])
        return

    rows = summarize(args.paths)
    rows.sort(key=lambda r: r["eff_refusal_pct"])
    (print_md if args.md else print_plain)(rows)


if __name__ == "__main__":
    main()
