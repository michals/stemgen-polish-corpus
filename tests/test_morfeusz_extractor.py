from collections import Counter

from polish_corpus.morfeusz_extractor import MorfeuszDictionary


def test_filter_derivational_self_lemmas() -> None:
    """Verify productive gerunds and participles yield to verbal base lemmas."""
    # Gerund: 'badania' with candidates 'badanie' (ger) and 'badać' (verb)
    filtered = MorfeuszDictionary._filter_derivational_self_lemmas(
        "badania", ["badanie", "badać"]
    )
    assert filtered == ["badać"]

    # Passive participle: 'związane' with 'związany' (adj/ppas) and 'związać' (verb)
    filtered = MorfeuszDictionary._filter_derivational_self_lemmas(
        "związane", ["związany", "związać"]
    )
    assert filtered == ["związać"]

    # Active participle: 'wystarczający' with 'wystarczający' and 'wystarczać'
    filtered = MorfeuszDictionary._filter_derivational_self_lemmas(
        "wystarczający", ["wystarczający", "wystarczać"]
    )
    assert filtered == ["wystarczać"]

    # Non-derivational nouns: 'mam' with candidates 'mieć' and 'mama' (both kept)
    filtered = MorfeuszDictionary._filter_derivational_self_lemmas(
        "mam", ["mieć", "mama"]
    )
    assert set(filtered) == {"mieć", "mama"}


def test_resolve_homonyms_family_mass() -> None:
    """Verify Family Mass correctly attributes 'mam', 'mają', and 'miał' to 'mieć'."""
    morfeusz = MorfeuszDictionary()
    # Populate 'mieć' paradigm
    for form in ("mam", "ma", "mają", "miał", "miała", "mieli", "mieć"):
        morfeusz.word_to_lemmas[form]["mieć"] += 1
        morfeusz.lemma_to_forms["mieć"].add(form)

    # Populate 'mama' paradigm (competes on 'mam')
    for form in ("mama", "mamy", "mamie", "mamę", "mamą", "mam"):
        morfeusz.word_to_lemmas[form]["mama"] += 1
        morfeusz.lemma_to_forms["mama"].add(form)

    # Populate 'maja' paradigm (competes on 'mają')
    for form in ("maja", "mai", "mają"):
        morfeusz.word_to_lemmas[form]["maja"] += 1
        morfeusz.lemma_to_forms["maja"].add(form)

    # Populate 'miał' as fine coal noun
    for form in ("miał", "miału", "miałem"):
        morfeusz.word_to_lemmas[form]["miał"] += 1
        morfeusz.lemma_to_forms["miał"].add(form)

    # Corpus frequencies: 'ma' and 'mają' and 'miał' occur frequently; 'mama' occasionally; 'maja' rarely
    corpus_tf = Counter(
        {
            "ma": 500,
            "mają": 200,
            "miał": 300,
            "mam": 50,
            "mieć": 10,
            "mama": 30,
            "mamy": 20,
            "maja": 1,
            "miału": 1,
        }
    )

    resolved = morfeusz.resolve_homonyms(corpus_term_freq=corpus_tf)
    assert resolved["mam"] == "mieć"
    assert resolved["mają"] == "mieć"
    assert resolved["miał"] == "mieć"


def test_lookup_lemma_superlative() -> None:
    """Verify superlative naj- resolves to base adjective lemma."""
    morfeusz = MorfeuszDictionary()
    morfeusz.dominant_lemma["stary"] = "stary"
    morfeusz.dominant_lemma["starszy"] = "stary"
    morfeusz.dominant_lemma["starszych"] = "stary"
    morfeusz.dominant_lemma["ważny"] = "ważny"
    morfeusz.dominant_lemma["ważniejsze"] = "ważny"
    morfeusz.dominant_lemma["duży"] = "duży"
    morfeusz.dominant_lemma["większe"] = "duży"

    assert morfeusz.lookup_lemma("najstarszy") == "stary"
    assert morfeusz.lookup_lemma("najstarszych") == "stary"
    assert morfeusz.lookup_lemma("najważniejsze") == "ważny"
    assert morfeusz.lookup_lemma("największe") == "duży"


def test_lookup_lemma_compounds() -> None:
    """Verify hyphenated compounds resolve their head segment."""
    morfeusz = MorfeuszDictionary()
    morfeusz.dominant_lemma["wschodniej"] = "wschodni"
    morfeusz.dominant_lemma["czerwonych"] = "czerwony"
    morfeusz.dominant_lemma["gospodarczego"] = "gospodarczy"

    assert morfeusz.lookup_lemma("środkowo-wschodniej") == "środkowo-wschodni"
    assert morfeusz.lookup_lemma("biało-czerwonych") == "biało-czerwony"
    assert morfeusz.lookup_lemma("społeczno-gospodarczego") == "społeczno-gospodarczy"


def test_lookup_lemma_negation() -> None:
    """Verify negated participles/verbs resolve properly."""
    morfeusz = MorfeuszDictionary()
    # Verb base
    morfeusz.dominant_lemma["znany"] = "znać"
    assert morfeusz.lookup_lemma("nieznany") == "znać"

    # Adjective base
    morfeusz.dominant_lemma["bezpieczny"] = "bezpieczny"
    assert morfeusz.lookup_lemma("niebezpieczny") == "niebezpieczny"
