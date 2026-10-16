---
last_mapped_commit: 02ed6cd4ab60c4be38b5b397c048ebb556d0660c
last_mapped_at: 2026-10-16
---
# Testing Patterns

**Analysis Date:** 2026-10-16

## Test Framework

**Runner:**
- `pytest>=8.0.0` (dev dependency in `pyproject.toml`, also in `[dependency-groups] dev`)
- Config: `pyproject.toml` (`[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `pythonpath = ["src"]`)

**Assertion Library:**
- Plain `assert` statements (no unittest classes, no third-party assertion library). All tests live in `tests/test_smoke.py`.

**Run Commands:**

```bash
pytest                    # Run all tests (testpaths = tests/)
pytest tests/test_smoke.py  # Run the single smoke-test module
pytest -v                 # Verbose per-test output
uv run pytest             # Project-preferred invocation (uv.lock present)
```

## Test File Organization

**Location:**
- Separate top-level `tests/` directory (not co-located with source). `src/polish_corpus/` contains zero test files; all tests live in `tests/test_smoke.py`.

**Naming:**
- `test_<subject>.py` for modules; `test_<behavior>` snake_case for functions: `test_package_exports`, `test_default_tier_subdir`, `test_quick_test_run`, `test_cli_help` (`tests/test_smoke.py:8-50`)

**Structure:**

```
tests/
└── test_smoke.py   # Only test module: package exports, tier config, end-to-end quick-test build, CLI help
```

## Test Structure

**Suite Organization:**

```python
import pytest

from polish_corpus.builder import build_polish_corpus
from polish_corpus.cli import main
from polish_corpus.config import TIERS, TierConfig

def test_package_exports() -> None:
    """Verify package configuration and tiers are exposed."""
    assert "recommended" in TIERS
    assert "compact" in TIERS
    assert "extended" in TIERS
    assert isinstance(TIERS["recommended"], TierConfig)
```

(`tests/test_smoke.py:1-14`)

**Patterns:**
- Function-style tests returning `-> None` with a one-line docstring stating the verified behavior — follow this shape for every new test
- Flat independent tests with no fixtures except `tmp_path`/`capsys`/`importorskip`; no `setup`/`teardown`, no classes, no parametrization
- Direct `assert` on return values and filesystem artifacts, not on mocks

## Mocking

**Framework:** `pytest` builtin fixtures only (`tmp_path`, `capsys`, `pytest.importorskip`). No `unittest.mock`, `monkeypatch`, `pytest-mock`, or network stubbing is used anywhere.

**Patterns:**

```python
def test_quick_test_run(tmp_path) -> None:
    """Verify quick test pipeline runs end-to-end and creates expected artifacts."""
    pytest.importorskip("pyarrow", reason="pyarrow required for parquet export")
    out_dir = tmp_path / "output"
    exit_code = build_polish_corpus(
        tier_name="recommended",
        output_dir=out_dir,
        quick_test=True,
    )
    assert exit_code == 0
    assert (out_dir / "corpus.zip").exists()
```

(`tests/test_smoke.py:24-34`)

```python
def test_cli_help(capsys) -> None:
    """Verify CLI help output."""
    try:
        main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    captured = capsys.readouterr()
    assert "stemgen-polish-corpus" in captured.out
    assert "--tier" in captured.out
```

(`tests/test_smoke.py:42-50`)

**What to Mock:**
- Nothing is mocked today. Prefer the existing approach: exercise the real pipeline with `quick_test=True` (internal seed documents, ~20 docs, `< 0.2s`) instead of mocking fetchers or the dictionary.

**What NOT to Mock:**
- Do not mock `build_polish_corpus` itself, the parquet exporter, or `BalancedCorpusWriter` — the suite's value is the real end-to-end artifact check (`corpus.zip`, `ground_truth*.parquet`, `build_summary.json`)

## Fixtures and Factories

**Test Data:**
- No fixtures file or factory helpers. Seed/paradigm data is generated inside production code: `generate_seed_documents(genre, target_docs)` (`src/polish_corpus/builder.py:41-91`) and the inline `bootstrap_data` list of `(form, lemma, pos)` tuples (`src/polish_corpus/builder.py:138-151`). Tests reuse these by passing `quick_test=True` — do the same for new pipeline tests.

```python
def generate_seed_documents(genre: str, target_docs: int) -> list[str]: ...
```

**Location:**
- Test isolation uses pytest's builtin `tmp_path` (`out_dir = tmp_path / "output"` in `tests/test_smoke.py:27-28`). There is no `conftest.py` and no shared `fixtures/` directory — add one only when a second test module needs the same setup.

## Coverage

**Requirements:** None enforced. No `--cov`, `fail-under`, `coverage` config, or CI gate exists in the repo.

**View Coverage:**

```bash

# Not currently configured; ad-hoc only:

pytest --cov=polish_corpus --cov-report=term-missing  # requires pytest-cov (not installed)
```

## Test Types

**Unit Tests:**
- Config/shape checks with no I/O: `test_package_exports` (tier registry contents and types, `tests/test_smoke.py:8-14`) and `test_default_tier_subdir` (output path nesting `./dist/<tier>`, `tests/test_smoke.py:16-21`). Add new unit tests in this style for pure helpers (`clean_lemma`, `count_words`, `chunk_text_stream`, `create_lemma_stratified_split`, `resolve_homonyms`).

**Integration Tests:**
- `test_quick_test_run` (`tests/test_smoke.py:24-39`): runs the full `build_polish_corpus(quick_test=True)` pipeline into `tmp_path` and asserts all six artifacts exist (`corpus.zip`, `ground_truth.parquet`, `ground_truth_train.parquet`, `ground_truth_test.parquet`, `snowball_voc_ground_truth.parquet`, `build_summary.json`). Guard it with `pytest.importorskip("pyarrow")` since parquet export requires the optional `pyarrow>=14.0.0` dependency.

**E2E Tests:**
- Not used as a separate category. `test_cli_help` (`tests/test_smoke.py:42-50`) is the closest: invokes the real `main(["--help"])` entrypoint (`src/polish_corpus/cli.py:13-55`), expects `SystemExit(0)`, and asserts on captured stdout via `capsys`. No subprocess or network-level E2E exists — full-tier builds require downloads and are never exercised in tests.

## Common Patterns

**Async Testing:**
- Not applicable. The entire codebase is synchronous (`urllib.request`, `gzip`, `zipfile`, plain generators); there is no `asyncio`, `anyio`, or `trio`.

**Error Testing:**
- Errors are asserted via `try/except SystemExit` + code check, not `pytest.raises`:

```python
try:
    main(["--help"])
except SystemExit as e:
    assert e.code == 0
```

(`tests/test_smoke.py:44-47`). Mirror this for future CLI exit-code tests (e.g. invalid `--tier` should exit non-zero via argparse).

---

*Testing analysis: 2026-10-16*
