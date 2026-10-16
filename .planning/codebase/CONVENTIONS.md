---
last_mapped_commit: 02ed6cd4ab60c4be38b5b397c048ebb556d0660c
last_mapped_at: 2026-10-16
---
# Coding Conventions

**Analysis Date:** 2026-10-16

## Naming Patterns

**Files:**
- All source modules use `snake_case.py` under `src/polish_corpus/`: `builder.py`, `corpus_sampler.py`, `morfeusz_extractor.py`, `paradigm_generator.py`, `benchmark_splitter.py`, `text_sources.py`, `fetchers.py`, `config.py`, `cli.py`, `__init__.py`, `__main__.py`
- Test files use `test_<subject>.py` in `tests/` — currently only `tests/test_smoke.py`
- Generated artifact names use `snake_case` with dots: `ground_truth.parquet`, `build_summary.json`, `corpus.zip`

**Functions:**
- Use `snake_case` verbs describing the action: `build_polish_corpus` (`src/polish_corpus/builder.py`), `download_file`, `ensure_all_text_sources` (`src/polish_corpus/fetchers.py`), `create_lemma_stratified_split`, `export_records_to_parquet` (`src/polish_corpus/benchmark_splitter.py`), `complete_paradigms` (`src/polish_corpus/paradigm_generator.py`), `count_words`, `chunk_text_stream` (`src/polish_corpus/corpus_sampler.py`), `parse_polimorf_stream`, `clean_lemma` (`src/polish_corpus/morfeusz_extractor.py`), `get_default_output_dir` (`src/polish_corpus/config.py`)
- Generator/streaming helpers use the `iter_` prefix: `iter_spoken_forum_docs`, `iter_literature_docs`, `iter_news_docs`, `iter_wikipedia_docs` (`src/polish_corpus/text_sources.py`)
- Getter-style resource helpers use the `get_` prefix: `get_polimorf_path`, `get_sjp_odm_path`, `get_snowball_voc_path`, `get_nkjp1m_paths`, `get_news_paths`, `get_wikipedia_path`, `get_literature_dir` (`src/polish_corpus/fetchers.py`)

**Variables:**
- Use `snake_case` throughout: `out_dir`, `total_docs_to_generate`, `genre_docs`, `added_docs`, `gt_records`, `train_records` (`src/polish_corpus/builder.py`); `current_doc`, `current_word_count`, `token_counts` (`src/polish_corpus/corpus_sampler.py`)
- Module-level constants are `UPPER_SNAKE_CASE`: `CACHE_DIR`, `DEFAULT_OUTPUT_BASE`, `TIERS`, `GENRE_CONFIG`, `CORE_POS_TAGS`, `POLIMORF_URL`, `LITERATURE_BOOKS`, `TOKEN_RE`, `VALID_WORD_RE` (`src/polish_corpus/config.py`, `src/polish_corpus/corpus_sampler.py`, `src/polish_corpus/morfeusz_extractor.py`)
- Genre directory keys embed ordering prefixes: `"01_nkjp_spoken_forum"`, `"02_nkjp_literature"`, `"03_nkjp_news"`, `"04_wikipedia"`, plus `"99_morfeusz_paradigms"` (`src/polish_corpus/config.py`, `src/polish_corpus/corpus_sampler.py`)

**Types:**
- Use `PascalCase` for classes and dataclasses: `BalancedCorpusWriter` (`src/polish_corpus/corpus_sampler.py`), `MorfeuszDictionary` (`src/polish_corpus/morfeusz_extractor.py`), `TierConfig` (`src/polish_corpus/config.py`)
- Use lowercase record tuples, not model classes, for ground-truth rows: `list[tuple[str, str, int, int]]` meaning `(word, lemma, tf, df)` (`src/polish_corpus/benchmark_splitter.py`, `src/polish_corpus/builder.py`)

## Code Style

**Formatting:**
- No formatter (black/isort) is configured; Ruff is the only style tool
- `pyproject.toml` sets `[tool.ruff] line-length = 100`, `target-version = "py310"`
- Line length is not enforced as a lint error (`E501` is in the `ignore` list), so keep lines ≤100 by convention

**Linting:**
- Tool: `ruff>=0.8.0` (dev dependency in `pyproject.toml`, also in `[dependency-groups] dev`)
- Enabled rules (`pyproject.toml [tool.ruff.lint]`): `select = ["E", "F", "UP", "B", "SIM", "I"]`
- Ignored: `ignore = ["ISC004", "BLE001", "F401", "E501"]` — unused imports and blind-except are tolerated, and long lines are allowed
- Run with: `ruff check src/ tests/`

## Import Organization

**Order:**
1. `from __future__ import annotations` — present at the top of every module except `__init__.py` and `__main__.py`
2. Standard library (`argparse`, `csv`, `gzip`, `json`, `re`, `random`, `shutil`, `sys`, `time`, `urllib.request`, `zipfile`, `pathlib`, `dataclasses`, `collections`, `collections.abc`)
3. Third-party imports are function-local, never top-level: `import pyarrow` inside `export_records_to_parquet` (`src/polish_corpus/benchmark_splitter.py:80-81`)
4. First-party relative imports (`from .config import ...`, `from .corpus_sampler import ...`) — always relative, never absolute `polish_corpus.x` inside the package

**Path Aliases:**
- None. `pythonpath = ["src"]` is set in `[tool.pytest.ini_options]` (`pyproject.toml`) so tests import the package as `from polish_corpus.builder import ...` (`tests/test_smoke.py:3-5`)

## Error Handling

**Patterns:**
- Use defensive `try/except Exception as e` with `print("[Warning] ...")` / `print("[Notice] ...")` fallbacks at orchestration boundaries, never letting one source kill the build:
  ```python
  try:
      get_nkjp1m_paths(force=force)
  except Exception as e:
      print(f"[Warning] Failed to fetch NKJP1M ({e}). Will fallback to local data/seeds if missing.")
  ```
  (`src/polish_corpus/fetchers.py:97-100`; same shape in `src/polish_corpus/builder.py:121-126` and `src/polish_corpus/builder.py:235-236`)
- Use early `return` for missing optional inputs in generators instead of raising: `if not jsonl_gz_path.exists(): return` (`src/polish_corpus/text_sources.py:25-26`)
- Use `raise ... from err` chaining when re-raising a missing optional dependency:
  ```python
  try:
      import pyarrow as pa
      import pyarrow.parquet as pq
  except ImportError as err:
      raise ImportError(
          "pyarrow is required to export parquet datasets. "
          "Please install it with: pip install pyarrow"
      ) from err
  ```
  (`src/polish_corpus/benchmark_splitter.py:79-86`)
- Validate CLI inputs via `argparse` (`choices=list(TIERS.keys())`, `type=Path`, `action="store_true"`) rather than manual checks (`src/polish_corpus/cli.py:19-45`)
- Validate file usability with existence + non-empty guards before ingesting: `if polimorf_path and polimorf_path.exists() and polimorf_path.stat().st_size > 0:` (`src/polish_corpus/builder.py:130`), and `if dest_path.exists() and not force and dest_path.stat().st_size > 0:` for cache hits (`src/polish_corpus/fetchers.py:26-28`)

## Logging

**Framework:** `print` to stdout only. No `logging` module, no log files.

**Patterns:**
- Prefix every progress line with a bracketed component tag: `[CorpusBuilder]`, `[MorfeuszDictionary]`, `[ParadigmGenerator]`, `[Fetchers]`, `[Cache Hit]`, `[Downloading]`, `[Downloaded]`, `[Warning]`, `[Notice]` (see `src/polish_corpus/builder.py`, `src/polish_corpus/fetchers.py`, `src/polish_corpus/morfeusz_extractor.py`, `src/polish_corpus/paradigm_generator.py`)
- Gate verbose progress prints behind a `verbose: bool = True` parameter: `ingest_polimorf(..., verbose=True)` (`src/polish_corpus/morfeusz_extractor.py:63-68`), `complete_paradigms(..., verbose=True)` (`src/polish_corpus/paradigm_generator.py:16-21`)
- Report throughput counters with thousands separators: `f"Processed {total_lines:,} rows: ..."` (`src/polish_corpus/morfeusz_extractor.py:107-112`)

## Comments

**When to Comment:**
- Every module opens with a docstring stating which pipeline step it implements (e.g. `"""Implements Step 2 of general_polish_corpus_strategy.md: ..."""` in `src/polish_corpus/corpus_sampler.py:1-7`)
- Numbered inline comments mark ordered pipeline stages inside long functions (`# 1. Reject invalid orthography`, `# 2. Filter proper nouns BEFORE lowercasing` in `src/polish_corpus/morfeusz_extractor.py:84-96`)
- Ordering-sensitive logic gets an explicit BEFORE/AFTER warning comment: `# Filter proper nouns BEFORE lowercasing (lemma[0].isupper())` (`src/polish_corpus/morfeusz_extractor.py:89-91`) and `# 2. Reject proper nouns BEFORE lowercasing` (`src/polish_corpus/morfeusz_extractor.py:156`)

**JSDoc/TSDoc:**
- Not applicable (Python project). Use PEP 257 docstrings instead: one-line summary for helpers (`"""Download a file with caching."""` in `src/polish_corpus/fetchers.py:24`), multi-line with `Returns:`/`Yields:` detail for public functions (`complete_paradigms` in `src/polish_corpus/paradigm_generator.py:23-27`, `resolve_homonyms` in `src/polish_corpus/morfeusz_extractor.py:192-197`)

## Function Design

**Size:** Keep functions single-purpose and short. Small pure helpers (`clean_lemma`, `count_words`, `chunk_text_stream`, `get_default_output_dir`) are under 15 lines; the only large function is the `build_polish_corpus` orchestrator (~190 lines, `src/polish_corpus/builder.py:94-283`), which is organized into 9 numbered stages — add new pipeline stages there, not in helpers.

**Parameters:** Use keyword-friendly signatures with defaults for everything optional: `build_polish_corpus(tier_name="recommended", output_dir=None, polimorf_path=None, quick_test=False, force_download=False)` (`src/polish_corpus/builder.py:94-100`); `download_file(url, dest_path, force=False)` (`src/polish_corpus/fetchers.py:23`); `complete_paradigms(writer, morfeusz, top_n_lemmas=10_000, batch_size=1_500, verbose=True)` (`src/polish_corpus/paradigm_generator.py:16-21`). Accept `Path | str | None` for directory args and normalize with `Path(output_dir)` at the top (`src/polish_corpus/builder.py:103`).

**Return Values:** Return values, not side-channel state:
- Builders return POSIX exit codes: `build_polish_corpus(...) -> int` returns `0` (`src/polish_corpus/builder.py:283`); `main(argv) -> int` returns that code and `__main__` does `sys.exit(main())` (`src/polish_corpus/cli.py:13`, `src/polish_corpus/__main__.py:8`)
- Download helpers return the resolved `Path` for chaining (`src/polish_corpus/fetchers.py:23-39`)
- Split helpers return plain tuples: `create_lemma_stratified_split(...) -> tuple[list[...], list[...]]` (`src/polish_corpus/benchmark_splitter.py:17-21`); `complete_paradigms(...) -> tuple[int, int]` as `(paradigms_checked, missing_forms_added)` (`src/polish_corpus/paradigm_generator.py:22-27`)
- Streaming producers are `Iterator[str]` generators using `yield` (`src/polish_corpus/text_sources.py`, `chunk_text_stream` in `src/polish_corpus/corpus_sampler.py:28-54`)

## Module Design

**Exports:** Define the public surface explicitly in `src/polish_corpus/__init__.py` with both imports and `__all__` (`build_polish_corpus`, `TIERS`, `TierConfig`, `DEFAULT_OUTPUT_BASE`, `get_default_output_dir`, `__version__`). Internals (seed texts, `_stream_nkjp_sentences`, `_line_iterator`) stay module-private; nested underscore closures are the norm for per-call paragraph sources (`_sentences()`, `_articles()`, `_paragraphs()` in `src/polish_corpus/text_sources.py`).

**Barrel Files:** `src/polish_corpus/__init__.py` is the only barrel — re-export only the orchestrator entry point and config, not every submodule. Import sibling modules relatively from inside the package (`from .builder import ...`, `from .config import ...`).

**Type annotations:** Annotate all public signatures with `from __future__ import annotations` + PEP 604 unions (`Path | str | None`, `int | None`) and builtin generics (`dict[str, Counter[str]]`, `list[tuple[str, str, int, int]]`, `Callable[[str], int] | None`). Keep `dict`/`Counter`/`set` attribute annotations on stateful classes (`MorfeuszDictionary.__init__` in `src/polish_corpus/morfeusz_extractor.py:55-61`, `BalancedCorpusWriter.__init__` in `src/polish_corpus/corpus_sampler.py:60-71`).

---

*Convention analysis: 2026-10-16*
