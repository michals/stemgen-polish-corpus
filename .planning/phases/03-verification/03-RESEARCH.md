# Phase 3: Verification — Research

**Researched:** 2026-10-16 · **Domain:** audit instrumentation + fixture consolidation + corpus-scale gate · **Confidence:** HIGH

Locked: GT export code untouched, no stemgen changes, stdlib only (+ existing `pyarrow` for parquet reads), streaming counters (O(1) memory). Builds on Phase 1 choke point + Phase 2 guards. No CONTEXT.md exists (same as Phases 1–2) — planning from research + requirements.

## 1. VER-03 — Audit rates: exact insertion points

**Design:** new `audit_clean(text) -> tuple[str, AuditCounts]` in `text_cleaning.py` beside `clean_text()`. `AuditCounts` is a small `NamedTuple` (`foreign_dropped, digit_dropped, url_removed, email_removed, tokens_kept`) counted in the same single pass that already classifies each whitespace-token (`_drop_token` distinguishes digit-cause vs foreign-cause; URL/email subs count via `subn`). `clean_text()` delegates to it (discards counts) so behavior is identical — one implementation, no drift. `tokenize()` output length feeds `tokens_kept` (counted on the cleaned text, consistent with writer TF/DF).

**Writer:** `BalancedCorpusWriter` gains `audit: dict[str, Counter]` per genre + global rollup, accumulated in `add_document()` (the choke point — every stored doc passes through it). `summary()` exposes `audit_rates`: per genre and global, each `{foreign_fragment_rate, digit_token_rate, dropped_total, tokens_kept}` where `rate = dropped_cause / (dropped_total + tokens_kept)` (denominator = all raw candidate tokens, so rates are shares of input). `url_removed`/`email_removed` reported as counts only (they vanish before tokenization — a rate over tokens would mislead). `add_paradigm_batch` excluded (dictionary-derived forms, never raw text) — noted in summary output as `paradigm_docs_excluded: true`.

**Builder:** extend `build_summary.json` (`builder.py:267-279`) with the writer's `audit_rates` verbatim under key `"audit_rates"`. No schema break — additive key; parquet GT schema untouched.

**Streaming/memory:** counters only, O(1) per doc. No full-corpus buffering.

**Tests:** synthetic dirty paragraph with known composition (e.g. 8 Polish + 2 foreign + 1 numeric + 1 URL) through `BalancedCorpusWriter` + `tmp_path` → assert exact counter values and rate arithmetic; `build_summary.json` key presence asserted via quick-test build.

## 2. VER-01 — Fixture consolidation: what exists vs what to pin

Audit §2 has 14 rows. Coverage today: `Béziera`/`café` (01-01), 11 more (`Schrödinger`, `Besançon`, `Turčianske`, `Corrèze`, `Hübner`, `Maréchal`, `désintéressement`, `Führer`, `naïve`, `Linköping`, `Saint-Étienne-la-Geneste`) + numerics (01-02) — i.e. all 14 inputs are asserted at `clean_text()` level. The consolidation task is NOT re-adding cases; it is:
1. **Audit-trace:** every audit §2 row maps to explicit test IDs (test-name comments referencing the audit row), so a future reader can verify completeness mechanically.
2. **Validator-level pins at the right level:** assert non-generation, not invalidity — `ziera`/`caf`/`COVID` are Polish-class strings, so `is_valid_token("ziera")` correctly returns True; the guarantee is `tokenize(clean_text("Béziera")) == []` and `"ziera" not in tokenize(...)`. Pin the no-salvage property per row (no `B`, `H`, `tienne-la` orphans).
3. **Gap-fill only true gaps:** source-hardening paths (URL/email/boilerplate already covered in 02); any audit-row variant missing (e.g. `Anthé`, `Turčianske Teplice` multiword, `Mein Führer` phrase) gets added as whole-string cases.

## 3. VER-02 — Full-tier rebuild gate: scope and script

**Gate tier: compact** (4.4k docs / 2.2M tokens, `TIERS` in `config.py:97-108`). Rationale: smallest full tier that exercises real cached sources end-to-end (NKJP 13MB, news 38MB, literature dir, full 47MB PoliMorf ingest); recommended (10.1k docs) proves nothing more about fragment-absence and costs multiples. `data_cache/wiki_pl.jsonl` is absent → wikipedia genre falls back to numbered seed docs (clean by construction); the gate script reports per-genre doc origins so seed-fallback is visible, not hidden.

**Gate script** `scripts/verify_zero_fragments.py` (stdlib + `pyarrow`, already a runtime dep): opens `dist/compact/corpus.zip`, re-tokenizes every stored doc with shared `tokenize()`, asserts (a) every token passes `is_valid_token`, (b) no char outside the Polish class survives in doc text, (c) re-tokenized counts reproduce writer TF/DF (stored/counts agreement at scale); scans `ground_truth.parquet` word column the same way. Prints per-genre fragment counts + rates, exits nonzero on any fragment. Reads `build_summary.json` audit rates as the acceptance signal (criterion 2) and cross-checks script-measured vs writer-reported rates agree.

**Runtime notes:** full PoliMorf ingest + 4.4k-doc build + 5k-lemma paradigms is a tens-of-minutes run; `ensure_all_text_sources` per-source try/except already degrades missing wiki to seed fallback (no hang risk beyond normal downloads — all other sources are cached). Run with generous timeout; network only needed if cache gaps appear (none expected except wiki, which degrades).

## 4. Edge cases planner must handle

- `chunk_text_stream` also calls `clean_text` for sizing — writer must count audit from its own `audit_clean` call only (sizing-path drops are not stored docs; double counting would inflate rates). No change to chunk path.
- Empty-after-clean docs return `""` without consuming quota (`corpus_sampler.py:77-81`) — audit counters still record their drops (input tokens were considered), but no doc slot; rates stay input-honest.
- `html.unescape` can fuse adjacent text into URLs/emails post-decode — `subn` counts post-decode removals, consistent with what actually vanished.
- Full gates both plans share: `pytest tests/ -q`, `ruff check src/ tests/`.
