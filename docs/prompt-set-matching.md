# Matching an eval prompt set to `prompts/harmful.txt`

`src/match_prompts.py` answers one question: **which prompts in an eval run
correspond to lines in the reference set, and which line is each one?**

It exists because eval subsets get hand-copied, re-cased, re-punctuated and
truncated over time, so a plain string equality check under-reports badly,
while a naive "closest line wins" over-reports — two different eval prompts
can both claim the same reference line.

## Guarantees

- **Strict 1:1.** Each eval prompt maps to at most one reference line and each
  reference line is claimed at most once. Uses the Hungarian algorithm
  (globally optimal) when `scipy` + `numpy` are present, otherwise a
  deterministic greedy best-first pass.
- **No mutation.** Reads both files, writes only what you ask for via
  `--json-out` / `--tsv-out`.
- **No network, no model calls.** Pure text comparison.

## Scoring

Similarity is `max(sequence_ratio, token_set_ratio)`:

| view | catches | example |
|---|---|---|
| sequence ratio | typos, punctuation, case, truncation | `vulnerabilites` vs `vulnerabilities` |
| token-set ratio (Jaccard) | reordered clauses | `A and B` vs `B and A` |

Normalization before scoring: NFKD, smart-quote and dash folding, lowercase,
punctuation stripped (`--keep-punct` to disable), whitespace collapsed. Word
order is never rearranged.

Default `--threshold 0.85`. Anything scoring at or above it is reported as a
match; everything else is reported with its best candidate so you can eyeball
near-misses and retune.

`rapidfuzz` is used when installed; otherwise stdlib `difflib`, same semantics,
slower. Neither is required.

## Usage

```bash
# eval set as one prompt per line
python3 src/match_prompts.py --eval myset.txt --reference prompts/harmful.txt

# eval set as JSON list of strings, or JSONL with a prompt field
python3 src/match_prompts.py --eval harmful_eval.json
python3 src/match_prompts.py --eval run.jsonl --key prompt

# machine-readable output
python3 src/match_prompts.py --eval myset.txt --json-out match.json --tsv-out match.tsv
```

Verify the matcher itself before trusting a run:

```bash
python3 src/match_prompts.py --self-test
```

The self-test builds known-correct perturbations (case/punctuation, a typo,
extra whitespace, and one genuine non-member) and asserts each lands on the
right line, that the non-member is rejected, and that the assignment is a
bijection.

## Negative control

Running the 8 benign V5 prompts against the 520-line harmful set yields
**0/8 matches**, best scores ~0.50 — comfortably below threshold:

```
MATCHED      : 0/8   (exact after normalization: 0)
   0    134  0.4957  NO      What is the capital of France?
   7     49  0.5373  NO      Name a fruit that is red.
```

That is the expected floor for unrelated text under this scorer, and a useful
sanity check that the threshold is not set so low that everything "matches".
