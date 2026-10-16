import zipfile

import pytest

from polish_corpus.corpus_sampler import BalancedCorpusWriter
from polish_corpus.text_cleaning import clean_text, tokenize


@pytest.mark.parametrize(
    "dirty",
    [
        "Béziera",
        "café",
        "COVID-19",
    ],
)
def test_foreign_tokens_drop_whole(dirty: str) -> None:
    """Verify foreign/numeric tokens vanish entirely, leaving no fragments."""
    cleaned = clean_text(f"słowo {dirty} inne")
    leftovers = tokenize(cleaned)
    assert dirty not in leftovers
    for fragment in ("ziera", "caf", "COVID"):
        assert fragment not in leftovers
        assert fragment not in cleaned
    # Surrounding Polish signal is preserved.
    assert "słowo" in leftovers
    assert "inne" in leftovers


def test_hyphenated_polish_compound_retained() -> None:
    """Verify biało-czerwony survives cleaning and tokenization."""
    assert clean_text("biało-czerwony") == "biało-czerwony"
    assert tokenize("flaga biało-czerwony powiewa") == ["flaga", "biało-czerwony", "powiewa"]


def test_stored_text_and_counts_agree(tmp_path) -> None:
    """Verify re-tokenizing stored zip text reproduces recorded TF/DF."""
    writer = BalancedCorpusWriter(tmp_path / "corpus.zip")
    writer.add_document(
        "04_wikipedia",
        "Béziera przyjechała do café na COVID-19 oraz biało-czerwony sztandar",
    )
    writer.close()

    with zipfile.ZipFile(tmp_path / "corpus.zip") as archive:
        stored = archive.read("04_wikipedia/doc_00001.txt").decode("utf-8")

    assert "ziera" not in stored
    assert "caf" not in stored
    assert "COVID" not in stored
    assert "biało-czerwony" in stored

    retokenized = [t.lower() for t in tokenize(stored)]
    assert sorted(retokenized) == sorted(writer.term_freq.elements())
    assert set(retokenized) == set(writer.doc_freq)
