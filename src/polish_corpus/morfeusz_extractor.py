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

    @staticmethod
    def _filter_derivational_self_lemmas(word: str, candidates: list[str]) -> list[str]:
        """Prefer verbal base lemmas over productive gerund/participle self-lemmas."""
        if len(candidates) <= 1:
            return candidates
        verb_cands = [
            lem
            for lem in candidates
            if lem.endswith(("ć", "c")) and lem != word and len(lem) >= 3
        ]
        if not verb_cands:
            return candidates
        # If non-verb candidates are purely participial (-ący, -any, -ony, -ty, -ły) or gerund (-nie, -cie),
        # prefer the parent verb lemma so the entire inflectional paradigm stays unified.
        non_deriv = [
            lem
            for lem in candidates
            if lem in verb_cands
            or not lem.endswith(("nie", "cie", "ący", "any", "ony", "ty", "ły"))
        ]
        return non_deriv if non_deriv else verb_cands

    def resolve_homonyms(
        self,
        corpus_term_freq: Callable[[str], int] | dict[str, int] | Counter[str] | None = None,
        lemma_frequency_fn: Callable[[str], int] | None = None,
    ) -> dict[str, str]:
        """Resolve surface homonyms to a single dominant lemma (1 word -> 1 lemma) using Family Mass."""
        tf_fn: Callable[[str], int] | None = None
        if isinstance(corpus_term_freq, (dict, Counter)):
            def tf_fn(w: str) -> int:
                return corpus_term_freq.get(w, 0)
        elif callable(corpus_term_freq):
            tf_fn = corpus_term_freq
        elif callable(lemma_frequency_fn):
            tf_fn = lemma_frequency_fn

        # 1. Precompute fractional family token mass for every lemma across the corpus
        lemma_family_mass: dict[str, float] = defaultdict(float)
        if tf_fn is not None:
            for w, lem_counter in self.word_to_lemmas.items():
                w_tf = tf_fn(w)
                if w_tf <= 0:
                    continue
                # Filter out self-derivational gerund/participle lemmas when a shorter verb lemma exists
                cands = self._filter_derivational_self_lemmas(w, list(lem_counter.keys()))
                share = w_tf / len(cands)
                for lem in cands:
                    lemma_family_mass[lem] += share

        self.dominant_lemma.clear()

        for word, lemma_counter in self.word_to_lemmas.items():
            if len(lemma_counter) == 1:
                self.dominant_lemma[word] = next(iter(lemma_counter.keys()))
                continue

            candidates = self._filter_derivational_self_lemmas(word, list(lemma_counter.keys()))
            if len(candidates) == 1:
                self.dominant_lemma[word] = candidates[0]
                continue

            if tf_fn is not None:
                # Rank by:
                # 1. Family token mass across corpus inflections
                # 2. Surface lemma frequency
                # 3. Internal dictionary analysis count
                # 4. Identity fallback (lem == word) as final tie-breaker only
                best = max(
                    candidates,
                    key=lambda lem: (
                        lemma_family_mass.get(lem, 0.0),
                        tf_fn(lem),
                        lemma_counter[lem],
                        1 if lem == word else 0,
                    ),
                )
            else:
                best = max(
                    candidates,
                    key=lambda lem: (
                        len(self.lemma_to_forms.get(lem, ())),
                        lemma_counter[lem],
                        1 if lem == word else 0,
                    ),
                )
            self.dominant_lemma[word] = best

        return self.dominant_lemma

    def lookup_lemma(self, word: str) -> str:
        """Resolve word to its dominant lemma with productive prefix & compound fallback."""
        w = word.lower()
        direct = self.dominant_lemma.get(w)
        if direct is not None:
            return direct

        # 1. Superlative prefix 'naj-' (not tabulated in raw PoliMorf)
        if w.startswith("naj") and len(w) >= 6:
            rem = w[3:]
            if rem in self.dominant_lemma:
                return self.dominant_lemma[rem]

        # 2. Negation prefix 'nie-' on participles/adjectives/gerunds
        if w.startswith("nie") and len(w) >= 6:
            rem = w[3:]
            if rem in self.dominant_lemma:
                base_lem = self.dominant_lemma[rem]
                # If base is a verb, keep unified with verb; if adj/adv/subst, prefix 'nie'
                if base_lem.endswith(("ć", "c")):
                    return base_lem
                return "nie" + base_lem

        # 3. Hyphenated compounds (e.g. 'środkowo-wschodniej' -> 'środkowo-wschodni')
        if "-" in w:
            parts = w.split("-")
            head = parts[-1]
            head_lem = self.dominant_lemma.get(head)
            if head_lem is not None:
                return "-".join([*parts[:-1], head_lem])

        return w

    def get_paradigm(self, lemma_lower: str) -> set[str]:
        """Return all standard inflected forms for a lemma."""
        return self.lemma_to_forms.get(lemma_lower, set())
