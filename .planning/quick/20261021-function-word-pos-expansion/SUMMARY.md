---
task: function-word-pos-expansion
date: 2026-10-21
status: completed
---

# Quick Task Summary: Lexicon POS Expansion & Function-Word Bootstrap Anchors

Synchronized dictionary config, bootstrap anchors, and canary probes with `stemgen` Phase 14:
- Expanded `CORE_POS_TAGS` in `polish_corpus/config.py` with `prep`, `conj`, `comp`, `part`, `qub`, `pred`, `interj`.
- Added 16 function-word bootstrap anchors in `polish_corpus/builder.py`.
- Added canary lemma probes for `"nie"`, `"od"`, `"lecz"` in `verify_zero_fragments.py`.
- Verified clean suite with 123 tests passing and 0 ruff errors.
