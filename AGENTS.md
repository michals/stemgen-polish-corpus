<!-- GSD:project-start source:PROJECT.md -->

## Project

**Corpus Quality Hardening**

Hardening pass on `stemgen-polish-corpus` (per `quality-audit.md`): add a real text-cleaning
stage, align token counting, and harden sources so foreign diacritics and other
noise stop leaking into the `corpus.zip` files stemgen trains on. GT quality issues are
documented in a handoff file for the upstream project, not fixed here. For the stemgen
project (Michał), validated by a full-tier rebuild with audit stats showing zero foreign fragments.

**Core Value:** Corpus docs contain only valid Polish word tokens — no truncated foreign
fragments for stemgen to train on.

### Constraints

- **Compatibility**: `corpus.zip` layout (`{genre}/doc_*.txt` hierarchy) must stay consumable by
  `stemgen build --corpus`; ground-truth parquet schema (`word, lemma, tf, df`) stays compatible
  unless explicitly versioned — benchmark/split consumers rely on it
- **Correctness**: stored doc text and TF/DF counts must agree (clean before both write and count)
- **Performance**: cleaning must stream (no full-corpus in-memory); full-tier builds stay practical
- **Scope**: Phases A–D only (cleaning, tokenizer, GT hygiene, source hardening)

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- Python >=3.10 (developed/tested on 3.11.12) - All pipeline code in `src/polish_corpus/`
- None - pure-Python project, no JS/TS/Rust extensions

## Runtime

- CPython 3.10+ (type hints use `from __future__ import annotations` + `X | None` syntax in `src/polish_corpus/cli.py`, `src/polish_corpus/builder.py`, `src/polish_corpus/fetchers.py`)
- uv (recommended per `README.md`) with `uv.lock` committed; also supports std `pip` + `venv`
- Lockfile: present (`uv.lock`)
- Build backend: `hatchling` (`[build-system]` in `pyproject.toml`), wheel packages `src/polish_corpus`

## Frameworks

- Standard library only for pipeline logic - `argparse` (CLI), `urllib.request` (downloads), `gzip`/`zipfile`/`csv`/`json` (parsing), `pathlib`/`dataclasses`/`collections`/`random` (core logic)
- No web framework, no ORM, no async framework
- pytest >=8.0.0 (resolved 9.1.1 in `uv.lock`) - Config: `[tool.pytest.ini_options]` in `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["src"]`)
- Smoke test: `tests/test_smoke.py` (runs `--quick-test` build)
- ruff >=0.8.0 (resolved 0.17.0 in `uv.lock`) - lint + format; config in `pyproject.toml` (`line-length = 100`, `target-version = "py310"`, rules `["E", "F", "UP", "B", "SIM", "I"]`)
- hatchling - wheel build backend
- Console script: `stemgen-polish-corpus = "polish_corpus.cli:main"` (`[project.scripts]`), dual entry via `src/polish_corpus/__main__.py` (`python -m polish_corpus`)

## Key Dependencies

- pyarrow >=14.0.0 (resolved 25.0.1 on py3.10 / 26.0.0 on py3.11+ per `uv.lock` markers) - ONLY runtime dependency; used in `src/polish_corpus/benchmark_splitter.py:80-103` (`export_records_to_parquet`) to write `ground_truth*.parquet` tables with `zstd` compression, schema `(word: string, lemma: string, tf: int64, df: int64)`
- None - no database driver, no cloud SDK, no HTTP client library (uses stdlib `urllib.request` with custom `User-Agent: stemgen-polish-corpus/1.0` in `src/polish_corpus/fetchers.py:32-33`)
- `pytest` pulls `pluggy`, `packaging`, `iniconfig`, `pygments`, `exceptiongroup`, `tomli`, `colorama` (see `uv.lock`)

## Configuration

- Single env var override: `POLISH_CORPUS_CACHE` - custom cache dir; resolution order in `src/polish_corpus/config.py:13-19`: env var → `./data_cache` (repo root, if exists) → `./data_cache` (cwd)
- Output base defaults to `./dist` (cwd-resolved) in `src/polish_corpus/config.py:21`; per-tier nesting via `get_default_output_dir()` in `src/polish_corpus/config.py:24-26`
- CLI flags override config: `--tier {compact,recommended,extended}`, `--output-dir`, `--polimorf-path`, `--quick-test`, `--force-download` (`src/polish_corpus/cli.py:19-45`)
- No `.env` file present or required; no secrets of any kind
- `pyproject.toml` - project metadata, dependencies, hatchling wheel target, pytest + ruff config
- `uv.lock` - pinned resolution (version 1, revision 3)

## Platform Requirements

- Python >=3.10, `uv` (or `pip`), ~disk for `data_cache/` downloads (NKJP1M, WikiNeural, news CSVs, PoliMorf ~GB-scale)
- Install: `uv pip install -e ".[dev]"`; test: `pytest`
- CLI batch tool, not a service - runs wherever Python 3.10+ runs (macOS/Linux/Windows wheels for pyarrow in `uv.lock`)
- No container/Dockerfile, no CI workflow files detected
- Outputs: `corpus.zip` (stdlib `zipfile.ZIP_DEFLATED` in `src/polish_corpus/corpus_sampler.py:63-66`), `*.parquet` (pyarrow+zstd), `build_summary.json`, `README.md` under `dist/<tier>/`

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Naming Patterns

- All source modules use `snake_case.py` under `src/polish_corpus/`: `builder.py`, `corpus_sampler.py`, `morfeusz_extractor.py`, `paradigm_generator.py`, `benchmark_splitter.py`, `text_sources.py`, `fetchers.py`, `config.py`, `cli.py`, `__init__.py`, `__main__.py`
- Test files use `test_<subject>.py` in `tests/` — currently only `tests/test_smoke.py`
- Generated artifact names use `snake_case` with dots: `ground_truth.parquet`, `build_summary.json`, `corpus.zip`
- Use `snake_case` verbs describing the action: `build_polish_corpus` (`src/polish_corpus/builder.py`), `download_file`, `ensure_all_text_sources` (`src/polish_corpus/fetchers.py`), `create_lemma_stratified_split`, `export_records_to_parquet` (`src/polish_corpus/benchmark_splitter.py`), `complete_paradigms` (`src/polish_corpus/paradigm_generator.py`), `count_words`, `chunk_text_stream` (`src/polish_corpus/corpus_sampler.py`), `parse_polimorf_stream`, `clean_lemma` (`src/polish_corpus/morfeusz_extractor.py`), `get_default_output_dir` (`src/polish_corpus/config.py`)
- Generator/streaming helpers use the `iter_` prefix: `iter_spoken_forum_docs`, `iter_literature_docs`, `iter_news_docs`, `iter_wikipedia_docs` (`src/polish_corpus/text_sources.py`)
- Getter-style resource helpers use the `get_` prefix: `get_polimorf_path`, `get_sjp_odm_path`, `get_snowball_voc_path`, `get_nkjp1m_paths`, `get_news_paths`, `get_wikipedia_path`, `get_literature_dir` (`src/polish_corpus/fetchers.py`)
- Use `snake_case` throughout: `out_dir`, `total_docs_to_generate`, `genre_docs`, `added_docs`, `gt_records`, `train_records` (`src/polish_corpus/builder.py`); `current_doc`, `current_word_count`, `token_counts` (`src/polish_corpus/corpus_sampler.py`)
- Module-level constants are `UPPER_SNAKE_CASE`: `CACHE_DIR`, `DEFAULT_OUTPUT_BASE`, `TIERS`, `GENRE_CONFIG`, `CORE_POS_TAGS`, `POLIMORF_URL`, `LITERATURE_BOOKS`, `TOKEN_RE`, `VALID_WORD_RE` (`src/polish_corpus/config.py`, `src/polish_corpus/corpus_sampler.py`, `src/polish_corpus/morfeusz_extractor.py`)
- Genre directory keys embed ordering prefixes: `"01_nkjp_spoken_forum"`, `"02_nkjp_literature"`, `"03_nkjp_news"`, `"04_wikipedia"`, plus `"99_morfeusz_paradigms"` (`src/polish_corpus/config.py`, `src/polish_corpus/corpus_sampler.py`)
- Use `PascalCase` for classes and dataclasses: `BalancedCorpusWriter` (`src/polish_corpus/corpus_sampler.py`), `MorfeuszDictionary` (`src/polish_corpus/morfeusz_extractor.py`), `TierConfig` (`src/polish_corpus/config.py`)
- Use lowercase record tuples, not model classes, for ground-truth rows: `list[tuple[str, str, int, int]]` meaning `(word, lemma, tf, df)` (`src/polish_corpus/benchmark_splitter.py`, `src/polish_corpus/builder.py`)

## Code Style

- No formatter (black/isort) is configured; Ruff is the only style tool
- `pyproject.toml` sets `[tool.ruff] line-length = 100`, `target-version = "py310"`
- Line length is not enforced as a lint error (`E501` is in the `ignore` list), so keep lines ≤100 by convention
- Tool: `ruff>=0.8.0` (dev dependency in `pyproject.toml`, also in `[dependency-groups] dev`)
- Enabled rules (`pyproject.toml [tool.ruff.lint]`): `select = ["E", "F", "UP", "B", "SIM", "I"]`
- Ignored: `ignore = ["ISC004", "BLE001", "F401", "E501"]` — unused imports and blind-except are tolerated, and long lines are allowed
- Run with: `ruff check src/ tests/`

## Import Organization

- None. `pythonpath = ["src"]` is set in `[tool.pytest.ini_options]` (`pyproject.toml`) so tests import the package as `from polish_corpus.builder import ...` (`tests/test_smoke.py:3-5`)

## Error Handling

- Use defensive `try/except Exception as e` with `print("[Warning] ...")` / `print("[Notice] ...")` fallbacks at orchestration boundaries, never letting one source kill the build:
- Use early `return` for missing optional inputs in generators instead of raising: `if not jsonl_gz_path.exists(): return` (`src/polish_corpus/text_sources.py:25-26`)
- Use `raise ... from err` chaining when re-raising a missing optional dependency:
- Validate CLI inputs via `argparse` (`choices=list(TIERS.keys())`, `type=Path`, `action="store_true"`) rather than manual checks (`src/polish_corpus/cli.py:19-45`)
- Validate file usability with existence + non-empty guards before ingesting: `if polimorf_path and polimorf_path.exists() and polimorf_path.stat().st_size > 0:` (`src/polish_corpus/builder.py:130`), and `if dest_path.exists() and not force and dest_path.stat().st_size > 0:` for cache hits (`src/polish_corpus/fetchers.py:26-28`)

## Logging

- Prefix every progress line with a bracketed component tag: `[CorpusBuilder]`, `[MorfeuszDictionary]`, `[ParadigmGenerator]`, `[Fetchers]`, `[Cache Hit]`, `[Downloading]`, `[Downloaded]`, `[Warning]`, `[Notice]` (see `src/polish_corpus/builder.py`, `src/polish_corpus/fetchers.py`, `src/polish_corpus/morfeusz_extractor.py`, `src/polish_corpus/paradigm_generator.py`)
- Gate verbose progress prints behind a `verbose: bool = True` parameter: `ingest_polimorf(..., verbose=True)` (`src/polish_corpus/morfeusz_extractor.py:63-68`), `complete_paradigms(..., verbose=True)` (`src/polish_corpus/paradigm_generator.py:16-21`)
- Report throughput counters with thousands separators: `f"Processed {total_lines:,} rows: ..."` (`src/polish_corpus/morfeusz_extractor.py:107-112`)

## Comments

- Every module opens with a docstring stating which pipeline step it implements (e.g. `"""Implements Step 2 of general_polish_corpus_strategy.md: ..."""` in `src/polish_corpus/corpus_sampler.py:1-7`)
- Numbered inline comments mark ordered pipeline stages inside long functions (`# 1. Reject invalid orthography`, `# 2. Filter proper nouns BEFORE lowercasing` in `src/polish_corpus/morfeusz_extractor.py:84-96`)
- Ordering-sensitive logic gets an explicit BEFORE/AFTER warning comment: `# Filter proper nouns BEFORE lowercasing (lemma[0].isupper())` (`src/polish_corpus/morfeusz_extractor.py:89-91`) and `# 2. Reject proper nouns BEFORE lowercasing` (`src/polish_corpus/morfeusz_extractor.py:156`)
- Not applicable (Python project). Use PEP 257 docstrings instead: one-line summary for helpers (`"""Download a file with caching."""` in `src/polish_corpus/fetchers.py:24`), multi-line with `Returns:`/`Yields:` detail for public functions (`complete_paradigms` in `src/polish_corpus/paradigm_generator.py:23-27`, `resolve_homonyms` in `src/polish_corpus/morfeusz_extractor.py:192-197`)

## Function Design

- Builders return POSIX exit codes: `build_polish_corpus(...) -> int` returns `0` (`src/polish_corpus/builder.py:283`); `main(argv) -> int` returns that code and `__main__` does `sys.exit(main())` (`src/polish_corpus/cli.py:13`, `src/polish_corpus/__main__.py:8`)
- Download helpers return the resolved `Path` for chaining (`src/polish_corpus/fetchers.py:23-39`)
- Split helpers return plain tuples: `create_lemma_stratified_split(...) -> tuple[list[...], list[...]]` (`src/polish_corpus/benchmark_splitter.py:17-21`); `complete_paradigms(...) -> tuple[int, int]` as `(paradigms_checked, missing_forms_added)` (`src/polish_corpus/paradigm_generator.py:22-27`)
- Streaming producers are `Iterator[str]` generators using `yield` (`src/polish_corpus/text_sources.py`, `chunk_text_stream` in `src/polish_corpus/corpus_sampler.py:28-54`)

## Module Design

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| CLI | Argparse parsing (`--tier`, `--output-dir`, `--polimorf-path`, `--quick-test`, `--force-download`); delegates to builder | `src/polish_corpus/cli.py` |
| Package entry | Re-exports `build_polish_corpus`, `TIERS`, `TierConfig`; defines console script target | `src/polish_corpus/__init__.py` |
| Module entry | `python -m polish_corpus` shim forwarding to `cli.main` | `src/polish_corpus/__main__.py` |
| Orchestrator | 9-step `build_polish_corpus()` pipeline: fetch → ingest dict → stream docs → resolve homonyms → complete paradigms → export GT → split → Snowball annotate → write metadata | `src/polish_corpus/builder.py` |
| Config | Tier definitions, genre shares, POS allowlist, source URLs, cache/output path resolution | `src/polish_corpus/config.py` |
| Fetchers | `urllib`-based `download_file` with `.part` temp + cache-hit skip; per-source getters; `ensure_all_text_sources` with per-source try/except fallback | `src/polish_corpus/fetchers.py` |
| Text sources | Four genre iterators yielding ~500-word docs chunked from cached raw files; NKJP channel-prefix routing | `src/polish_corpus/text_sources.py` |
| Dictionary | `MorfeuszDictionary`: PoliMorf/SJP ingest with proper-noun + POS + orthography filters; homonym resolution; lemma→forms index | `src/polish_corpus/morfeusz_extractor.py` |
| Sampler/Writer | `TOKEN_RE` tokenization; `chunk_text_stream` doc assembly; `BalancedCorpusWriter` streaming zip writer with in-memory TF/DF counters | `src/polish_corpus/corpus_sampler.py` |
| Paradigms | Top-N lemma ranking by corpus TF; missing-form detection; batched writes to `99_morfeusz_paradigms/` | `src/polish_corpus/paradigm_generator.py` |
| Splitter/Export | Lemma-stratified 80/20 split (seed 42); Snowball voc annotation; zstd-compressed parquet export via `pyarrow` | `src/polish_corpus/benchmark_splitter.py` |
| Seed fallback | `generate_seed_documents()` in-builder synthetic Polish paragraphs per genre used in `--quick-test` and as per-genre shortfall filler | `src/polish_corpus/builder.py:41-91` |

## Pattern Overview

- One public orchestrator owns the whole run: `build_polish_corpus()` in `src/polish_corpus/builder.py:94-283` executes steps 1–9 in fixed order; there is no scheduler, queue, or plugin registry.
- Sources are lazy pull iterators (`Iterator[str]` per genre) consumed directly by the writer — no intermediate document store except the output zip.
- All cross-stage state lives in two in-memory structures owned by `BalancedCorpusWriter` (`term_freq: Counter`, `doc_freq: Counter`) plus `MorfeuszDictionary` (`word_to_lemmas`, `lemma_to_forms`, `dominant_lemma`).
- Configuration is static module-level data (`TIERS`, `GENRE_CONFIG`, URL constants) selected by a `tier_name` string, not dependency injection.
- Failure handling is degrade-and-continue: each fetcher call is wrapped in try/except, missing genres fall back to seed documents, missing dictionary falls back to a ~30-entry hardcoded bootstrap list.

## Layers

- Purpose: Parse user intent and run the fixed 9-step build in order
- Location: `src/polish_corpus/cli.py`, `src/polish_corpus/__main__.py`, `src/polish_corpus/builder.py`
- Contains: Argparse definitions, `main(argv) -> int` functions, the `build_polish_corpus()` orchestrator
- Depends on: Config, fetchers, text sources, dictionary, sampler, paradigm generator, splitter
- Used by: Console script `stemgen-polish-corpus`, `python -m polish_corpus`, tests, library callers
- Purpose: Single source of truth for tiers, genres, POS allowlist, remote URLs, filesystem locations
- Location: `src/polish_corpus/config.py`
- Contains: `TierConfig` frozen dataclass, `TIERS` dict (compact/recommended/extended), `GENRE_CONFIG` shares, `CORE_POS_TAGS`, `LITERATURE_BOOKS`, URL constants, `CACHE_DIR` / `DEFAULT_OUTPUT_BASE` resolution, `get_default_output_dir()`
- Depends on: `os.environ` (`POLISH_CORPUS_CACHE` override), `pathlib`
- Used by: Every other module
- Purpose: Materialize remote datasets into `data_cache/` and convert them into clean `Iterator[str]` document streams and an in-memory morphological dictionary
- Location: `src/polish_corpus/fetchers.py`, `src/polish_corpus/text_sources.py`, `src/polish_corpus/morfeusz_extractor.py`
- Contains: `download_file` + `get_*` / `ensure_all_text_sources`; `iter_spoken_forum_docs` / `iter_literature_docs` / `iter_news_docs` / `iter_wikipedia_docs` + `_stream_nkjp_sentences`; `MorfeuszDictionary` + `parse_polimorf_stream` + `clean_lemma`
- Depends on: Config; stdlib only (`urllib`, `gzip`, `csv`, `json`, `re`, `zipfile`) — no HTTP or parsing third-party deps
- Used by: Builder orchestrator only
- Purpose: Chunk paragraphs into ~500-word docs, stream them into `corpus.zip` while counting TF/DF, then derive all output tables from those counters
- Location: `src/polish_corpus/corpus_sampler.py`, `src/polish_corpus/paradigm_generator.py`, `src/polish_corpus/benchmark_splitter.py`
- Contains: `TOKEN_RE`, `count_words`, `chunk_text_stream`, `BalancedCorpusWriter`; `complete_paradigms`; `create_lemma_stratified_split`, `build_snowball_voc_ground_truth`, `export_records_to_parquet`
- Depends on: Config (`GENRE_CONFIG`), dictionary (for lemma lookups), fetchers (Snowball voc path), `pyarrow` (parquet export only)
- Used by: Builder orchestrator only

## Data Flow

### Primary Request Path

### Genre Stream Flow (inside step 4)

- In-memory only, single run scope: `BalancedCorpusWriter.term_freq` / `doc_freq` (`collections.Counter`) accumulate every token while streaming; `MorfeuszDictionary.word_to_lemmas` (`defaultdict(Counter)`), `lemma_to_forms` (`defaultdict(set)`), and `dominant_lemma` (plain dict, filled once by `resolve_homonyms`) carry the lexicon.
- No database, no incremental/checkpoint state; re-running rebuilds everything from `data_cache/` + fresh counters. Filesystem side effects are the output zip (opened once, closed after paradigm completion) and the parquet/JSON/MD artifacts.

## Key Abstractions

- Purpose: Sanitized in-memory morphological lexicon with 1-word→1-lemma resolution and paradigm lookup
- Examples: `src/polish_corpus/morfeusz_extractor.py:52-230`
- Pattern: Ingest-then-resolve two-phase object — `ingest_polimorf()` / `ingest_sjp_odm()` populate bidirectional maps, `resolve_homonyms(lemma_frequency_fn)` collapses to `dominant_lemma`, `get_paradigm(lemma)` serves the completion stage
- Purpose: Single-pass zip writer that is simultaneously the TF/DF statistics accumulator every downstream stage reads
- Examples: `src/polish_corpus/corpus_sampler.py:57-141`
- Pattern: Stateful streaming sink — `add_document()` / `add_documents_for_genre()` / `add_paradigm_batch()` mutate counters as a side effect of writing; `summary()` derives final metrics; must call `close()` after paradigm completion
- Purpose: Uniform `fn(max_docs) -> Iterator[str]` pull interface hiding heterogeneous raw formats (NKJP jsonl.gz, Wolne Lektury txt, news CSVs, WikiNeural jsonl)
- Examples: `src/polish_corpus/text_sources.py:45-164`
- Pattern: Private sentence/paragraph generator closed over cache paths + `chunk_text_stream` re-pass loop (`while count < max_docs`) that re-chunks until the quota is met or the source is exhausted
- Purpose: Declarative sizing knobs — token/doc targets and top-lemma counts per tier; token-share and doc-length targets per genre
- Examples: `src/polish_corpus/config.py:80-116`
- Pattern: Frozen dataclass instances in the `TIERS` dict selected by name string; builder derives per-genre doc quotas as `int(total_docs * share)`
- Purpose: Universal `(word, lemma, tf, df)` row shape shared by full GT, train/test splits, and Snowball annotation
- Examples: `src/polish_corpus/benchmark_splitter.py:17-103`, `src/polish_corpus/builder.py:205-236`
- Pattern: Plain `list[tuple[str, str, int, int]]` threaded through split and `export_records_to_parquet()`, which maps it to a 4-column `pyarrow` table with zstd compression

## Entry Points

- Location: `pyproject.toml:35-36` → `src/polish_corpus/cli.py:13-55`
- Triggers: Installed `pip install -e ".[dev]"` entry point; `stemgen-polish-corpus --tier recommended`, `--quick-test`, etc.
- Responsibilities: Argparse parsing with `recommended` default tier; forwards all flags to `build_polish_corpus()` and returns its exit code
- Location: `src/polish_corpus/__main__.py:1-8`
- Triggers: `python -m polish_corpus --quick-test` / `--tier compact`
- Responsibilities: Thin shim importing `cli.main` and `sys.exit`-ing with its return code; same behavior as the console script
- Location: `src/polish_corpus/builder.py:94-283` (also re-exported from `src/polish_corpus/__init__.py`)
- Triggers: Direct Python import, used by `tests/test_smoke.py:24-39`
- Responsibilities: Full 9-step build with `tier_name`, `output_dir`, `polimorf_path`, `quick_test`, `force_download` parameters; returns `0` on success
- Location: `src/polish_corpus/builder.py:286-293`, `src/polish_corpus/cli.py:13`
- Triggers: `python builder.py` style invocation; test harness calling `main(["--help"])`
- Responsibilities: `builder.main()` delegates to `cli_main()`; covered by the CLI help smoke test

## Architectural Constraints

- **Threading:** Single-threaded synchronous pipeline. No threads, asyncio, or multiprocessing anywhere; downloads, parsing, and zip writes all happen sequentially in `build_polish_corpus()`. Long full-tier builds block the calling process for the entire run.
- **Global state:** Module-level singletons resolved at import time — `CACHE_DIR` (`src/polish_corpus/config.py:13-19`, honors `POLISH_CORPUS_CACHE` env var then `data_cache/` then CWD fallback) and `DEFAULT_OUTPUT_BASE` (`src/polish_corpus/config.py:21`, CWD-anchored `./dist`). `GENRE_CONFIG`, `TIERS`, `CORE_POS_TAGS`, and URL constants are mutable module dicts/sets shared by all callers; per-run mutable state is confined to `BalancedCorpusWriter` and `MorfeuszDictionary` instances.
- **Circular imports:** None at module import time. The only back-edge is a deferred function-level import: `builder.main()` imports `cli.main` inside the function body (`src/polish_corpus/builder.py:286-289`) precisely to avoid a `cli ↔ builder` cycle (`cli.py` imports `build_polish_corpus` at top level). Do not hoist that import to module top.
- **Memory ceiling:** `term_freq`/`doc_freq` Counters and the full `word_to_lemmas`/`lemma_to_forms` maps (millions of entries for full PoliMorf) are held in RAM simultaneously; there is no spill-to-disk or chunked GT export.
- **Network-at-build:** Full (non-`quick_test`) builds require outbound HTTPS to `download.sgjp.pl`, `huggingface.co`, `wolnelektury.pl`, `sjp.pl`, and `raw.githubusercontent.com` unless every artifact is already cached; each fetch degrades independently to seed/local fallback rather than failing the build.

## Anti-Patterns

### Raw text stored but tokenized form counted

### Silent identity-lemma fallback for OOV

## Error Handling

- Per-source fetch guards: `ensure_all_text_sources()` wraps each of the four genre downloads in its own try/except and prints `[Warning]` while continuing (`src/polish_corpus/fetchers.py:94-115`); PoliMorf download failure falls back to local cache then to the bootstrap list (`src/polish_corpus/builder.py:120-154`).
- Cache-hit short-circuit: `download_file()` skips non-empty existing files unless `force=True`, using a `.part` temp file + atomic rename to avoid half-written cache entries (`src/polish_corpus/fetchers.py:23-39`).
- Lenient parsing: `errors="replace"` on all gzip/text opens, header skipping for news CSVs, `#`/short-line skipping for PoliMorf, and `VALID_WORD_RE` orthography rejection (`src/polish_corpus/morfeusz_extractor.py:26-44`, `src/polish_corpus/text_sources.py`).
- Snowball annotation is best-effort: wrapped in try/except that prints `[Notice]` and continues without the file (`src/polish_corpus/builder.py:228-236`).

## Cross-Cutting Concerns

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-fast` for a trivial task inline, with no subagents and no PLAN.md
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
