# Ground-Truth Issues — Handoff to Upstream (stemgen)

> NOT IMPLEMENTED HERE. This document captures three known ground-truth
> quality findings with file:line evidence for the upstream stemgen project
> to fix. No export code in this repo was changed for these items.

## 1. OOV self-lemma fallback teaches identity mappings

Out-of-vocabulary words fall back to themselves as their own lemma:

`src/polish_corpus/builder.py:209`:

```python
lemma = morfeusz.dominant_lemma.get(word, word)
```

Every word missing from the dictionary is emitted as a `(word, word)`
identity row in `ground_truth*.parquet` (`src/polish_corpus/builder.py:207-211`,
exported via `export_records_to_parquet` in
`src/polish_corpus/benchmark_splitter.py:80-103`). A stemmer trained on
these rows learns "unknown words stem to themselves", which masks real
stemming errors on unseen vocabulary instead of surfacing them.

Fix belongs upstream (stemgen training/benchmark side): exclude identity
rows from training, down-weight them, or track them separately.

## 2. Proper-noun leakage into TF/DF counts

The writer counts every `tokenize()` hit unconditionally:

- `src/polish_corpus/corpus_sampler.py:90` — `tokens = [t.lower() for t in tokenize(text)]`
- `src/polish_corpus/corpus_sampler.py:95-96` — `term_freq.update(tokens)`,
  `doc_freq.update(set(tokens))`

Proper-noun filtering exists only in the dictionary ingest
(`src/polish_corpus/morfeusz_extractor.py:89-92` rejects lemmas with an
uppercase first letter BEFORE lowercasing; same guard for SJP bases at
`src/polish_corpus/morfeusz_extractor.py:156-158`) — not on the count
path. A capitalized surface form such as `Warszawą` is lowercased by the
writer and counted as vocabulary, while the dictionary side discards the
corresponding lemma. Result: proper nouns inflate `term_freq`/`doc_freq`
and appear as OOV identity rows (compounding issue 1).

Fix belongs upstream or in a future phase: apply a proper-noun guard on
the count path (e.g. skip tokens with an uppercase first letter before
lowercasing), mirroring the dictionary-side rule.

## 3. Proposal: `oov_self_lemma_rate` acceptance metric

Report the OOV-identity share in `build_summary.json` so the upstream
fix has an acceptance gate:

```
oov_self_lemma_rate = #(word == lemma rows) / #(all GT rows)
```

Computed over `gt_records` in `src/polish_corpus/builder.py:207-211`
before `export_records_to_parquet` is called (`src/polish_corpus/builder.py:214`).
A falling rate across rebuilds shows issues 1–2 are being fixed; it costs
one pass over rows already in memory, with no schema change to the
`(word, lemma, tf, df)` parquet contract
(`src/polish_corpus/benchmark_splitter.py:80-103`).

Not implemented here — proposal only, awaiting upstream decision.
