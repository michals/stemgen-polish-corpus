# Phase 1: Cleaning Stage + Shared Tokenizer - Pattern Map

**Mapped:** 2026-10-16
**Files analyzed:** 3 (1 new, 2 modified)
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/polish_corpus/text_cleaning.py` (NEW) | utility | transform | `src/polish_corpus/morfeusz_extractor.py` | role-match |
| `src/polish_corpus/corpus_sampler.py` (MODIFY) | service | streaming | `src/polish_corpus/corpus_sampler.py` (self) | exact |
| `tests/test_cleaning.py` (NEW) | test | batch | `tests/test_smoke.py` | role-match |

## Pattern Assignments

### `src/polish_corpus/text_cleaning.py` (utility, transform) — NEW

**Analog:** `src/polish_corpus/morfeusz_extractor.py` (pure-function + regex-constant pattern)

**Imports pattern** (morfeusz_extractor.py lines 11-23):
```python
from __future__ import annotations

import gzip
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from pathlib import Path

from .config import CORE_POS_TAGS

# Accept Polish letters and internal hyphens (e.g., biało-czerwony)
VALID_WORD_RE = re.compile(r"^[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+(-[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+)?$")
```

Copy: `from __future__ import annotations`, stdlib-only imports (`html`, `re`, `unicodedata`), module-level compiled regex constant with comment. New module needs NO `pathlib`/`gzip`/`Counter` — pure `str -> str` / `str -> bool` functions only.

**Pure-function pattern** (lines 47-49):
```python
def clean_lemma(raw_lemma: str) -> str:
    """Strip Morfeusz homonym indicators (e.g., 'piec:s1' -> 'piec')."""
    return raw_lemma.split(":")[0]
```

Copy: one-line-summary PEP 257 docstring, typed signature, no I/O, no logging. `clean_text(text: str) -> str`, `is_valid_token(token: str) -> bool`, `tokenize(text: str) -> list[str]` follow this shape.

**Canonical TOKEN_RE source** (corpus_sampler.py line 20):
```python
TOKEN_RE = re.compile(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+(?:-[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]+)?")
```

Move verbatim into `text_cleaning.py`; `corpus_sampler.py` and `morfeusz_extractor.py` (import swap if trivial) import it from there. `is_valid_token()` = `TOKEN_RE.fullmatch(t)` + no-digit + per-hyphen-segment Polish-only check (see RESEARCH §2).

**Validator pattern** (morfeusz_extractor.py lines 84-87, numbered-pipeline comment style):
```python
# 1. Reject invalid orthography
if not VALID_WORD_RE.match(form):
    discarded_invalid += 1
    continue
```

Copy the numbered `# 1. ... # 2. ...` inline-comment style for the load-bearing ordering inside `clean_text()` (NFC → strip `�`/controls → `html.unescape` → token-drop → quote/dash normalize → whitespace collapse).

---

### `src/polish_corpus/corpus_sampler.py` (service, streaming) — MODIFY

**Analog:** itself (in-place choke-point edit, lines 73-91)

```python
def add_document(self, genre: str, text: str) -> str:
    """Add a single natural document to the zip archive under genre directory."""
    ...
    tokens = [t.lower() for t in TOKEN_RE.findall(text)]
    token_count = len(tokens)
    self.token_counts[genre] += token_count

    # Track vocabulary frequencies
    self.term_freq.update(tokens)
    self.doc_freq.update(set(tokens))

    self.zip_file.writestr(filename, text)
    return filename
```

**Writer-gate edit:** first line of `add_document` becomes `text = clean_text(text)` (import from `.text_cleaning`); then replace `TOKEN_RE.findall(text)` at line 83 with shared `tokenize(text)` (which already filters via `is_valid_token`), and `count_words` (lines 23-25) with the shared version:
```python
def count_words(text: str) -> int:
    """Return count of alphabetic word tokens in text."""
    return len(TOKEN_RE.findall(text))
```
→ delegate to `tokenize()`. Stored zip text and TF/DF agree by construction. Do NOT gate `add_paradigm_batch` (lines 109-126, counts `forms` list directly).

**Streaming/no-buffer constraint:** writer holds only `Counter` accumulators + one open `ZipFile`; `clean_text` must be per-doc `str -> str`, no corpus-wide state (per PROJECT.md Performance constraint).

---

### `tests/test_cleaning.py` (test, batch) — NEW

**Analog:** `tests/test_smoke.py`

**Import + plain-function pattern** (test_smoke.py lines 1-13):
```python
import pytest

from polish_corpus.builder import build_polish_corpus
from polish_corpus.cli import main
from polish_corpus.config import TIERS, TierConfig


def test_package_exports() -> None:
    """Verify package configuration and tiers are exposed."""
```

Copy: `pythonpath = ["src"]` import style (`from polish_corpus.text_cleaning import ...`), plain `test_*` functions with one-line docstrings, no fixtures/classes. Parametrize the RESEARCH §4 fixture table (`Béziera→∅`, `café→∅` not `caf`, `COVID-19→∅`, `biało-czerwony` retained, `&eacute;` ordering, NFD→NFC) plus one zip-vs-TF/DF agreement test on a dirty sample via `BalancedCorpusWriter` + `tmp_path`.

---

## Shared Patterns

### Module docstring (all new modules)
**Source:** `src/polish_corpus/corpus_sampler.py:1-7`
```python
"""Multi-genre balanced corpus sampler and document chunker.

Implements Step 2 of general_polish_corpus_strategy.md:
...
"""
```
New `text_cleaning.py` opens with the same shape: one-line summary + pipeline-step reference.

### Logging
No logging in pure functions (`clean_lemma`, `count_words` are silent). Keep `text_cleaning.py` print-free; progress prints stay in builder/writer orchestration only.

### Error handling
Lenient-by-convention: `errors="replace"` on text opens, skip-and-continue on bad rows. `clean_text` must never raise on weird input — return `""` for empty-after-clean; `chunk_text_stream` already skips `para_words == 0` (lines 42-43).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | All files have analogs above. `html.unescape` + `unicodedata.normalize("NFC", ...)` ordering has no in-repo precedent — follow RESEARCH.md §2 verbatim. |

## Metadata

**Analog search scope:** `src/polish_corpus/`, `tests/`
**Files scanned:** 4 (`corpus_sampler.py`, `morfeusz_extractor.py`, `builder.py`, `test_smoke.py`)
**Git-tracked check:** all analogs verified via `git ls-files` (non-empty)
**Pattern extraction date:** 2026-10-16
