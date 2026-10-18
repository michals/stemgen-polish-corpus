"""Morfeusz 2 / PoliMorf Ground Truth Extractor and Sanitizer.

Implements Step 1 of general_polish_corpus_strategy.md:
1. Strip homonym qualifiers (:s1, :v, etc.)
2. Separate common words from proper nouns BEFORE lowercasing (keeping proper nouns as fallback only)
3. Filter to core POS lexical categories
4. Resolve surface homonyms (1 word -> 1 dominant lemma) via 2-Pass EM Family Mass
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
    """Yield (form, raw_lemma, pos_tag) from PoliMorf tab.gz."""
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

    def __init__(self) -> None:
        # Common words: word_lower -> Counter(lemma_lower -> count_of_analyses)
        self.word_to_lemmas: dict[str, Counter[str]] = defaultdict(Counter)
        # Proper nouns (fallback only, excluded from paradigm expansion):
        # word_lower -> Counter(lemma_lower -> count_of_analyses)
        self.proper_word_to_lemmas: dict[str, Counter[str]] = defaultdict(Counter)
        # lemma_lower -> set of inflected forms (lower) for common words
        self.lemma_to_forms: dict[str, set[str]] = defaultdict(set)
        # Dominant mapping: word_lower -> dominant_lemma_lower
        self.dominant_lemma: dict[str, str] = {}
        self.proper_dominant_lemma: dict[str, str] = {}
        # Normalized EM family mass prior: lemma_lower -> float
        self.lemma_family_mass: dict[str, float] = defaultdict(float)

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
        proper_lines = 0
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

            clean_lem = clean_lemma(raw_lemma)
            if not clean_lem or not VALID_WORD_RE.match(clean_lem):
                discarded_invalid += 1
                continue

            # 2. Filter to core lexical categories
            if pos not in CORE_POS_TAGS:
                discarded_pos += 1
                continue

            form_lower = form.lower()
            lemma_lower = clean_lem.lower()

            # 3. Separate capitalized proper nouns from common vocabulary
            if clean_lem[0].isupper():
                self.proper_word_to_lemmas[form_lower][lemma_lower] += 1
                proper_lines += 1
                continue

            self.word_to_lemmas[form_lower][lemma_lower] += 1
            self.lemma_to_forms[lemma_lower].add(form_lower)
            accepted_lines += 1

            if verbose and total_lines % 1_000_000 == 0:
                print(
                    f"  Processed {total_lines:,} rows: "
                    f"{accepted_lines:,} common, {proper_lines:,} proper fallback, "
                    f"{discarded_pos:,} non-core POS."
                )

        if verbose:
            print(
                f"[MorfeuszDictionary] Completed: {total_lines:,} processed, "
                f"{accepted_lines:,} common ({len(self.word_to_lemmas):,} words, "
                f"{len(self.lemma_to_forms):,} lemmas), "
                f"{len(self.proper_word_to_lemmas):,} proper-noun forms."
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
        proper_lines = 0

        def _line_iterator() -> Iterator[str]:
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
            if not base or " " in base or not VALID_WORD_RE.match(base):
                continue

            is_proper = base[0].isupper()
            base_lower = base.lower()
            if is_proper:
                proper_lines += 1
            else:
                accepted_lines += 1

            for form in parts:
                if not VALID_WORD_RE.match(form):
                    continue
                form_lower = form.lower()
                if is_proper:
                    self.proper_word_to_lemmas[form_lower][base_lower] += 1
                else:
                    self.word_to_lemmas[form_lower][base_lower] += 1
                    self.lemma_to_forms[base_lower].add(form_lower)

        if verbose:
            print(
                f"[MorfeuszDictionary] SJP Ingestion Completed: {total_lines:,} lines -> "
                f"{len(self.word_to_lemmas):,} common forms, "
                f"{len(self.proper_word_to_lemmas):,} proper forms."
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
        """Resolve surface homonyms to a single dominant lemma using 2-Pass EM Family Mass."""
        tf_fn: Callable[[str], int] | None = None
        if isinstance(corpus_term_freq, (dict, Counter)):

            def tf_fn(w: str) -> int:
                return corpus_term_freq.get(w, 0)

        elif callable(corpus_term_freq):
            tf_fn = corpus_term_freq
        elif callable(lemma_frequency_fn):
            tf_fn = lemma_frequency_fn

        self.lemma_family_mass.clear()
        if tf_fn is not None:
            # Pass 1 (Anchor Prior): Unambiguous words contribute full TF;
            # ambiguous words contribute quadratically damped TF / |C(w)|^2 so high-TF
            # homonyms (like 'mam') cannot artificially inflate rare nouns ('mama').
            prior_mass: dict[str, float] = defaultdict(lambda: 1.0)
            filtered_cands_map: dict[str, list[str]] = {}
            for w, lem_counter in self.word_to_lemmas.items():
                cands = self._filter_derivational_self_lemmas(w, list(lem_counter.keys()))
                filtered_cands_map[w] = cands
                w_tf = tf_fn(w)
                if w_tf <= 0:
                    continue
                k = len(cands)
                if k == 1:
                    prior_mass[cands[0]] += float(w_tf)
                elif k > 1:
                    damped_share = float(w_tf) / float(k * k)
                    for lem in cands:
                        prior_mass[lem] += damped_share

            # Pass 2 (Proportional E-Step): Distribute each word's TF proportionally to Pass-1 prior
            for w, cands in filtered_cands_map.items():
                w_tf = tf_fn(w)
                if w_tf <= 0 or not cands:
                    continue
                if len(cands) == 1:
                    self.lemma_family_mass[cands[0]] += float(w_tf)
                else:
                    denom = sum(prior_mass[lem] for lem in cands)
                    for lem in cands:
                        weight = (prior_mass[lem] / denom) if denom > 0 else (1.0 / len(cands))
                        self.lemma_family_mass[lem] += float(w_tf) * weight

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
                best = max(
                    candidates,
                    key=lambda lem: (
                        self.lemma_family_mass.get(lem, 0.0),
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

        # Resolve proper-noun fallback table using corpus TF or analysis count
        self.proper_dominant_lemma.clear()
        for word, prop_counter in self.proper_word_to_lemmas.items():
            if len(prop_counter) == 1:
                self.proper_dominant_lemma[word] = next(iter(prop_counter.keys()))
            else:
                self.proper_dominant_lemma[word] = max(
                    prop_counter.keys(),
                    key=lambda lem: (
                        tf_fn(lem) if tf_fn is not None else 0,
                        prop_counter[lem],
                        1 if lem == word else 0,
                    ),
                )

        return self.dominant_lemma

    def get_candidates(self, word: str) -> list[str]:
        """Return canonicalized candidate lemmas C(w) for word (empty list if true OOV)."""
        w = word.lower()
        if w in self.word_to_lemmas:
            raw_cands = list(self.word_to_lemmas[w].keys())
            return self._filter_derivational_self_lemmas(w, raw_cands)

        # Superlative prefix 'naj-'
        if w.startswith("naj") and len(w) >= 6:
            rem = w[3:]
            if rem in self.word_to_lemmas:
                raw_cands = list(self.word_to_lemmas[rem].keys())
                return self._filter_derivational_self_lemmas(rem, raw_cands)

        # Negation prefix 'nie-'
        if w.startswith("nie") and len(w) >= 6:
            rem = w[3:]
            if rem in self.word_to_lemmas:
                base_cands = self._filter_derivational_self_lemmas(
                    rem, list(self.word_to_lemmas[rem].keys())
                )
                return [
                    c if c.endswith(("ć", "c")) else f"nie{c}"
                    for c in base_cands
                ]

        # Proper noun fallback if not in common lexicon
        if w in self.proper_word_to_lemmas:
            return list(self.proper_word_to_lemmas[w].keys())

        return []

    def lookup_lemma(self, word: str) -> str:
        """Resolve word to its dominant lemma with productive prefix, proper-noun & compound fallback."""
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
                if base_lem.endswith(("ć", "c")):
                    return base_lem
                return "nie" + base_lem

        # 3. Proper noun fallback (e.g. 'polsce' -> 'polska', 'krakowie' -> 'kraków')
        prop = self.proper_dominant_lemma.get(w)
        if prop is not None:
            return prop

        # 4. Hyphenated compounds (e.g. 'środkowo-wschodniej' -> 'środkowo-wschodni')
        if "-" in w:
            parts = w.split("-")
            head = parts[-1]
            head_lem = self.dominant_lemma.get(head) or self.proper_dominant_lemma.get(head)
            if head_lem is not None:
                return "-".join([*parts[:-1], head_lem])

        return w

    def get_paradigm(self, lemma_lower: str) -> set[str]:
        """Return all standard inflected forms for a common lemma."""
        return self.lemma_to_forms.get(lemma_lower, set())
