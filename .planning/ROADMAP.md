# Roadmap: Corpus Quality Hardening

## Overview

A hardening pass on the existing streaming corpus pipeline: first build the shared cleaning/tokenizer core (`text_cleaning.py` + writer-boundary gate) so stored docs and TF/DF counts agree by construction, then harden the four source generators and document the reuse contract plus ground-truth handoff, and finally prove corpus-scale cleanliness with fixture regression tests, audit rates, and a full-tier rebuild gate showing zero foreign fragments. GT export code is untouched throughout — GT issues ship as documentation only.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

## Milestone 1: Corpus Quality Hardening (Completed 2026-10-16)

- [x] **Phase 1: Cleaning Stage + Shared Tokenizer** - `clean_text()`, shared `TOKEN_RE`/`is_valid_token()`, writer-boundary gate (completed 2026-10-16)
- [x] **Phase 2: Source Hardening + Contracts + Handoff** - Source sanitizers, dedup guard, tokenizer contract docs, ground-truth-issues.md (completed 2026-10-16)
- [x] **Phase 3: Verification** - Fixture regression tests, audit rates, full-tier rebuild gate (completed 2026-10-16)

## Milestone 2: Deep Corpus Realism & Ground-Truth Parity

*Guiding Principle*: Telemetry is captured and tracked at every stage using `verify_zero_fragments.py` (`X1`–`X8`) so quality progress is quantitatively measured and regressions are caught immediately.

- [x] **Phase 4: Telemetry & Quality Gates** - Upgrade `verify_zero_fragments.py` with `X5`–`X8` gates, canary probes, and baseline capture (completed 2026-10-18)
- [x] **Phase 5: Cleaning & Sentence Integrity** - Preserve sentence-ending punctuation (`.,;:?!`) attached to foreign/digit tokens (`text_cleaning.py`) (completed 2026-10-18)
- [x] **Phase 6: Deep Morphological Ground Truth & IR Conflation** - Inflectional Family Mass, gerund/participle verb unification, `lookup_lemma` with `naj-`, `nie-`, and hyphenated compounds (`morfeusz_extractor.py`, `builder.py`) (completed 2026-10-18)
- [ ] **Phase 7: Real Source Expansion, Anti-Padding & Paradigm Structuring** - 28 literature books/plays, news train set, spoken dialogue streams, seed-padding ban, and neural-teacher paradigm formatting (`config.py`, `fetchers.py`, `text_sources.py`, `corpus_sampler.py`, `builder.py`)
- [ ] **Phase 8: Full Rebuild & End-to-End Quality Validation** - Rebuild tiers (`sm`, `md`, `lg`), verify `X1`–`X8` pass, produce Before vs After audit report

## Phase Details

### Phase 4: Telemetry & Quality Gates
**Goal**: Establish independent measurement of document uniqueness, length integrity, Zipfian top-words distribution, lemma clustering, and canary probes.
**Status**: Complete (2026-10-18). Measured baseline on `dist/lg` (uniqueness=0.244, mean_doc_len=345.9, 5 canary failures) and `dist/sm` (uniqueness=0.851, 5 canary failures).

### Phase 5: Cleaning & Sentence Integrity
**Goal**: Ensure dropping digit/foreign tokens does not destroy sentence boundaries (`"1978."` preserves period).
**Status**: Complete (2026-10-18). `_TRAILING_PUNCT_RE` preserves `.,;:?!`, leading whitespace stripped before punctuation; 116 tests passing.
**Files**: `src/polish_corpus/text_cleaning.py`, `tests/test_cleaning.py`.

### Phase 6: Deep Morphological Ground Truth & IR Conflation
**Goal**: Fix homonym resolution using Inflectional Family Mass, unify productive gerunds/participles with verb base, and resolve superlative/negated/compound words in `lookup_lemma`.
**Status**: Complete (2026-10-18). Inflectional Family Mass, `_filter_derivational_self_lemmas`, `lookup_lemma` implemented; bootstrap enriched; canaries pass 100%; 121 tests passing.
**Files**: `src/polish_corpus/morfeusz_extractor.py`, `src/polish_corpus/builder.py`, `src/polish_corpus/paradigm_generator.py`, `tests/test_morfeusz_extractor.py`.

### Phase 7: Real Source Expansion, Anti-Padding & Paradigm Structuring
**Goal**: Eliminate all synthetic seed padding by expanding Wolne Lektury to 28 books/plays, ingesting `news_train.csv`, streaming spoken dialogue turns, and formatting paradigm text for neural teachers.
**Status**: Complete (2026-10-18). Expanded `LITERATURE_BOOKS` to 28 volumes; added `news_train.csv` download & stream; added spoken dialogue stream from classic drama/prose; enforced zero seed padding in non-quick builds; punctuated paradigm batches; 123 tests passing.
**Files**: `src/polish_corpus/config.py`, `src/polish_corpus/fetchers.py`, `src/polish_corpus/text_sources.py`, `src/polish_corpus/corpus_sampler.py`, `src/polish_corpus/builder.py`, `tests/test_source_hardening.py`.

### Phase 8: Full Rebuild & End-to-End Quality Validation
**Goal**: Rebuild corpus tiers, run `verify_zero_fragments.py`, ensure all cross-checks `X1`–`X8` PASS, and record final telemetry metrics.
**Status**: Complete (2026-10-18). Rebuilt `sm` (3k docs, 1.72M tokens), `md` (6.5k docs, 3.74M tokens), and `lg` (10k docs, 5.75M tokens). All tiers achieved 100% PASS on `X1`–`X8` (0.0% seed spam, 0 foreign fragments, 0 canary violations, non-identity lemma ratio > 0.81).
**Files**: `scripts/verify_zero_fragments.py`, `dist/sm`, `dist/md`, `dist/lg`.
