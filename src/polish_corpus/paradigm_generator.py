"""Inflectional paradigm completion for top lemmas.

Completes inflected forms for high-frequency vocabulary:
- Finds top N lemmas by corpus token frequency.
- Retrieves all standard inflected forms from MorfeuszDictionary.
- Identifies forms missing from natural text or needing paradigm reinforcement.
- Emits them in batches into 99_morfeusz_paradigms/*.txt with floor TF=1.
"""

from __future__ import annotations

from .corpus_sampler import BalancedCorpusWriter
from .morfeusz_extractor import MorfeuszDictionary


def complete_paradigms(
    writer: BalancedCorpusWriter,
    morfeusz: MorfeuszDictionary,
    top_n_lemmas: int = 10_000,
    batch_size: int = 1_500,
    verbose: bool = True,
) -> tuple[int, int]:
    """Ensure all inflected forms of top N lemmas exist in the corpus archive.

    Returns:
        (total_paradigms_checked, missing_forms_added)
    """
    if verbose:
        print(f"[ParadigmGenerator] Ranking lemmas to select top {top_n_lemmas:,}...")

    # Calculate lemma frequencies from existing corpus term frequencies
    lemma_freq: dict[str, int] = {}
    for word, tf in writer.term_freq.items():
        lemma = morfeusz.dominant_lemma.get(word)
        if lemma:
            lemma_freq[lemma] = lemma_freq.get(lemma, 0) + tf

    # Sort lemmas by descending frequency
    ranked_lemmas = sorted(lemma_freq.keys(), key=lambda lem: lemma_freq[lem], reverse=True)
    selected_lemmas = ranked_lemmas[:top_n_lemmas]

    if verbose:
        print(f"[ParadigmGenerator] Selected {len(selected_lemmas):,} top lemmas. Checking missing inflections...")

    missing_forms: list[str] = []
    current_vocab = writer.term_freq

    for lemma in selected_lemmas:
        all_forms = morfeusz.get_paradigm(lemma)
        for form in all_forms:
            if form not in current_vocab:
                missing_forms.append(form)

    if verbose:
        print(
            f"[ParadigmGenerator] Found {len(missing_forms):,} missing inflected forms. "
            f"Writing to 99_morfeusz_paradigms/ in batches of {batch_size}..."
        )

    # Write missing forms in batches
    batch_count = 0
    for i in range(0, len(missing_forms), batch_size):
        batch = missing_forms[i : i + batch_size]
        batch_count += 1
        writer.add_paradigm_batch(batch_count, batch)

    if verbose:
        print(
            f"[ParadigmGenerator] Completed: Added {len(missing_forms):,} forms across {batch_count} paradigm files."
        )

    return len(selected_lemmas), len(missing_forms)
