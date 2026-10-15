"""Morfeusz 2 / PoliMorf Ground Truth Extractor and Sanitizer.

Implements Step 1 of general_polish_corpus_strategy.md:
1. Strip homonym qualifiers (:s1, :v, etc.)
2. Filter proper nouns BEFORE lowercasing (lemma[0].isupper())
3. Discard forms not in core POS lexical categories
4. Resolve surface homonyms (1 word -> 1 dominant lemma)
5. Index inflectional paradigms by lemma for Step 4 completion
"""

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


def parse_polimorf_stream(
    tab_gz_path: Path,
) -> Iterator[tuple[str, str, str]]:
    """Yield (form, raw_lemma, pos_tag) from PoliMorf tab.gz.

    PoliMorf lines typically follow:
        <form> <tab> <lemma> <tab> <tag> [<tab> <qualifiers>]
    """
    with gzip.open(tab_gz_path, "rt", encoding="utf-8", errors="replace") as f:
        for _line_no, line in enumerate(f, 1):
            line = line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            form, raw_lemma, tag = parts[0], parts[1], parts[2]
            pos = tag.split(":")[0]
            yield form, raw_lemma, pos


def clean_lemma(raw_lemma: str) -> str:
    """Strip Morfeusz homonym indicators (e.g., 'piec:s1' -> 'piec')."""
    return raw_lemma.split(":")[0]


class MorfeuszDictionary:
    """Sanitized in-memory morphological dictionary extracted from PoliMorf."""

    def __init__(self):
        # word_lower -> Counter(lemma_lower -> count_of_analyses)
        self.word_to_lemmas: dict[str, Counter[str]] = defaultdict(Counter)
        # lemma_lower -> set of inflected forms (lower)
        self.lemma_to_forms: dict[str, set[str]] = defaultdict(set)
        # Dominant mapping: word_lower -> dominant_lemma_lower
        self.dominant_lemma: dict[str, str] = {}

    def ingest_polimorf(
        self,
        tab_gz_path: Path,
        max_rows: int | None = None,
        verbose: bool = True,
    ) -> None:
        """Parse, filter, and index PoliMorf tabular data."""
        if verbose:
            print(f"[MorfeuszDictionary] Parsing {tab_gz_path.name}...")

        total_lines = 0
        accepted_lines = 0
        discarded_proper = 0
        discarded_pos = 0
        discarded_invalid = 0

        for form, raw_lemma, pos in parse_polimorf_stream(tab_gz_path):
            total_lines += 1
            if max_rows and total_lines > max_rows:
                break

            # 1. Reject invalid orthography
            if not VALID_WORD_RE.match(form):
                discarded_invalid += 1
                continue

            # 2. Filter proper nouns BEFORE lowercasing
            clean_lem = clean_lemma(raw_lemma)
            if not clean_lem or clean_lem[0].isupper():
                discarded_proper += 1
                continue

            # 3. Filter to core lexical categories
            if pos not in CORE_POS_TAGS:
                discarded_pos += 1
                continue

            form_lower = form.lower()
            lemma_lower = clean_lem.lower()

            self.word_to_lemmas[form_lower][lemma_lower] += 1
            self.lemma_to_forms[lemma_lower].add(form_lower)
            accepted_lines += 1

            if verbose and total_lines % 1_000_000 == 0:
                print(
                    f"  Processed {total_lines:,} rows: "
                    f"{accepted_lines:,} accepted, {discarded_proper:,} proper nouns, "
                    f"{discarded_pos:,} non-core POS."
                )

        if verbose:
            print(
                f"[MorfeuszDictionary] Completed: {total_lines:,} processed, "
                f"{accepted_lines:,} accepted -> {len(self.word_to_lemmas):,} unique words, "
                f"{len(self.lemma_to_forms):,} unique lemmas."
            )

    def ingest_sjp_odm(
        self,
        odm_path: Path,
        max_lines: int | None = None,
        verbose: bool = True,
    ) -> None:
        """Parse, filter, and index SJP odm.txt (or sjp_odm.zip)."""
        odm_path = Path(odm_path)
        if verbose:
            print(f"[MorfeuszDictionary] Parsing SJP odm data from {odm_path.name}...")

        total_lines = 0
        accepted_lines = 0
        discarded_proper = 0

        def _line_iterator():
            if odm_path.suffix == ".zip":
                with zipfile.ZipFile(odm_path) as zf, zf.open("odm.txt") as f:
                    for line_bytes in f:
                        yield line_bytes.decode("utf-8", errors="ignore").strip()
            else:
                with open(odm_path, encoding="utf-8", errors="ignore") as f:
                    for line_str in f:
                        yield line_str.strip()

        for line in _line_iterator():
            total_lines += 1
            if max_lines and total_lines > max_lines:
                break
            if not line or "," not in line:
                continue

            parts = [p.strip() for p in line.split(",")]
            base = parts[0]

            # 1. Reject proper nouns BEFORE lowercasing
            if not base or base[0].isupper() or " " in base:
                discarded_proper += 1
                continue

            # 2. Reject non-word orthography
            if not VALID_WORD_RE.match(base):
                continue

            base_lower = base.lower()
            accepted_lines += 1

            for form in parts:
                if not VALID_WORD_RE.match(form):
                    continue
                form_lower = form.lower()
                self.word_to_lemmas[form_lower][base_lower] += 1
                self.lemma_to_forms[base_lower].add(form_lower)

            if verbose and total_lines % 50_000 == 0:
                print(
                    f"  Processed {total_lines:,} lines: "
                    f"{accepted_lines:,} accepted base words, {discarded_proper:,} proper nouns."
                )

        if verbose:
            print(
                f"[MorfeuszDictionary] SJP Ingestion Completed: {total_lines:,} lines -> "
                f"{len(self.word_to_lemmas):,} unique inflected forms across "
                f"{len(self.lemma_to_forms):,} base lemmas."
            )

    def resolve_homonyms(
        self,
        lemma_frequency_fn: Callable[[str], int] | None = None,
    ) -> dict[str, str]:
        """Resolve surface homonyms to a single dominant lemma (1 word -> 1 lemma).

        If lemma_frequency_fn is provided, selects the candidate lemma with the highest
        corpus frequency. Otherwise breaks ties using dictionary analysis count,
        favoring lemma == word when applicable.
        """
        self.dominant_lemma.clear()

        for word, lemma_counter in self.word_to_lemmas.items():
            if len(lemma_counter) == 1:
                self.dominant_lemma[word] = next(iter(lemma_counter.keys()))
                continue

            candidates = list(lemma_counter.keys())
            if lemma_frequency_fn:
                # Rank by external corpus lemma frequency, then internal analysis frequency
                best = max(
                    candidates,
                    key=lambda lem: (
                        lemma_frequency_fn(lem),
                        1 if lem == word else 0,
                        lemma_counter[lem],
                    ),
                )
            else:
                best = max(
                    candidates,
                    key=lambda lem: (
                        1 if lem == word else 0,
                        lemma_counter[lem],
                    ),
                )
            self.dominant_lemma[word] = best

        return self.dominant_lemma

    def get_paradigm(self, lemma_lower: str) -> set[str]:
        """Return all standard inflected forms for a lemma."""
        return self.lemma_to_forms.get(lemma_lower, set())
