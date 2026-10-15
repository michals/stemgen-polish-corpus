"""Configuration and constants for the Polish General Corpus Builder."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Paths
PACKAGE_DIR = Path(__file__).parent.resolve()
REPO_ROOT = PACKAGE_DIR.parent.parent

_env_cache = os.environ.get("POLISH_CORPUS_CACHE")
if _env_cache:
    CACHE_DIR = Path(_env_cache).resolve()
elif (REPO_ROOT / "data_cache").exists():
    CACHE_DIR = (REPO_ROOT / "data_cache").resolve()
else:
    CACHE_DIR = (Path.cwd() / "data_cache").resolve()

DEFAULT_OUTPUT_BASE = (Path.cwd() / "dist").resolve()


def get_default_output_dir(tier_name: str) -> Path:
    """Return default output directory nested by tier name (e.g. ./dist/recommended)."""
    return DEFAULT_OUTPUT_BASE / tier_name


# URLs for Lexicons and Ground Truth
POLIMORF_URL = "https://download.sgjp.pl/morfeusz/20260823/polimorf-20260823.tab.gz"
SGJP_URL = "https://download.sgjp.pl/morfeusz/20260823/sgjp-20260823.tab.gz"
SJP_ODM_URL = "https://sjp.pl/sl/odmiany/sjp-odm-20260901.zip"
SNOWBALL_POLISH_VOC_URL = "https://raw.githubusercontent.com/snowballstem/snowball-data/master/polish/voc.txt"

# URLs for Corpus Text Sources
NKJP1M_TRAIN_URL = "https://huggingface.co/datasets/ipipan/nkjp1m/resolve/main/nkjp1m_train.jsonl.gz"
NKJP1M_DEV_URL = "https://huggingface.co/datasets/ipipan/nkjp1m/resolve/main/nkjp1m_dev.jsonl.gz"
NEWS_DEV_URL = "https://huggingface.co/datasets/allegro/summarization-polish-summaries-corpus/resolve/main/whole/dev.csv"
NEWS_TEST_URL = "https://huggingface.co/datasets/allegro/summarization-polish-summaries-corpus/resolve/main/whole/test.csv"
WIKINEURAL_PL_URL = "https://huggingface.co/datasets/Babelscape/wikineural/resolve/main/train_pl.jsonl"

LITERATURE_BOOKS = [
    ("lalka_1.txt", "https://wolnelektury.pl/media/book/txt/lalka-tom-pierwszy.txt"),
    ("lalka_2.txt", "https://wolnelektury.pl/media/book/txt/lalka-tom-drugi.txt"),
    ("faraon_1.txt", "https://wolnelektury.pl/media/book/txt/faraon-tom-pierwszy.txt"),
    ("krzyzacy_1.txt", "https://wolnelektury.pl/media/book/txt/krzyzacy-tom-pierwszy.txt"),
    ("quo_vadis.txt", "https://wolnelektury.pl/media/book/txt/quo-vadis.txt"),
    ("chlopi_1.txt", "https://wolnelektury.pl/media/book/txt/chlopi-czesc-pierwsza-jesien.txt"),
    ("pan_tadeusz.txt", "https://wolnelektury.pl/media/book/txt/pan-tadeusz.txt"),
]

# Core POS tags allowed for dictionary and ground truth
# (Excludes proper nouns, abbreviations, foreign words, punctuation, interpunction)
CORE_POS_TAGS = {
    "subst",   # Nouns
    "depr",    # Depreciative nouns
    "adj",     # Adjectives
    "adja",    # Adjectival forms (e.g. biało-czerwony)
    "adjp",    # Post-prepositional adjectives
    "adjc",    # Predicative adjectives
    "adv",     # Adverbs
    "fin",     # Finite verbs (present/future)
    "bedzie",  # Future tense of 'być'
    "aglt",    # Agglutinative past-tense markers (-em, -eś, etc.)
    "praet",   # Past tense verbs (l-participle)
    "impt",    # Imperative verbs
    "imps",    # Impersonal past forms (-no, -to)
    "inf",     # Infinitives
    "pcon",    # Contemporary adverbial participles (-ąc)
    "pant",    # Anterior adverbial participles (-wszy, -łszy)
    "ger",     # Gerunds (-nie, -cie)
    "pact",    # Active adjectival participles (-ący)
    "ppas",    # Passive adjectival participles (-any, -ony, -ty)
    "num",     # Numerals
    "ppron12", # 1st and 2nd person pronouns (ja, ty, my, wy)
    "ppron3",  # 3rd person pronouns (on, ona, oni)
    "siebie",  # Reflexive pronoun (siebie, się)
}

# Subdirectory genre layout and nominal token shares
GENRE_CONFIG = {
    "01_nkjp_spoken_forum": {"share": 0.25, "target_doc_words": 500},
    "02_nkjp_literature":   {"share": 0.20, "target_doc_words": 500},
    "03_nkjp_news":         {"share": 0.15, "target_doc_words": 500},
    "04_wikipedia":         {"share": 0.40, "target_doc_words": 500},
}


@dataclass(frozen=True)
class TierConfig:
    name: str
    target_tokens: int
    target_docs: int
    top_lemmas_for_paradigms: int


TIERS = {
    "compact": TierConfig(
        name="compact",
        target_tokens=2_200_000,
        target_docs=4_400,
        top_lemmas_for_paradigms=5_000,
    ),
    "recommended": TierConfig(
        name="recommended",
        target_tokens=5_150_000,
        target_docs=10_100,
        top_lemmas_for_paradigms=10_000,
    ),
    "extended": TierConfig(
        name="extended",
        target_tokens=12_500_000,
        target_docs=25_000,
        top_lemmas_for_paradigms=15_000,
    ),
}
