---
last_mapped_commit: 02ed6cd4ab60c4be38b5b397c048ebb556d0660c
last_mapped_at: 2026-10-16
---
# Codebase Structure

**Analysis Date:** 2026-10-16

## Directory Layout

```
stemgen-polish-corpus/
├── src/polish_corpus/   # Sole Python package (all pipeline code)
│   ├── __init__.py          # Public re-exports + __version__
│   ├── __main__.py          # `python -m polish_corpus` shim
│   ├── cli.py               # Argparse entrypoint
│   ├── builder.py           # 9-step build orchestrator + seed docs
│   ├── config.py            # Tiers, genres, URLs, paths, POS allowlist
│   ├── fetchers.py          # Download + cache layer
│   ├── text_sources.py      # 4 genre iterators
│   ├── morfeusz_extractor.py# Dictionary ingest + homonym resolution
│   ├── corpus_sampler.py    # Chunker + zip writer + TF/DF counters
│   ├── paradigm_generator.py# Top-lemma inflection completion
│   └── benchmark_splitter.py# 80/20 split + Snowball annotate + parquet export
├── tests/               # Pytest suite (single smoke file)
│   └── test_smoke.py        # Tier config, quick-test E2E, CLI help
├── data_cache/          # Downloaded raw sources (gitignored, local-only)
├── output/              # Local test builds (e.g. output/general/)
├── dist/                # Default tier output root `./dist/<tier>/` (created on build)
├── .planning/           # GSD planning docs (incl. .planning/codebase/)
├── quality-audit.md     # 2026-10-16 foreign-diacritic/data-quality audit
├── pyproject.toml       # Build (hatchling), deps, scripts, pytest/ruff config
├── uv.lock              # Pinned dependency lockfile
├── README.md            # Features, tiers, install, usage, output schema
└── LICENSE              # BSD-3-Clause
```

Total package size is small: 11 files, ~1,315 lines (`wc -l src/polish_corpus/*.py`), largest being `builder.py` (293 lines) and `morfeusz_extractor.py` (230 lines).

## Directory Purposes

**`src/polish_corpus/`:**
- Purpose: The entire application — flat single-package pipeline, no subpackages
- Contains: 11 `.py` modules; orchestration (`builder.py`, `cli.py`), config (`config.py`), ingest (`fetchers.py`, `text_sources.py`, `morfeusz_extractor.py`), accumulation/post-process (`corpus_sampler.py`, `paradigm_generator.py`, `benchmark_splitter.py`), entries (`__init__.py`, `__main__.py`)
- Key files: `src/polish_corpus/builder.py` (orchestrator — start here), `src/polish_corpus/config.py` (all knobs), `src/polish_corpus/cli.py` (flags)

**`tests/`:**
- Purpose: Pytest suite, currently one smoke file with 4 tests
- Contains: `test_smoke.py` only — no fixtures, factories, or helpers directories
- Key files: `tests/test_smoke.py`

**`data_cache/` (generated, gitignored):**
- Purpose: Local download cache for all remote raw sources; read by `text_sources.py` and `morfeusz_extractor.py` via `CACHE_DIR`
- Contains: `nkjp1m_train.jsonl.gz`, `nkjp1m_dev.jsonl.gz`, `news_articles.csv`, `news_test.csv`, `wiki_pl.jsonl`, `literature/*.txt` (7 Wolne Lektury books), `polimorf-20260823.tab.gz`, `sjp_odm.zip`, `snowball_voc.txt`
- Key files: None checked in — populated on first full build or via individual `get_*` fetchers

**`output/` and `dist/`:**
- Purpose: Build outputs. `dist/<tier>/` is the default target (`DEFAULT_OUTPUT_BASE`); `output/` holds ad-hoc local builds (e.g. `output/general/` from test runs)
- Contains per-tier: `corpus.zip`, `ground_truth.parquet`, `ground_truth_train.parquet`, `ground_truth_test.parquet`, `snowball_voc_ground_truth.parquet`, `build_summary.json`, `README.md`
- Generated: Yes; committed: No (both gitignored build artifacts)

**`.planning/`:**
- Purpose: GSD planning state and codebase maps
- Contains: `codebase/ARCHITECTURE.md`, `codebase/STRUCTURE.md` (this map), plus phase/milestone state
- Generated: Partially (maps); committed: Yes

## Key File Locations

**Entry Points:**
- `src/polish_corpus/cli.py`: `main(argv) -> int` argparse entrypoint (console script target)
- `src/polish_corpus/__main__.py`: `python -m polish_corpus` shim
- `src/polish_corpus/__init__.py`: Library surface (`build_polish_corpus`, `TIERS`, `TierConfig`, `get_default_output_dir`)
- `pyproject.toml:35-36`: `[project.scripts]` wiring `stemgen-polish-corpus = "polish_corpus.cli:main"`

**Configuration:**
- `src/polish_corpus/config.py`: All tiers, genre shares, POS tags, source URLs, `CACHE_DIR` resolution (`POLISH_CORPUS_CACHE` env override), `get_default_output_dir()`
- `pyproject.toml`: Package metadata, `pyarrow` runtime dep, `pytest`/`ruff` dev deps, `[tool.pytest.ini_options]` (`testpaths`, `pythonpath`), `[tool.ruff]` (line-length 100, py310)

**Core Logic:**
- `src/polish_corpus/builder.py`: `build_polish_corpus()` + `generate_seed_documents()` — read this first for data flow
- `src/polish_corpus/morfeusz_extractor.py`: `MorfeuszDictionary`, `parse_polimorf_stream()`, `clean_lemma()`
- `src/polish_corpus/corpus_sampler.py`: `BalancedCorpusWriter`, `chunk_text_stream()`, `TOKEN_RE`, `count_words()`
- `src/polish_corpus/text_sources.py`: `iter_spoken_forum_docs()`, `iter_literature_docs()`, `iter_news_docs()`, `iter_wikipedia_docs()`
- `src/polish_corpus/fetchers.py`: `download_file()`, `get_*_path()`, `ensure_all_text_sources()`
- `src/polish_corpus/paradigm_generator.py`: `complete_paradigms()`
- `src/polish_corpus/benchmark_splitter.py`: `create_lemma_stratified_split()`, `build_snowball_voc_ground_truth()`, `export_records_to_parquet()`

**Testing:**
- `tests/test_smoke.py`: All 4 tests (package exports, default output dir, `--quick-test` E2E into `tmp_path`, CLI `--help`)

**Docs / Audits:**
- `README.md`: Features, corpus tiers table, install, usage, output schema, licensing
- `quality-audit.md`: Foreign-diacritic root-cause analysis + phased remediation plan ( Phases A–D) — required reading before touching tokenization or GT export

## Naming Conventions

**Files:**
- `snake_case` descriptive module names matching their single responsibility: `corpus_sampler.py`, `morfeusz_extractor.py`, `paradigm_generator.py`, `benchmark_splitter.py`, `text_sources.py`, `fetchers.py`, `builder.py`, `config.py`, `cli.py`. Test file mirrors the scope it covers: `test_smoke.py` (not per-module `test_*.py`).

**Directories:**
- `snake_case` package name `polish_corpus`; genre output dirs use zero-padded numeric prefixes enforcing sort order: `01_nkjp_spoken_forum`, `02_nkjp_literature`, `03_nkjp_news`, `04_wikipedia`, `99_morfeusz_paradigms`. Cache files keep upstream names (`nkjp1m_train.jsonl.gz`, `polimorf-20260823.tab.gz`).

**Symbols (follow these when adding code):**
- Public functions are verb-led: `build_polish_corpus`, `ensure_all_text_sources`, `download_file`, `get_polimorf_path` / `get_*_path`, `iter_*_docs`, `chunk_text_stream`, `count_words`, `complete_paradigms`, `create_lemma_stratified_split`, `export_records_to_parquet`, `clean_lemma`, `parse_polimorf_stream`, `generate_seed_documents`, `get_default_output_dir`.
- Classes are nouns: `MorfeuszDictionary`, `BalancedCorpusWriter`, `TierConfig`.
- Module constants are `UPPER_SNAKE`: `TIERS`, `GENRE_CONFIG`, `CORE_POS_TAGS`, `CACHE_DIR`, `TOKEN_RE`, `VALID_WORD_RE`, `*_URL`, `LITERATURE_BOOKS`, `DEFAULT_OUTPUT_BASE`.
- Genre string keys (`"01_nkjp_spoken_forum"`, …) must match exactly across `GENRE_CONFIG`, `genre_streams` in `builder.py:163-168`, the seed dict in `generate_seed_documents()`, and the zip directory names written by the sampler.

## Where to Add New Code

**New pipeline stage (e.g. text cleaning / normalization):**
- Primary code: new module in `src/polish_corpus/` (e.g. `src/polish_corpus/text_cleaning.py` per `quality-audit.md` §5 Phase A), called from `build_polish_corpus()` in `src/polish_corpus/builder.py` at the correct step index; shared validators live next to `TOKEN_RE` in `src/polish_corpus/corpus_sampler.py` or a new shared module imported by both sampler and `morfeusz_extractor.py`.
- Tests: extend `tests/test_smoke.py` or add `tests/test_<stage>.py` (pytest discovers `testpaths = ["tests"]` with `pythonpath = ["src"]`).

**New genre / text source:**
- URL constant + cache filename in `src/polish_corpus/config.py` (`*_URL`, extend `GENRE_CONFIG` with `{"share": ..., "target_doc_words": 500}`); getter in `src/polish_corpus/fetchers.py` plus a call in `ensure_all_text_sources()`; iterator `iter_<genre>_docs(max_docs)` in `src/polish_corpus/text_sources.py` reusing `chunk_text_stream`; registration in the `genre_streams` dict in `src/polish_corpus/builder.py:163-168` and seed texts in `generate_seed_documents()`.

**New dictionary / lexicon ingestor:**
- Method on `MorfeuszDictionary` in `src/polish_corpus/morfeusz_extractor.py` (e.g. `ingest_*`), following the `ingest_polimorf` pattern (orthography check → proper-noun filter before lowercasing → `CORE_POS_TAGS` gate → populate both maps); wire the fallback chain in `src/polish_corpus/builder.py:128-154`.

**New output artifact:**
- Export helper next to `export_records_to_parquet()` in `src/polish_corpus/benchmark_splitter.py`; invocation + summary/`README.md` lines in `src/polish_corpus/builder.py` steps 6–9; expected-file assertion in `tests/test_smoke.py::test_quick_test_run`.

**Utilities:**
- Shared helpers: `src/polish_corpus/config.py` for constants/paths; small pure functions (tokenization, cleaning, counting) alongside `TOKEN_RE` in `src/polish_corpus/corpus_sampler.py` until they warrant their own module.

## Special Directories

**`data_cache/`:**
- Purpose: Raw download cache (NKJP, news, Wikipedia, literature, PoliMorf, SJP, Snowball voc)
- Generated: Yes (populated by `fetchers.py` on first full build)
- Committed: No (gitignored)

**`output/` / `dist/`:**
- Purpose: Per-tier build outputs (`corpus.zip`, `*.parquet`, `build_summary.json`, `README.md`)
- Generated: Yes (created by `build_polish_corpus()`)
- Committed: No (build artifacts)

**`.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`:**
- Purpose: Virtualenv, bytecode, test/lint caches
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-10-16*
