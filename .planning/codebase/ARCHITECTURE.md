---
last_mapped_commit: 02ed6cd4ab60c4be38b5b397c048ebb556d0660c
last_mapped_at: 2026-10-16
---
<!-- refreshed: 2026-10-16 -->

# Architecture

**Analysis Date:** 2026-10-16

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                      Entry / Orchestration                   │
├──────────────────┬──────────────────┬───────────────────────┤
│   CLI            │  Package shim    │  Builder (orchestrator)│
│  `src/polish_corpus/cli.py` │ `src/polish_corpus/__main__.py` │ `src/polish_corpus/builder.py` │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ingest / Source Layer                     │
│  `src/polish_corpus/fetchers.py` (download+cache)            │
│  `src/polish_corpus/text_sources.py` (genre iterators)       │
│  `src/polish_corpus/morfeusz_extractor.py` (dict ingest)     │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│            Sampling / Accumulation / Post-process            │
│  `src/polish_corpus/corpus_sampler.py` (zip + TF/DF)        │
│  `src/polish_corpus/paradigm_generator.py` (TF floor fill)  │
│  `src/polish_corpus/benchmark_splitter.py` (split+export)  │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Outputs (per-tier dir under `./dist/<tier>/` or custom)    │
│  corpus.zip, ground_truth*.parquet, build_summary.json       │
└─────────────────────────────────────────────────────────────┘
```

Static config underpins all layers: `src/polish_corpus/config.py` (URLs, `GENRE_CONFIG`, `TIERS`, `CORE_POS_TAGS`, cache/output paths). No skills directories exist in the repo (no `.claude/skills/` or `.agents/skills/`), so no project-skill constraints apply.

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

**Overall:** Sequential staged batch ETL pipeline with a single orchestrator function and streaming-then-accumulating state.

**Key Characteristics:**
- One public orchestrator owns the whole run: `build_polish_corpus()` in `src/polish_corpus/builder.py:94-283` executes steps 1–9 in fixed order; there is no scheduler, queue, or plugin registry.
- Sources are lazy pull iterators (`Iterator[str]` per genre) consumed directly by the writer — no intermediate document store except the output zip.
- All cross-stage state lives in two in-memory structures owned by `BalancedCorpusWriter` (`term_freq: Counter`, `doc_freq: Counter`) plus `MorfeuszDictionary` (`word_to_lemmas`, `lemma_to_forms`, `dominant_lemma`).
- Configuration is static module-level data (`TIERS`, `GENRE_CONFIG`, URL constants) selected by a `tier_name` string, not dependency injection.
- Failure handling is degrade-and-continue: each fetcher call is wrapped in try/except, missing genres fall back to seed documents, missing dictionary falls back to a ~30-entry hardcoded bootstrap list.

## Layers

**Entry / Orchestration:**
- Purpose: Parse user intent and run the fixed 9-step build in order
- Location: `src/polish_corpus/cli.py`, `src/polish_corpus/__main__.py`, `src/polish_corpus/builder.py`
- Contains: Argparse definitions, `main(argv) -> int` functions, the `build_polish_corpus()` orchestrator
- Depends on: Config, fetchers, text sources, dictionary, sampler, paradigm generator, splitter
- Used by: Console script `stemgen-polish-corpus`, `python -m polish_corpus`, tests, library callers

**Configuration:**
- Purpose: Single source of truth for tiers, genres, POS allowlist, remote URLs, filesystem locations
- Location: `src/polish_corpus/config.py`
- Contains: `TierConfig` frozen dataclass, `TIERS` dict (compact/recommended/extended), `GENRE_CONFIG` shares, `CORE_POS_TAGS`, `LITERATURE_BOOKS`, URL constants, `CACHE_DIR` / `DEFAULT_OUTPUT_BASE` resolution, `get_default_output_dir()`
- Depends on: `os.environ` (`POLISH_CORPUS_CACHE` override), `pathlib`
- Used by: Every other module

**Ingest (fetch + raw text streams + dictionary):**
- Purpose: Materialize remote datasets into `data_cache/` and convert them into clean `Iterator[str]` document streams and an in-memory morphological dictionary
- Location: `src/polish_corpus/fetchers.py`, `src/polish_corpus/text_sources.py`, `src/polish_corpus/morfeusz_extractor.py`
- Contains: `download_file` + `get_*` / `ensure_all_text_sources`; `iter_spoken_forum_docs` / `iter_literature_docs` / `iter_news_docs` / `iter_wikipedia_docs` + `_stream_nkjp_sentences`; `MorfeuszDictionary` + `parse_polimorf_stream` + `clean_lemma`
- Depends on: Config; stdlib only (`urllib`, `gzip`, `csv`, `json`, `re`, `zipfile`) — no HTTP or parsing third-party deps
- Used by: Builder orchestrator only

**Sampling / Accumulation / Post-process:**
- Purpose: Chunk paragraphs into ~500-word docs, stream them into `corpus.zip` while counting TF/DF, then derive all output tables from those counters
- Location: `src/polish_corpus/corpus_sampler.py`, `src/polish_corpus/paradigm_generator.py`, `src/polish_corpus/benchmark_splitter.py`
- Contains: `TOKEN_RE`, `count_words`, `chunk_text_stream`, `BalancedCorpusWriter`; `complete_paradigms`; `create_lemma_stratified_split`, `build_snowball_voc_ground_truth`, `export_records_to_parquet`
- Depends on: Config (`GENRE_CONFIG`), dictionary (for lemma lookups), fetchers (Snowball voc path), `pyarrow` (parquet export only)
- Used by: Builder orchestrator only

## Data Flow

### Primary Request Path

1. Parse CLI args or library kwargs — tier selection, output dir, quick-test flag (`src/polish_corpus/cli.py:13-55`, `src/polish_corpus/builder.py:94-104`)
2. Fetch/cache remote sources, unless `quick_test=True` skips all downloads (`src/polish_corpus/builder.py:115-126`, `src/polish_corpus/fetchers.py:94-115`)
3. Ingest morphological dictionary: PoliMorf tab.gz → SJP odm.zip → hardcoded bootstrap fallback (`src/polish_corpus/builder.py:128-154`, `src/polish_corpus/morfeusz_extractor.py:63-186`)
4. Stream balanced genre documents into `corpus.zip` via `BalancedCorpusWriter`, filling per-genre quotas from `GENRE_CONFIG` shares; shortfalls filled with synthetic seed docs (`src/polish_corpus/builder.py:156-185`, `src/polish_corpus/text_sources.py`, `src/polish_corpus/corpus_sampler.py:73-107`)
5. Resolve homonyms: `word → dominant lemma` using accumulated corpus lemma frequencies (`src/polish_corpus/builder.py:187-189`, `src/polish_corpus/morfeusz_extractor.py:188-226`)
6. Complete paradigms for top-N lemmas: missing inflected forms written to `99_morfeusz_paradigms/` with TF≥1/DF≥1 floor (`src/polish_corpus/builder.py:191-195`, `src/polish_corpus/paradigm_generator.py:16-72`)
7. Build ground-truth records `(word, lemma, tf, df)` from writer counters + dominant-lemma map and export `ground_truth.parquet` (`src/polish_corpus/builder.py:205-215`, `src/polish_corpus/benchmark_splitter.py:74-103`)
8. Lemma-stratified 80/20 split → `ground_truth_train.parquet` / `ground_truth_test.parquet`, all surface forms of a lemma kept together (`src/polish_corpus/builder.py:217-226`, `src/polish_corpus/benchmark_splitter.py:17-50`)
9. Annotate official Snowball `voc.txt` → `snowball_voc_ground_truth.parquet`; write per-tier `README.md` + `build_summary.json` (`src/polish_corpus/builder.py:228-282`, `src/polish_corpus/benchmark_splitter.py:53-71`)

### Genre Stream Flow (inside step 4)

1. Each `iter_*_docs(max_docs)` opens its cached raw file(s) and yields sentences/paragraphs (`src/polish_corpus/text_sources.py:45-164`)
2. `chunk_text_stream(paragraphs, target_words=500, min_words=200/250)` accumulates paragraphs until `>= target_words`, then yields one document string (`src/polish_corpus/corpus_sampler.py:28-54`)
3. `BalancedCorpusWriter.add_documents_for_genre()` caps at the genre quota and calls `add_document()` per doc, which lowercases `TOKEN_RE` matches, updates `term_freq`/`doc_freq`, and `writestr`s to `{genre}/doc_{idx:05d}.txt` (`src/polish_corpus/corpus_sampler.py:73-107`)

**State Management:**
- In-memory only, single run scope: `BalancedCorpusWriter.term_freq` / `doc_freq` (`collections.Counter`) accumulate every token while streaming; `MorfeuszDictionary.word_to_lemmas` (`defaultdict(Counter)`), `lemma_to_forms` (`defaultdict(set)`), and `dominant_lemma` (plain dict, filled once by `resolve_homonyms`) carry the lexicon.
- No database, no incremental/checkpoint state; re-running rebuilds everything from `data_cache/` + fresh counters. Filesystem side effects are the output zip (opened once, closed after paradigm completion) and the parquet/JSON/MD artifacts.

## Key Abstractions

**MorfeuszDictionary:**
- Purpose: Sanitized in-memory morphological lexicon with 1-word→1-lemma resolution and paradigm lookup
- Examples: `src/polish_corpus/morfeusz_extractor.py:52-230`
- Pattern: Ingest-then-resolve two-phase object — `ingest_polimorf()` / `ingest_sjp_odm()` populate bidirectional maps, `resolve_homonyms(lemma_frequency_fn)` collapses to `dominant_lemma`, `get_paradigm(lemma)` serves the completion stage

**BalancedCorpusWriter:**
- Purpose: Single-pass zip writer that is simultaneously the TF/DF statistics accumulator every downstream stage reads
- Examples: `src/polish_corpus/corpus_sampler.py:57-141`
- Pattern: Stateful streaming sink — `add_document()` / `add_documents_for_genre()` / `add_paradigm_batch()` mutate counters as a side effect of writing; `summary()` derives final metrics; must call `close()` after paradigm completion

**Genre iterator functions:**
- Purpose: Uniform `fn(max_docs) -> Iterator[str]` pull interface hiding heterogeneous raw formats (NKJP jsonl.gz, Wolne Lektury txt, news CSVs, WikiNeural jsonl)
- Examples: `src/polish_corpus/text_sources.py:45-164`
- Pattern: Private sentence/paragraph generator closed over cache paths + `chunk_text_stream` re-pass loop (`while count < max_docs`) that re-chunks until the quota is met or the source is exhausted

**TierConfig + GENRE_CONFIG:**
- Purpose: Declarative sizing knobs — token/doc targets and top-lemma counts per tier; token-share and doc-length targets per genre
- Examples: `src/polish_corpus/config.py:80-116`
- Pattern: Frozen dataclass instances in the `TIERS` dict selected by name string; builder derives per-genre doc quotas as `int(total_docs * share)`

**Ground-truth record tuple:**
- Purpose: Universal `(word, lemma, tf, df)` row shape shared by full GT, train/test splits, and Snowball annotation
- Examples: `src/polish_corpus/benchmark_splitter.py:17-103`, `src/polish_corpus/builder.py:205-236`
- Pattern: Plain `list[tuple[str, str, int, int]]` threaded through split and `export_records_to_parquet()`, which maps it to a 4-column `pyarrow` table with zstd compression

## Entry Points

**Console script `stemgen-polish-corpus`:**
- Location: `pyproject.toml:35-36` → `src/polish_corpus/cli.py:13-55`
- Triggers: Installed `pip install -e ".[dev]"` entry point; `stemgen-polish-corpus --tier recommended`, `--quick-test`, etc.
- Responsibilities: Argparse parsing with `recommended` default tier; forwards all flags to `build_polish_corpus()` and returns its exit code

**Module execution `python -m polish_corpus`:**
- Location: `src/polish_corpus/__main__.py:1-8`
- Triggers: `python -m polish_corpus --quick-test` / `--tier compact`
- Responsibilities: Thin shim importing `cli.main` and `sys.exit`-ing with its return code; same behavior as the console script

**Library call `build_polish_corpus()`:**
- Location: `src/polish_corpus/builder.py:94-283` (also re-exported from `src/polish_corpus/__init__.py`)
- Triggers: Direct Python import, used by `tests/test_smoke.py:24-39`
- Responsibilities: Full 9-step build with `tier_name`, `output_dir`, `polimorf_path`, `quick_test`, `force_download` parameters; returns `0` on success

**Standalone `builder.main()` / `cli.main(["--help"])`:**
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

**What happens:** `BalancedCorpusWriter.add_document()` (`src/polish_corpus/corpus_sampler.py:73-91`) writes the untouched `text` via `writestr` but derives TF/DF from `TOKEN_RE.findall(text)`, so foreign diacritics and digits silently split or vanish from statistics while remaining in the archived document.
**Why it's wrong:** Stored docs and `ground_truth.parquet` disagree by construction; truncated fragments become `(word, word)` self-lemma rows downstream (see `quality-audit.md`).
**Do this instead:** Introduce a single `clean_text()` normalization applied before both `writestr` and `TOKEN_RE` counting, and share one `TOKEN_RE` + `is_valid_token()` validator between `src/polish_corpus/corpus_sampler.py` and `src/polish_corpus/morfeusz_extractor.py` as proposed in `quality-audit.md` §5.

### Silent identity-lemma fallback for OOV

**What happens:** Ground-truth construction (`src/polish_corpus/builder.py:207-211`) uses `morfeusz.dominant_lemma.get(word, word)`, so every token absent from the dictionary — proper nouns, fragments, typos — is emitted as a `(word, word)` row indistinguishable from genuine lemmas.
**Why it's wrong:** Trains downstream stemmer models toward identity mappings for noise; flagged as high-severity in `quality-audit.md` §4.
**Do this instead:** Drop OOV rows or emit them with an explicit `lemma=NULL` + `oov_flag` column so consumers can exclude them; add `oov_self_lemma_rate` to `build_summary.json`.

## Error Handling

**Strategy:** Degrade-and-continue with printed notices; only truly fatal errors (e.g. missing `pyarrow` at parquet export) raise.

**Patterns:**
- Per-source fetch guards: `ensure_all_text_sources()` wraps each of the four genre downloads in its own try/except and prints `[Warning]` while continuing (`src/polish_corpus/fetchers.py:94-115`); PoliMorf download failure falls back to local cache then to the bootstrap list (`src/polish_corpus/builder.py:120-154`).
- Cache-hit short-circuit: `download_file()` skips non-empty existing files unless `force=True`, using a `.part` temp file + atomic rename to avoid half-written cache entries (`src/polish_corpus/fetchers.py:23-39`).
- Lenient parsing: `errors="replace"` on all gzip/text opens, header skipping for news CSVs, `#`/short-line skipping for PoliMorf, and `VALID_WORD_RE` orthography rejection (`src/polish_corpus/morfeusz_extractor.py:26-44`, `src/polish_corpus/text_sources.py`).
- Snowball annotation is best-effort: wrapped in try/except that prints `[Notice]` and continues without the file (`src/polish_corpus/builder.py:228-236`).

## Cross-Cutting Concerns

**Logging:** `print()` with bracketed stage prefixes (`[Cache Hit]`, `[Downloading]`, `[MorfeuszDictionary]`, `[CorpusBuilder]`, `[ParadigmGenerator]`, `[Notice]`, `[Warning]`); progress lines every 1M PoliMorf rows / 50k SJP lines. No logging framework, no log levels, no file output.
**Validation:** Two regex gates with different strictness — permissive-split `TOKEN_RE` for corpus counting (`src/polish_corpus/corpus_sampler.py:20`) vs. reject-outright `VALID_WORD_RE` for dictionary ingest (`src/polish_corpus/morfeusz_extractor.py:23`); POS allowlist `CORE_POS_TAGS` plus proper-noun rejection via `lemma[0].isupper()` before lowercasing (`src/polish_corpus/morfeusz_extractor.py:89-98`).
**Authentication:** None. All remote fetches are unauthenticated HTTPS GETs with a static `User-Agent: stemgen-polish-corpus/1.0` header (`src/polish_corpus/fetchers.py:31-33`).

---

*Architecture analysis: 2026-10-16*
