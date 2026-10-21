---
task: function-word-pos-expansion
date: 2026-10-21
status: completed
---

# Quick Task: Lexicon POS Expansion & Function-Word Bootstrap Anchors

Expand `CORE_POS_TAGS` to include function words (`prep`, `conj`, `comp`, `part`, `qub`, `pred`, `interj`), add function-word bootstrap anchors in `builder.py`, and register canary lemma probes in `verify_zero_fragments.py`.

Files changed:
- `src/polish_corpus/config.py`: Add function-word POS tags to `CORE_POS_TAGS`.
- `src/polish_corpus/builder.py`: Add function-word anchors to `bootstrap_data`.
- `src/verify_zero_fragments.py`: Add `"nie"`, `"od"`, `"lecz"` canary probes.

Verification:
- `pytest tests/` passes 100%.
- `ruff check src/` clean with 0 errors.
