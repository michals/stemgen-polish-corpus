"""Lemma-stratified holdout split and Snowball benchmark evaluator.

Features:
- 80/20 Lemma-Stratified split (Zero-Shot Lemma evaluation).
- Benchmark test set generator against official snowball-data/polish/voc.txt.
"""

from __future__ import annotations

import random
from pathlib import Path

from .fetchers import get_snowball_voc_path
from .morfeusz_extractor import MorfeuszDictionary


def create_lemma_stratified_split(
    word_lemma_pairs: list[tuple[str, str, int, int]],
    train_ratio: float = 0.80,
    seed: int = 42,
) -> tuple[list[tuple[str, str, int, int]], list[tuple[str, str, int, int]]]:
    """Partition records by lemma into train and held-out test splits.

    Ensures that ALL surface forms of a held-out test lemma appear strictly in the test set.
    """
    rng = random.Random(seed)

    # Group records by lemma
    lemma_to_records: dict[str, list[tuple[str, str, int, int]]] = {}
    for item in word_lemma_pairs:
        lemma = item[1]
        lemma_to_records.setdefault(lemma, []).append(item)

    all_lemmas = list(lemma_to_records.keys())
    rng.shuffle(all_lemmas)

    split_idx = int(len(all_lemmas) * train_ratio)
    train_lemmas = set(all_lemmas[:split_idx])
    set(all_lemmas[split_idx:])

    train_records: list[tuple[str, str, int, int]] = []
    test_records: list[tuple[str, str, int, int]] = []

    for lemma, records in lemma_to_records.items():
        if lemma in train_lemmas:
            train_records.extend(records)
        else:
            test_records.extend(records)

    return train_records, test_records


def build_snowball_voc_ground_truth(
    morfeusz: MorfeuszDictionary,
    voc_path: Path | None = None,
) -> list[tuple[str, str, int, int]]:
    """Annotate official Snowball voc.txt words with Morfeusz 2 dominant lemmas."""
    if voc_path is None:
        voc_path = get_snowball_voc_path()

    records: list[tuple[str, str, int, int]] = []
    with open(voc_path, encoding="utf-8") as f:
        for line in f:
            word = line.strip().lower()
            if not word:
                continue
            lemma = morfeusz.dominant_lemma.get(word)
            if lemma:
                records.append((word, lemma, 1, 1))

    return records


def export_records_to_parquet(
    records: list[tuple[str, str, int, int]],
    output_path: Path,
) -> None:
    """Save records (word, lemma, tf, df) to a Parquet table matching universal schema."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as err:
        raise ImportError(
            "pyarrow is required to export parquet datasets. "
            "Please install it with: pip install pyarrow"
        ) from err

    output_path.parent.mkdir(parents=True, exist_ok=True)
    words = [r[0] for r in records]
    lemmas = [r[1] for r in records]
    tfs = [r[2] for r in records]
    dfs = [r[3] for r in records]

    table = pa.Table.from_arrays(
        [
            pa.array(words, type=pa.string()),
            pa.array(lemmas, type=pa.string()),
            pa.array(tfs, type=pa.int64()),
            pa.array(dfs, type=pa.int64()),
        ],
        names=["word", "lemma", "tf", "df"],
    )
    pq.write_table(table, output_path, compression="zstd")
