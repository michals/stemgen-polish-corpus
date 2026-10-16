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


def test_entity_decodes_before_filter() -> None:
    """Verify &eacute; decodes to é and is then dropped, never passed through."""
    cleaned = clean_text("słowo &eacute; inne")
    assert "&eacute;" not in cleaned
    assert "eacute" not in tokenize(cleaned)
    leftovers = tokenize(cleaned)
    assert "słowo" in leftovers
    assert "inne" in leftovers
    # The decoded é-token leaves no countable fragment behind.
    assert not any("e" == t for t in leftovers if t not in ("słowo", "inne"))


def test_nfd_foreign_input_drops_after_nfc() -> None:
    """Verify NFD e + combining acute composes to é under NFC, then drops."""
    nfd_cafe = "cafe\u0301"
    assert nfd_cafe != "café"  # guard: fixture really is decomposed
    cleaned = clean_text(f"słowo {nfd_cafe} inne")
    leftovers = tokenize(cleaned)
    assert "caf" not in leftovers
    assert "caf" not in cleaned
    assert "słowo" in leftovers
    assert "inne" in leftovers


def test_control_and_fffd_stripped() -> None:
    """Verify control characters and U+FFFD vanish while newlines survive."""
    cleaned = clean_text("słowo\x00\x01\x07 inne\ufffd dalsze")
    assert "\x00" not in cleaned
    assert "\ufffd" not in cleaned
    assert tokenize(cleaned) == ["słowo", "inne", "dalsze"]
    with_newline = clean_text("pierwszy akapit\n\ndrugi akapit")
    assert "\n" in with_newline


def test_quote_dash_normalization_without_resurrection() -> None:
    """Verify quote/dash variants normalize and never launder dropped tokens."""
    assert clean_text("„cytat”") == '"cytat"'
    assert clean_text("«cytat»") == '"cytat"'
    assert clean_text("słowo — inne") == "słowo - inne"
    assert clean_text("słowo – inne") == "słowo - inne"
    # Filter runs before punctuation normalization: no COVID-19 -> COVID salvage.
    cleaned = clean_text("model COVID-19 test")
    assert "COVID" not in tokenize(cleaned)
    assert "COVID" not in cleaned
    assert tokenize(cleaned) == ["model", "test"]


@pytest.mark.parametrize(
    "adversarial",
    [
        "",
        "   ",
        "\x00\x01\x02\ufffd",
        "&eacute;&eacute;&eacute;",
        "cafe\u0301",
        "COVID-19 2012 model3 Béziera Hübner",
        "„«»\"\"——–",
        "\n\n\n",
        "a\tb",
    ],
)
def test_clean_text_never_raises(adversarial: str) -> None:
    """Verify clean_text returns a string on adversarial input without raising."""
    result = clean_text(adversarial)
    assert isinstance(result, str)
