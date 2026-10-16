---
last_mapped_commit: 02ed6cd4ab60c4be38b5b397c048ebb556d0660c
last_mapped_at: 2026-10-16
---
# Technology Stack

**Analysis Date:** 2026-10-16

## Languages

**Primary:**
- Python >=3.10 (developed/tested on 3.11.12) - All pipeline code in `src/polish_corpus/`

**Secondary:**
- None - pure-Python project, no JS/TS/Rust extensions

## Runtime

**Environment:**
- CPython 3.10+ (type hints use `from __future__ import annotations` + `X | None` syntax in `src/polish_corpus/cli.py`, `src/polish_corpus/builder.py`, `src/polish_corpus/fetchers.py`)

**Package Manager:**
- uv (recommended per `README.md`) with `uv.lock` committed; also supports std `pip` + `venv`
- Lockfile: present (`uv.lock`)
- Build backend: `hatchling` (`[build-system]` in `pyproject.toml`), wheel packages `src/polish_corpus`

## Frameworks

**Core:**
- Standard library only for pipeline logic - `argparse` (CLI), `urllib.request` (downloads), `gzip`/`zipfile`/`csv`/`json` (parsing), `pathlib`/`dataclasses`/`collections`/`random` (core logic)
- No web framework, no ORM, no async framework

**Testing:**
- pytest >=8.0.0 (resolved 9.1.1 in `uv.lock`) - Config: `[tool.pytest.ini_options]` in `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["src"]`)
- Smoke test: `tests/test_smoke.py` (runs `--quick-test` build)

**Build/Dev:**
- ruff >=0.8.0 (resolved 0.17.0 in `uv.lock`) - lint + format; config in `pyproject.toml` (`line-length = 100`, `target-version = "py310"`, rules `["E", "F", "UP", "B", "SIM", "I"]`)
- hatchling - wheel build backend
- Console script: `stemgen-polish-corpus = "polish_corpus.cli:main"` (`[project.scripts]`), dual entry via `src/polish_corpus/__main__.py` (`python -m polish_corpus`)

## Key Dependencies

**Critical:**
- pyarrow >=14.0.0 (resolved 25.0.1 on py3.10 / 26.0.0 on py3.11+ per `uv.lock` markers) - ONLY runtime dependency; used in `src/polish_corpus/benchmark_splitter.py:80-103` (`export_records_to_parquet`) to write `ground_truth*.parquet` tables with `zstd` compression, schema `(word: string, lemma: string, tf: int64, df: int64)`

**Infrastructure:**
- None - no database driver, no cloud SDK, no HTTP client library (uses stdlib `urllib.request` with custom `User-Agent: stemgen-polish-corpus/1.0` in `src/polish_corpus/fetchers.py:32-33`)

**Transitive (dev):**
- `pytest` pulls `pluggy`, `packaging`, `iniconfig`, `pygments`, `exceptiongroup`, `tomli`, `colorama` (see `uv.lock`)

## Configuration

**Environment:**
- Single env var override: `POLISH_CORPUS_CACHE` - custom cache dir; resolution order in `src/polish_corpus/config.py:13-19`: env var → `./data_cache` (repo root, if exists) → `./data_cache` (cwd)
- Output base defaults to `./dist` (cwd-resolved) in `src/polish_corpus/config.py:21`; per-tier nesting via `get_default_output_dir()` in `src/polish_corpus/config.py:24-26`
- CLI flags override config: `--tier {compact,recommended,extended}`, `--output-dir`, `--polimorf-path`, `--quick-test`, `--force-download` (`src/polish_corpus/cli.py:19-45`)
- No `.env` file present or required; no secrets of any kind

**Build:**
- `pyproject.toml` - project metadata, dependencies, hatchling wheel target, pytest + ruff config
- `uv.lock` - pinned resolution (version 1, revision 3)

## Platform Requirements

**Development:**
- Python >=3.10, `uv` (or `pip`), ~disk for `data_cache/` downloads (NKJP1M, WikiNeural, news CSVs, PoliMorf ~GB-scale)
- Install: `uv pip install -e ".[dev]"`; test: `pytest`

**Production:**
- CLI batch tool, not a service - runs wherever Python 3.10+ runs (macOS/Linux/Windows wheels for pyarrow in `uv.lock`)
- No container/Dockerfile, no CI workflow files detected
- Outputs: `corpus.zip` (stdlib `zipfile.ZIP_DEFLATED` in `src/polish_corpus/corpus_sampler.py:63-66`), `*.parquet` (pyarrow+zstd), `build_summary.json`, `README.md` under `dist/<tier>/`

---

*Stack analysis: 2026-10-16*
