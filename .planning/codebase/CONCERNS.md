---
last_mapped_commit: 02ed6cd4ab60c4be38b5b397c048ebb556d0660c
last_mapped_at: 2026-10-16
---
# Codebase Concerns

**Analysis Date:** 2026-10-16

## Tech Debt

**No text-cleaning / normalization stage (highest-priority debt):**
- Issue: Raw source text flows verbatim from `src/polish_corpus/text_sources.py` into `BalancedCorpusWriter.add_document()` (`src/polish_corpus/corpus_sampler.py:73-91`), which calls `self.zip_file.writestr(filename, text)` on the raw string while computing TF/DF with a narrower regex. There is no NFC enforcement, no `�` / control-char stripping, no quote/dash normalization. The punctuation-spacing fix (`re.sub(r"\s+([,.:;?!])", ...)` in `src/polish_corpus/text_sources.py:40-41,149-150`) covers only a handful of characters.
- Files: `src/polish_corpus/text_sources.py`, `src/polish_corpus/corpus_sampler.py:20,73-91`
- Impact: Stored `corpus.zip` documents and TF/DF counts disagree by construction; downstream stemmer training sees surface forms its own tokenizer would not produce.
- Fix approach: Add a single `clean_text()` (new `src/polish_corpus/text_cleaning.py` or in `corpus_sampler.py`): NFC → strip `�`/control chars → foreign-letter policy → normalize `„ ” « » — –` → collapse whitespace. Apply **before** both `writestr` and `TOKEN_RE` counting. Add unit tests using the truncation table in `quality-audit.md` §2 as fixtures.

**Foreign-diacritics truncation via `TOKEN_RE` (from `quality-audit.md`):**
- Issue: `TOKEN_RE = re.compile(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+(?:-...)?")` (`src/polish_corpus/corpus_sampler.py:20`) and `VALID_WORD_RE` (`src/polish_corpus/morfeusz_extractor.py:23`) accept only ASCII + Polish diacritics. Any foreign letter acts as a split point: `Béziera → B + ziera`, `Schrödinger → Schr + dinger`, `Hübner → H + bner`, `café → caf`, `naïve → na + ve`, `COVID-19 → COVID`. Worst offender is `04_wikipedia` (WikiNeural: `é×43, è×16, ö×14, ...` plus Cyrillic); NKJP/news carry `Maréchal, Führer, Universität`; literature carries French dialogues at full-corpus scale (see `quality-audit.md` §§2–3).
- Files: `src/polish_corpus/corpus_sampler.py:20,83`, `src/polish_corpus/morfeusz_extractor.py:23`
- Impact: Garbage fragments leak into `term_freq`/`doc_freq` and then into `ground_truth.parquet` as self-lemma rows that stemgen learns as identity mappings.
- Fix approach: Decide foreign-text policy first (strict Polish-only drop vs. lenient keep-surface-but-exclude-from-TF/DF — open decision `quality-audit.md` §6.1), then implement one shared `TOKEN_RE` + `is_valid_token()` used by sampler, dictionary ingest, and GT export (Phase A+B in `quality-audit.md` §5).

**OOV self-lemma pollution in ground-truth export:**
- Issue: `builder.py:207-211` falls back to `morfeusz.dominant_lemma.get(word, word)`, so every OOV token — proper noun, foreign fragment, typo — becomes a `(word, word)` identity row. The dictionary filters proper nouns (`morfeusz_extractor.py:91`, `lemma[0].isupper()` before lowercasing) but corpus text is unfiltered, so the two vocabularies diverge by design (`quality-audit.md` §4.1, §4.4).
- Files: `src/polish_corpus/builder.py:207-211`, `src/polish_corpus/morfeusz_extractor.py:85-94`
- Impact: Trains the stemmer toward identity mappings for noise; inflates ground-truth row count with uninformative rows.
- Fix approach: Stop emitting silent `(word, word)` rows — drop them or emit with `lemma=NULL` + `oov_flag` so stemgen can exclude them; filter/flag proper-noun-like OOV at export; add `oov_self_lemma_rate`, `foreign_fragment_rate`, `digit_token_rate` to `build_summary.json` (`quality-audit.md` Phase C).

**Digit / alphanumeric truncation with no policy:**
- Issue: `TOKEN_RE` drops digits (`COVID-19 → COVID`, `model3 → model`). Digit tokens are common in sources (`2012, 1990, 2016, ...`; 20/21 docs in the test `corpus.zip` contain digit tokens). No explicit numeric-token policy exists (`quality-audit.md` §4.2).
- Files: `src/polish_corpus/corpus_sampler.py:20`
- Impact: Silent stem corruption for alphanumeric terms; inconsistent handling between sampler (splits) and dictionary (rejects).
- Fix approach: Explicit digit policy (recommended: drop pure-numeric tokens, strip/flag alphanumerics from TF/DF) and record counts in `build_summary.json`.

**Silent seed fallback masks missing-source failures:**
- Issue: `build_polish_corpus()` (`src/polish_corpus/builder.py:170-183`) fills any shortfall with `generate_seed_documents()` — 8 hardcoded paragraphs repeated 3× plus a `Dokument numer N` suffix. A full-tier build with all sources down would silently produce ~10k near-identical docs and still exit 0.
- Files: `src/polish_corpus/builder.py:41-91,170-185`
- Impact: Genre-balance claims become false; benchmark numbers look valid on garbage input; failure is invisible except a `[Notice]` print.
- Fix approach: Fail loudly when real-source yield is 0 (or below a threshold); cap seed fallback to `quick_test`-only or require an explicit `--allow-seed-fallback` flag; record `seed_doc_fraction` per genre in `build_summary.json`.

**Re-pass duplication loop skews document frequency:**
- Issue: All four `iter_*_docs` functions (`src/polish_corpus/text_sources.py:55-66,89-100,121-132,153-164`) wrap chunking in `while count < max_docs` and re-create the source generator each pass. When the source yields fewer docs than requested, the same content is re-yielded as new `doc_NNNNN.txt` files (`quality-audit.md` §4.6).
- Files: `src/polish_corpus/text_sources.py:45-164`
- Impact: Duplicate documents inflate DF for duplicated terms and distort Zipfian TF/DF the sampler is designed to produce.
- Fix approach: Single-pass iteration only; add a content-hash `seen` set guard or raise/return instead of re-yielding.

**Over-broad NKJP channel-prefix matching risks genre contamination:**
- Issue: `_stream_nkjp_sentences()` (`src/polish_corpus/text_sources.py:23-42`) matches with `clean_tid.startswith(p)`. `iter_news_docs` uses prefix `("1",)` and `iter_literature_docs` uses `("2",)`, which also match `10…`, `11…`, `12…`, `20…`, etc. Spoken prefixes `("6","7","4","sca","Supe")` are narrower but unverified against the real TID scheme.
- Files: `src/polish_corpus/text_sources.py:23-42,51,87,119`
- Impact: Suspected spoken/news/literature bleed across genre directories; genre-quota semantics unreliable.
- Fix approach: Verify TID scheme against `data_cache/nkjp1m_train.jsonl.gz`; switch to exact channel codes or anchored regexes (e.g. `1M_1/...` full segment match); add a test asserting disjoint TID sets per genre on a sample.

**Weak Wolne Lektury boilerplate filtering:**
- Issue: Literature path (`src/polish_corpus/text_sources.py:73-84`) skips only lines containing `Ten utwór nie jest objęty prawem autorskim` / `ISBN ` / `Wolne Lektury` plus a `len(line) > 20` gate. Headers, footers, `Rozdział` markers, page numbers, and verse line-numbers pass through (`quality-audit.md` §4.5).
- Files: `src/polish_corpus/text_sources.py:73-84`
- Impact: Boilerplate tokens pollute TF/DF and ground truth at full-corpus scale.
- Fix approach: Stronger boilerplate patterns (chapter headers, page numbers, repeated front/back matter); strip Gutenberg-style front matter by marker rather than substring.

**Unguarded HTML / entity / URL path in news and wiki ingest:**
- Issue: News CSV path (`src/polish_corpus/text_sources.py:108-116`) assumes `row[1]` is clean article text; wiki path (`src/polish_corpus/text_sources.py:139-151`) assumes `tokens` join is clean. No HTML-unescape, markup, URL, or e-mail stripping anywhere (`quality-audit.md` §4.7).
- Files: `src/polish_corpus/text_sources.py:103-151`
- Impact: Clean in the current small sample but one upstream schema/markup change injects tags/URLs into the corpus with no defense.
- Fix approach: Add `html.unescape` + markup/URL stripping in the shared cleaning stage (Phase D, `quality-audit.md` §5).

**Homonym resolution runs on pre-paradigm frequencies and rewards surface-form match:**
- Issue: `builder.py:189` calls `morfeusz.resolve_homonyms(lemma_frequency_fn=...)` **before** `complete_paradigms()` adds missing forms, so paradigm mass never influences disambiguation. The frequency function (`src/polish_corpus/paradigm_generator.py:33-36` shows the same pattern) looks up `writer.term_freq.get(lem, 0)` — lemmas that never appear as surface forms score 0 and fall through to the `1 if lem == word else 0` tie-break (`src/polish_corpus/morfeusz_extractor.py:205-224`).
- Files: `src/polish_corpus/builder.py:187-193`, `src/polish_corpus/morfeusz_extractor.py:188-226`, `src/polish_corpus/paradigm_generator.py:31-40`
- Impact: Homonym winners for rare/archaic lemmas are effectively arbitrary; paradigm completion then amplifies the arbitrary choice.
- Fix approach: Resolve homonyms after paradigm inventory is known, or score lemmas by summed paradigm-form TF rather than exact-string TF; log homonym decisions with runner-up margins.

**Paradigm-completion docs distort corpus statistics:**
- Issue: `complete_paradigms()` (`src/polish_corpus/paradigm_generator.py:16-72`) holds all missing forms in one in-memory list (up to hundreds of thousands for `extended` top-15k lemmas), then writes space-joined 1,500-form single-line pseudo-documents via `add_paradigm_batch()`. Token counting there (`corpus_sampler.py:120`, `tokens = [t.lower() for t in forms]`) bypasses `TOKEN_RE`, inconsistent with `add_document()` counting. Each batch gets DF=1 for 1,500 unrelated forms, and totals flow into `summary()` indistinguishable from natural text.
- Files: `src/polish_corpus/paradigm_generator.py:45-65`, `src/polish_corpus/corpus_sampler.py:109-126,132-140`
- Impact: TF floor guarantee (`TF≥1, DF≥1`) is met on paper but DF semantics are meaningless for paradigm batches; `total_tokens`/`unique_vocabulary` mix synthetic and natural counts.
- Fix approach: Report paradigm stats separately (`paradigm_forms_added`, `paradigm_batches`) in `build_summary.json`; use `TOKEN_RE` counting in both paths; consider one-form-per-line or lemma-grouped docs instead of 1,500-word megalines.

**Import-time, CWD-dependent path resolution:**
- Issue: `CACHE_DIR` and `DEFAULT_OUTPUT_BASE` are resolved at import time in `src/polish_corpus/config.py:13-21` from `REPO_ROOT` existence or `Path.cwd()`. Importing the installed package from another directory silently changes cache/output locations; `DEFAULT_OUTPUT_BASE` has no env override (only `POLISH_CORPUS_CACHE` exists); the `REPO_ROOT = PACKAGE_DIR.parent.parent` heuristic breaks under `site-packages`.
- Files: `src/polish_corpus/config.py:9-26`
- Impact: Reproducibility and CI surprises — same command writes to different directories depending on invocation CWD.
- Fix approach: Resolve paths lazily via functions, add `POLISH_CORPUS_OUTPUT` env override, and never depend on CWD at import time.

**Fragile `fetchers.download_file` (no timeout / retry / checksum / validation):**
- Issue: `download_file()` (`src/polish_corpus/fetchers.py:23-39`) uses `urllib.request.urlopen(req)` with no timeout, no retry, no checksum, and no size validation; leaves `.part` files on failure; `ensure_all_text_sources()` (`src/polish_corpus/fetchers.py:94-115`) swallows every per-source exception into a `print("[Warning] ...")` and continues to seed fallback.
- Files: `src/polish_corpus/fetchers.py:23-115`
- Impact: CI can hang indefinitely on a stalled download; corrupted/truncated multi-GB downloads are cached as valid (`st_size > 0` is the only check); partial failures are invisible downstream.
- Fix approach: Add timeout + retries with backoff, expected-size/SHA verification where available, atomic temp-then-rename with cleanup, and propagate (or at least count) source failures into `build_summary.json`.

**Unprotected stream parsing — one bad line kills a multi-hour build:**
- Issue: `_stream_nkjp_sentences()` calls `json.loads(line)` with no `try/except` (`src/polish_corpus/text_sources.py:31`); wiki path does the same (`src/polish_corpus/text_sources.py:145`); CSV reading assumes `row[1]` holds article text with no schema check (`src/polish_corpus/text_sources.py:114-116`); `errors="replace"` / `errors="ignore"` decoding (`text_sources.py:27,76,111,141`, `morfeusz_extractor.py:34,140,142`) silently injects `�` or drops bytes (none observed yet per `quality-audit.md` §3, but unguarded).
- Files: `src/polish_corpus/text_sources.py:23-42,103-151`, `src/polish_corpus/morfeusz_extractor.py:26-44,136-144`
- Impact: A single corrupt line in a multi-GB source aborts the entire build; encoding errors become silent data corruption.
- Fix approach: Per-line `try/except json.JSONDecodeError` with a counted skip; validate CSV header/column index; count and report `decode_replacement_rate`.

**`BalancedCorpusWriter` resource and input handling:**
- Issue: `ZipFile(mode="w")` is opened in `__init__` (`src/polish_corpus/corpus_sampler.py:60-67`) with no context-manager support and `close()` is called once at `builder.py:195` outside any `finally` — an exception mid-build leaves a corrupt zip. Unknown genres are silently accepted (`corpus_sampler.py:75-77` creates ghost counters on typo). `chunk_text_stream()` (`corpus_sampler.py:28-54`) silently drops the trailing document if under `min_words` and has no max-words cap, so one huge paragraph becomes one huge doc.
- Files: `src/polish_corpus/corpus_sampler.py:28-54,57-107,128-130`, `src/polish_corpus/builder.py:158-195`
- Impact: Corrupt/partial `corpus.zip` on failure; mistyped genre silently creates a new top-level directory; silent data loss and oversized docs.
- Fix approach: Implement context-manager (`__enter__`/`__exit__`) and use `with` in builder with `try/finally`; validate genre against `GENRE_CONFIG` (raise on unknown); log dropped-tail counts; split or cap oversized paragraphs.

**Dead code and silent drops in split / export paths:**
- Issue: `create_lemma_stratified_split()` (`src/polish_corpus/benchmark_splitter.py:37-39`) computes `set(all_lemmas[split_idx:])` without assigning it — dead expression; the split is lemma-count-based, so train/test *record* counts are unpredictable (one huge lemma falling in test skews the 80/20 claim). `build_snowball_voc_ground_truth()` (`src/polish_corpus/benchmark_splitter.py:62-70`) silently drops voc words lacking `dominant_lemma` (no coverage stat) and lowercases away proper-noun signal. `export_records_to_parquet()` (`src/polish_corpus/benchmark_splitter.py:74-103`) has no empty-records guard and hard-requires `zstd` compression with no fallback for older `pyarrow`.
- Files: `src/polish_corpus/benchmark_splitter.py:17-103`
- Impact: Misleading split ratios; unreported Snowball coverage loss; empty or unreadable parquet on edge inputs.
- Fix approach: Remove dead line; split by record weight or report both lemma- and record-level ratios; emit `snowball_coverage_rate`; guard empty exports; fall back to `snappy`/`none` if `zstd` unavailable.

**Minimal `build_summary.json` — builds are not auditable:**
- Issue: Summary writer (`src/polish_corpus/builder.py:267-279`) records only `tier`, `elapsed_seconds`, and archive `summary`. No source versions/hashes, no seed-fallback fraction, no OOV/foreign/digit rates, no paradigm-vs-natural token split, no per-genre doc/target shortfall (`quality-audit.md` Phase C + §7 call this out explicitly).
- Files: `src/polish_corpus/builder.py:267-279`
- Impact: Two builds cannot be compared; data-quality regressions (e.g. a source going missing and being seed-filled) are undetectable post hoc.
- Fix approach: Add `source_hashes`, `seed_doc_fraction`, `oov_self_lemma_rate`, `foreign_fragment_rate`, `digit_token_rate`, `paradigm_token_split`, per-genre `target_vs_actual`.

**`quick_test` still hits the network; test behavior is non-deterministic:**
- Issue: `build_polish_corpus(quick_test=True)` skips `ensure_all_text_sources()` but still calls `get_polimorf_path()` (`src/polish_corpus/builder.py:119-126`), which downloads unless cached; on failure it falls back to cache, then SJP, then a ~30-row hardcoded bootstrap (`builder.py:137-154`). The smoke test (`tests/test_smoke.py:24-39`) therefore passes with three wildly different dictionaries depending on network/cache state.
- Files: `src/polish_corpus/builder.py:94-154`, `tests/test_smoke.py:24-39`
- Impact: Flaky/slow tests, non-reproducible smoke-test artifacts, bootstrap dictionary too small to exercise homonym/paradigm logic meaningfully.
- Fix approach: Make `quick_test` fully offline (use cache-or-bootstrap, never download); add a tiny committed fixture dictionary for tests; assert dictionary source in the test.

## Known Bugs

**Single-letter and fragment tokens from foreign names (verified):**
- Symptoms: `Hübner → H + bner`, `Führer → F + hrer`, `désintéressement → d + sint + ressement`, `Saint-Étienne-la-Geneste → Saint + tienne-la + Geneste` (full table in `quality-audit.md` §2). Single-letter tokens (`H`, `F`, `d`, `B`) and stopword-like fragments (`on` from `Besançon`) enter TF/DF and ground truth.
- Files: `src/polish_corpus/corpus_sampler.py:20,83`, `src/polish_corpus/builder.py:207-211`
- Trigger: Any document containing non-Polish diacritics (guaranteed at full-corpus scale via WikiNeural `04_wikipedia`).
- Workaround: None in-tree; requires the `clean_text()` + shared-tokenizer fix.

**Dead split-set expression (`benchmark_splitter.py:39`):**
- Symptoms: `set(all_lemmas[split_idx:])` is computed and discarded. Functionally harmless today (the `else` branch collects test records), but it signals an unfinished refactor and will confuse the next editor into thinking test lemmas are materialized.
- Files: `src/polish_corpus/benchmark_splitter.py:37-39`
- Trigger: Code reading / modification.
- Workaround: Assign to `test_lemmas` and branch on membership explicitly.

**`summary()` type annotation is wrong (`dict[str, any]`):**
- Symptoms: `BalancedCorpusWriter.summary()` (`src/polish_corpus/corpus_sampler.py:132`) annotates `dict[str, any]` (builtin `any` function, not `typing.Any`). Works at runtime but defeats type checking.
- Files: `src/polish_corpus/corpus_sampler.py:132`
- Trigger: Static analysis / strict `mypy` runs.
- Workaround: Change to `dict[str, object]` or a `TypedDict`.

## Security Considerations

**No integrity verification for downloaded executable-adjacent data:**
- Risk: PoliMorf/SJP/NKJP/WikiNeural/literature archives are fetched over HTTPS but never checksum-verified; a compromised mirror or MITM with a valid cert yields a poisoned dictionary/corpus that flows straight into stemmer training data.
- Files: `src/polish_corpus/fetchers.py:23-91`, `src/polish_corpus/config.py:29-50`
- Current mitigation: HTTPS only; `st_size > 0` cache check.
- Recommendations: Pin SHA-256 per artifact in `config.py`, verify post-download, refuse to build on mismatch; log hashes into `build_summary.json`.

**Unbounded parsing of remote JSONL/CSV:**
- Risk: `json.loads` on multi-GB HF files, `csv.reader` over full article strings, and `ZipFile`/`gzip` handling have no size caps, no header validation, and `literature/*.txt` is a glob over a writable cache dir — a malicious or malformed cache entry can cause memory exhaustion or log injection via crafted filenames/content.
- Files: `src/polish_corpus/text_sources.py:23-151`, `src/polish_corpus/morfeusz_extractor.py:26-44,136-144`, `src/polish_corpus/fetchers.py:23-39`
- Current mitigation: None beyond `errors="replace"`.
- Recommendations: Per-line size caps and skip-counters, CSV header validation, restrict literature glob to the pinned `LITERATURE_BOOKS` filenames, sanitize logged paths. (No secrets handling observed; no `.env`/credential files exist in-repo — nothing to redact.)

## Performance Bottlenecks

**Full-dictionary + full-vocab in-memory Berliner — extended tier risk:**
- Problem: `MorfeuszDictionary.word_to_lemmas` holds ~4.2M `(form → Counter(lemma))` entries, `lemma_to_forms` the mirrored index, plus `writer.term_freq`/`doc_freq` over ~523k vocab; `complete_paradigms` additionally materializes the full missing-forms list before batching.
- Files: `src/polish_corpus/morfeusz_extractor.py:55-61`, `src/polish_corpus/paradigm_generator.py:45-65`, `src/polish_corpus/builder.py:205-226`
- Cause: No streaming/spilling anywhere; GT record list (`builder.py:207-211`) is also fully materialized before parquet export.
- Improvement path: Stream GT rows to parquet in batches (pyarrow `ParquetWriter`), compute paradigm deltas per lemma without a global missing list, document peak-RAM expectations per tier.

**Single-threaded ingest and sampling:**
- Problem: PoliMorf ingest (4.2M rows with per-row regex + dict inserts), per-document `TOKEN_RE.findall`, and sequential genre streaming are all single-threaded with progress logging only every 1M rows (`morfeusz_extractor.py:107-112`).
- Files: `src/polish_corpus/morfeusz_extractor.py:63-119`, `src/polish_corpus/corpus_sampler.py:73-107`
- Cause: No parallelism, no buffered batching.
- Improvement path: Profile before parallelizing (correctness first); at minimum add throughput logging per genre and consider `multiprocessing` for the PoliMorf parse.

**Network-bound builds with no caching granularity:**
- Problem: `ensure_all_text_sources()` re-downloads whole multi-GB artifacts on any cache miss; `force_download` refetches everything; no resume.
- Files: `src/polish_corpus/fetchers.py:60-115`
- Cause: Single-shot `shutil.copyfileobj` over `urlopen` with no range/resume.
- Improvement path: Per-source fetch with resume support and size pre-checks; document expected download sizes per tier in `README.md`.

## Fragile Areas

**Tokenizer pair (`TOKEN_RE` / `VALID_WORD_RE`):**
- Files: `src/polish_corpus/corpus_sampler.py:20`, `src/polish_corpus/morfeusz_extractor.py:23`
- Why fragile: Two near-identical but semantically different regexes (findall-split vs. fullmatch-reject) define the project's vocabulary in two places; any edit to one without the other re-opens the dictionary/corpus mismatch (`quality-audit.md` §4.4). Hyphen handling (`(?:-...)?` single internal hyphen) is load-bearing for forms like `biało-czerwony`.
- Safe modification: Change both through one shared constant + `is_valid_token()` helper with the `quality-audit.md` §2 table as regression fixtures; run the §7 reproduction scans after any edit.
- Test coverage: None — no tokenizer tests exist.

**Genre stream functions (`text_sources.py`):**
- Files: `src/polish_corpus/text_sources.py:45-164`
- Why fragile: Duplicated while-loop re-pass scaffolding ×4, fragile TID-prefix routing, bare `json.loads`, positional `row[1]` CSV access — four copies of the same failure modes.
- Safe modification: Extract one shared `bounded_stream(chunk_fn, max_docs, dedup=True)` driver; add per-source error counters; test with tiny local fixtures rather than the multi-GB cache.
- Test coverage: None — only exercised via the network-dependent smoke test.

**Dictionary ingest filters (`morfeusz_extractor.py:79-105,146-173`):**
- Files: `src/polish_corpus/morfeusz_extractor.py:63-186`
- Why fragile: Order-dependent (orthography → proper-noun → POS), case-sensitive-before-lowercasing logic, and `clean_lemma` qualifier stripping interact subtly; SJP path additionally rejects bases with spaces and silently skips invalid inflected forms per-row. Small filter changes swing accepted-row counts by millions.
- Safe modification: Log discard-reason counters unconditionally (not just `verbose`), snapshot counts per source in tests, never reorder filters without re-baselining.

**Stratified split (`benchmark_splitter.py:17-50`):**
- Files: `src/polish_corpus/benchmark_splitter.py:17-50`
- Why fragile: Fixed seed 42 with `random.Random`; lemma-count split masquerading as an 80/20 record split; no guard against tiny-test-lemma or empty-split edge cases.
- Safe modification: Assert both splits non-empty; log lemma- and record-level ratios; add a deterministic unit test with a skewed lemma-size fixture.

## Scaling Limits

**Extended tier (25k docs / ~13.4M tokens / top-15k paradigms):**
- Current capacity: Only the 21-doc seed-dominated test build has been observed (`build_summary.json`: 5,768 tokens, 336 vocab per `quality-audit.md` §7) — no full-tier build evidence in-tree.
- Limit: Memory (4.2M-row dictionary + full vocab counters + materialized GT/paradigm lists) and single-threaded throughput; multi-GB downloads on first run.
- Scaling path: Batch parquet writes, per-lemma paradigm deltas, download resume + size pre-checks, then a measured full `compact` build before attempting `recommended`/`extended`.

**Document-frequency semantics under duplication + paradigm batches:**
- Current capacity: DF is a `Counter` over per-doc token sets — correct only if docs are unique natural text.
- Limit: Re-pass duplicates and 1,500-form paradigm megadocs break the DF≈document-count invariant the BM25/benchmark use case depends on.
- Scaling path: Dedup guard + separate paradigm accounting (see Tech Debt above) before any benchmark claims.

## Dependencies at Risk

**`pyarrow` (sole runtime dependency, unpinned upper bound):**
- Risk: `pyproject.toml:15-17` requires `pyarrow>=14.0.0` with no upper pin; `zstd` compression (`benchmark_splitter.py:103`) needs a recent build — older resolvers can install a `pyarrow` that writes unreadable-by-others parquet or lacks `zstd`.
- Impact: Parquet export failure or format drift across environments.
- Migration plan: Pin a known-good range (e.g. `pyarrow>=14,<22`), add compression fallback, and cover export with a unit test that round-trips a small table.

**Unpinned network data sources (no version lock):**
- Risk: PoliMorf/SJP/NKJP/WikiNeural URLs (`config.py:29-40`) are live `resolve/main` / dated-but-unverified endpoints with no hash pin; upstream re-cuts silently change corpora and dictionary contents between builds.
- Impact: Irreproducible builds; benchmark drift with no diff trail.
- Migration plan: Vendor hashes + download-date stamps into `build_summary.json`; prefer content-addressed HF revisions (`resolve/<sha>`) over `main`.

## Missing Critical Features

**Shared text-cleaning + tokenizer module:**
- Problem: No `clean_text()` / shared `TOKEN_RE` / `is_valid_token()` exists; cleaning, validation, and counting are inline and inconsistent (`quality-audit.md` Phase A+B).
- Blocks: Every downstream quality fix (foreign policy, digit policy, OOV hygiene) — all presuppose this module.

**Ground-truth quality telemetry:**
- Problem: No `oov_self_lemma_rate`, `foreign_fragment_rate`, `digit_token_rate`, `snowball_coverage_rate`, or seed-fallback accounting anywhere (`quality-audit.md` Phase C).
- Blocks: Detecting silent data corruption and comparing builds.

**Real test suite beyond the smoke test:**
- Problem: Only `tests/test_smoke.py` (4 tests: tier config, output dir, end-to-end quick run, CLI help) exists; no unit tests for tokenization, chunking, ingest filters, homonym resolution, paradigm completion, splitting, or parquet round-trip.
- Blocks: Safe modification of every fragile area listed above.

## Test Coverage Gaps

**Tokenizer and cleaning (highest priority):**
- What's not tested: `TOKEN_RE` behavior on the `quality-audit.md` §2 table (14 foreign/digit cases), `VALID_WORD_RE` accept/reject boundary, NFC/`�`/control-char handling (which does not exist yet).
- Files: `src/polish_corpus/corpus_sampler.py:20-25`, `src/polish_corpus/morfeusz_extractor.py:23`
- Risk: The core data-quality defect has no regression net; any regex edit ships blind.
- Priority: High

**Chunking and writer accounting:**
- What's not tested: `chunk_text_stream` target/min/max behavior and tail-drop accounting; `add_document` TF/DF agreement with stored text; `add_paradigm_batch` counting consistency with `add_document`; `summary()` totals.
- Files: `src/polish_corpus/corpus_sampler.py:28-140`
- Risk: Silent data loss (dropped tails) and statistic drift go unnoticed.
- Priority: High

**Dictionary ingest and homonym resolution:**
- What's not tested: Proper-noun-before-lowercase filter, qualifier stripping, POS gating, `resolve_homonyms` tie-breaks with and without frequency function.
- Files: `src/polish_corpus/morfeusz_extractor.py:26-230`
- Risk: Million-row-scale filter regressions invisible without fixture-based tests.
- Priority: High

**Split and export correctness:**
- What's not tested: Lemma-stratified zero-shot invariant (no test lemma leaks into train), skewed-lemma-size split ratios, Snowball coverage reporting, parquet schema/round-trip including empty input.
- Files: `src/polish_corpus/benchmark_splitter.py:17-103`
- Risk: Benchmark invalidity (train/test lemma leakage) would go undetected.
- Priority: High

**Source-stream robustness:**
- What's not tested: Corrupt-JSONL-line skipping, CSV schema drift, missing-file behavior, dedup/re-pass behavior, TID genre routing disjointness.
- Files: `src/polish_corpus/text_sources.py`, `src/polish_corpus/fetchers.py`
- Risk: Multi-hour builds fail late on malformed input that a fixture test would have caught.
- Priority: Medium

---

*Concerns audit: 2026-10-16*
