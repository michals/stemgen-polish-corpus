---
last_mapped_commit: 02ed6cd4ab60c4be38b5b397c048ebb556d0660c
last_mapped_at: 2026-10-16
---
# External Integrations

**Analysis Date:** 2026-10-16

## APIs & External Services

**Morphological lexicons (download.sgjp.pl):**
- PoliMorf 20260823 tab.gz - Primary 4.2M-form dictionary source
  - URL: `https://download.sgjp.pl/morfeusz/20260823/polimorf-20260823.tab.gz` (`POLIMORF_URL` in `src/polish_corpus/config.py:30`)
  - Client: stdlib `urllib.request` via `get_polimorf_path()` in `src/polish_corpus/fetchers.py:42-45`, parsed with `gzip` in `src/polish_corpus/morfeusz_extractor.py:34`
  - Auth: none (public HTTPS)
- SGJP 20260823 tab.gz - Defined but UNUSED
  - URL: `https://download.sgjp.pl/morfeusz/20260823/sgjp-20260823.tab.gz` (`SGJP_URL` in `src/polish_corpus/config.py:31`)
  - No fetcher function references it; `grep SGJP_URL src/` hits only `config.py`. Candidate for removal or wiring.
- SJP inflection dump - Fallback dictionary when PoliMorf missing
  - URL: `https://sjp.pl/sl/odmiany/sjp-odm-20260901.zip` (`SJP_ODM_URL` in `src/polish_corpus/config.py:32`)
  - Client: `get_sjp_odm_path()` in `src/polish_corpus/fetchers.py:48-51`, parsed as `odm.txt` inside zip in `src/polish_corpus/morfeusz_extractor.py:138`
  - Auth: none

**Hugging Face datasets (huggingface.co, resolve/main direct links):**
- NKJP1M train/dev (IPAN) - Spoken/forum genre source
  - URLs: `.../ipipan/nkjp1m/.../nkjp1m_train.jsonl.gz`, `.../nkjp1m_dev.jsonl.gz` (`NKJP1M_TRAIN_URL`, `NKJP1M_DEV_URL` in `src/polish_corpus/config.py:36-37`)
  - Client: `get_nkjp1m_paths()` in `src/polish_corpus/fetchers.py:60-66`, streamed in `src/polish_corpus/text_sources.py:23-48`
- Allegro summarization corpus dev/test CSVs - News genre source
  - URLs: `.../allegro/summarization-polish-summaries-corpus/.../whole/dev.csv`, `.../whole/test.csv` (`NEWS_DEV_URL`, `NEWS_TEST_URL` in `src/polish_corpus/config.py:38-39`)
  - Client: `get_news_paths()` in `src/polish_corpus/fetchers.py:69-75`
- WikiNeural train_pl.jsonl (Babelscape) - Wikipedia genre source (40% token mass)
  - URL: `https://huggingface.co/datasets/Babelscape/wikineural/resolve/main/train_pl.jsonl` (`WIKINEURAL_PL_URL` in `src/polish_corpus/config.py:40`)
  - Client: `get_wikipedia_path()` in `src/polish_corpus/fetchers.py:78-81`
  - Auth: none on all HF links; plain GET with `User-Agent: stemgen-polish-corpus/1.0`

**Wolne Lektury (wolnelektury.pl):**
- 7 classic prose plain-text books (Lalka x2, Faraon, Krzyżacy, Quo Vadis, Chłopi, Pan Tadeusz) - Literature genre source
  - URLs: enumerated in `LITERATURE_BOOKS` in `src/polish_corpus/config.py:42-50`
  - Client: `get_literature_dir()` in `src/polish_corpus/fetchers.py:84-91`
  - Auth: none

**GitHub raw (raw.githubusercontent.com):**
- Snowball Polish voc.txt - regression benchmark vocabulary
  - URL: `https://raw.githubusercontent.com/snowballstem/snowball-data/master/polish/voc.txt` (`SNOWBALL_POLISH_VOC_URL` in `src/polish_corpus/config.py:33`)
  - Client: `get_snowball_voc_path()` in `src/polish_corpus/fetchers.py:54-57`, annotated in `build_snowball_voc_ground_truth()` in `src/polish_corpus/benchmark_splitter.py:53-71`
  - Auth: none

**Integration pattern (all sources):** download-once with file cache + graceful degradation. `download_file()` in `src/polish_corpus/fetchers.py:23-39` skips download when dest exists and is non-empty (prints `[Cache Hit]`), writes via `.part` temp file then renames. `ensure_all_text_sources()` in `src/polish_corpus/fetchers.py:94-115` wraps each genre fetch in try/except and falls back to synthetic seed documents (`generate_seed_documents()` in `src/polish_corpus/builder.py:41-91`). No SDK, no API keys, no retry/backoff, no checksum verification.

## Data Storage

**Databases:**
- None - no SQL/NoSQL, no ORM, no connection strings

**File Storage:**
- Local filesystem only
  - Cache: `data_cache/` (repo root or cwd; override via `POLISH_CORPUS_CACHE` env var) - holds `polimorf-*.tab.gz`, `sjp_odm.zip`, `nkjp1m_*.jsonl.gz`, `news_*.csv`, `wiki_pl.jsonl`, `literature/*.txt`, `snowball_voc.txt`. Git-ignored (`data_cache/` in `.gitignore`).
  - Output: `dist/<tier>/` (default) or `--output-dir` - `corpus.zip`, `ground_truth.parquet`, `ground_truth_train.parquet`, `ground_truth_test.parquet`, `snowball_voc_ground_truth.parquet`, `build_summary.json`, `README.md`. Git-ignored (`dist/`, `*.zip`, `*.parquet` in `.gitignore`).
  - Columnar format: Apache Parquet via `pyarrow` with `zstd` compression (`src/polish_corpus/benchmark_splitter.py:103`); document archive via stdlib `zipfile` DEFLATE (`src/polish_corpus/corpus_sampler.py:63-66`)

**Caching:**
- File-existence cache only (see `download_file()` above). `--force-download` flag in `src/polish_corpus/cli.py:41-45` bypasses it. No Redis/Memcached/HTTP-cache headers honored.

## Authentication & Identity

**Auth Provider:**
- None - all remote endpoints are public, unauthenticated HTTPS GETs. No login, OAuth, tokens, or user identity anywhere in the codebase.

## Monitoring & Observability

**Error Tracking:**
- None - no Sentry/datadog/OTel integration

**Logs:**
- `print()` to stdout with `[prefix]` tags (`[Downloading]`, `[Cache Hit]`, `[Warning]`, `[Notice]`, `[CorpusBuilder]`, `[Fetchers]`) across `src/polish_corpus/fetchers.py` and `src/polish_corpus/builder.py`. No logging framework, no log levels, no file sinks.

## CI/CD & Deployment

**Hosting:**
- None - CLI batch tool producing local artifacts; no server, container, or cloud deployment target

**CI Pipeline:**
- None - no `.github/workflows/`, no Dockerfile, no CI config detected

## Environment Configuration

**Required env vars:**
- None required. Single optional var:
  - `POLISH_CORPUS_CACHE` - overrides download cache directory (`src/polish_corpus/config.py:13`)

**Secrets location:**
- Not applicable - zero secrets, zero credentials. No `.env` file present or expected; `.gitignore` contains no secret patterns.

## Webhooks & Callbacks

**Incoming:**
- None - no server, no endpoints

**Outgoing:**
- None - all external contact is outbound HTTPS GET downloads at build time; no POST callbacks, no webhook emission, no telemetry ping

---

*Integration audit: 2026-10-16*
