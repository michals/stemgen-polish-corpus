"""Download and caching utilities for Polish external corpora and dictionaries."""

from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

from .config import (
    CACHE_DIR,
    LITERATURE_BOOKS,
    NEWS_DEV_URL,
    NEWS_TEST_URL,
    NEWS_TRAIN_URL,
    NKJP1M_DEV_URL,
    NKJP1M_TRAIN_URL,
    POLIMORF_URL,
    SJP_ODM_URL,
    SNOWBALL_POLISH_VOC_URL,
    WIKINEURAL_PL_URL,
)


def download_file(url: str, dest_path: Path, force: bool = False) -> Path:
    """Download a file with caching."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists() and not force and dest_path.stat().st_size > 0:
        print(f"[Cache Hit] {dest_path.name} already exists ({dest_path.stat().st_size:,} bytes).")
        return dest_path

    temp_path = dest_path.with_suffix(dest_path.suffix + ".part")
    print(f"[Downloading] {url} -> {dest_path.name}...")
    headers = {"User-Agent": "stemgen-polish-corpus/1.0"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp, open(temp_path, "wb") as out_f:
        shutil.copyfileobj(resp, out_f)

    temp_path.rename(dest_path)
    print(f"[Downloaded] {dest_path.name} ({dest_path.stat().st_size:,} bytes).")
    return dest_path


def get_polimorf_path(force: bool = False) -> Path:
    """Ensure PoliMorf tab.gz is downloaded and return its path."""
    dest = CACHE_DIR / "polimorf-20260823.tab.gz"
    return download_file(POLIMORF_URL, dest, force=force)


def get_sjp_odm_path(force: bool = False) -> Path:
    """Ensure SJP odm.zip is downloaded and return its path."""
    dest = CACHE_DIR / "sjp_odm.zip"
    return download_file(SJP_ODM_URL, dest, force=force)


def get_snowball_voc_path(force: bool = False) -> Path:
    """Ensure Snowball Polish voc.txt is downloaded and return its path."""
    dest = CACHE_DIR / "snowball_voc.txt"
    return download_file(SNOWBALL_POLISH_VOC_URL, dest, force=force)


def get_nkjp1m_paths(force: bool = False) -> tuple[Path, Path]:
    """Ensure NKJP1M train and dev files are downloaded."""
    train = CACHE_DIR / "nkjp1m_train.jsonl.gz"
    dev = CACHE_DIR / "nkjp1m_dev.jsonl.gz"
    download_file(NKJP1M_TRAIN_URL, train, force=force)
    download_file(NKJP1M_DEV_URL, dev, force=force)
    return train, dev


def get_news_paths(force: bool = False) -> tuple[Path, Path, Path]:
    """Ensure Polish news articles CSVs are downloaded."""
    train = CACHE_DIR / "news_train.csv"
    dev = CACHE_DIR / "news_articles.csv"
    test = CACHE_DIR / "news_test.csv"
    download_file(NEWS_TRAIN_URL, train, force=force)
    download_file(NEWS_DEV_URL, dev, force=force)
    download_file(NEWS_TEST_URL, test, force=force)
    return train, dev, test


def get_wikipedia_path(force: bool = False) -> Path:
    """Ensure Polish Wikipedia JSONL is downloaded."""
    dest = CACHE_DIR / "wiki_pl.jsonl"
    return download_file(WIKINEURAL_PL_URL, dest, force=force)


def get_literature_dir(force: bool = False) -> Path:
    """Ensure classic Polish literature books are downloaded."""
    dest_dir = CACHE_DIR / "literature"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for filename, url in LITERATURE_BOOKS:
        dest_file = dest_dir / filename
        try:
            download_file(url, dest_file, force=force)
        except Exception as e:
            print(f"[Warning] Failed to download {filename} from {url} ({e}). Continuing...")
    return dest_dir


def ensure_all_text_sources(force: bool = False) -> None:
    """Download all external multi-genre text sources if missing."""
    print("\n[Fetchers] Checking and downloading required multi-genre text sources...")
    try:
        get_nkjp1m_paths(force=force)
    except Exception as e:
        print(f"[Warning] Failed to fetch NKJP1M ({e}). Will fallback to local data/seeds if missing.")

    try:
        get_literature_dir(force=force)
    except Exception as e:
        print(f"[Warning] Failed to fetch Wolne Lektury ({e}). Will fallback to local data/seeds if missing.")

    try:
        get_news_paths(force=force)
    except Exception as e:
        print(f"[Warning] Failed to fetch news corpus ({e}). Will fallback to local data/seeds if missing.")

    try:
        get_wikipedia_path(force=force)
    except Exception as e:
        print(f"[Warning] Failed to fetch Polish Wikipedia ({e}). Will fallback to local data/seeds if missing.")
