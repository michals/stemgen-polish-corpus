"""Unified orchestrator for Polish General Corpus building.

Usage:
  python builder.py --tier compact --output-dir dist/general
  python builder.py --quick-test
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .benchmark_splitter import (
    build_snowball_voc_ground_truth,
    create_lemma_stratified_split,
    export_records_to_parquet,
)
from .config import (
    CACHE_DIR,
    DEFAULT_OUTPUT_BASE,
    GENRE_CONFIG,
    TIERS,
    TierConfig,
    get_default_output_dir,
)
from .corpus_sampler import BalancedCorpusWriter
from .fetchers import ensure_all_text_sources, get_polimorf_path
from .morfeusz_extractor import MorfeuszDictionary
from .paradigm_generator import complete_paradigms
from .text_sources import (
    iter_literature_docs,
    iter_news_docs,
    iter_spoken_forum_docs,
    iter_wikipedia_docs,
)


def generate_seed_documents(genre: str, target_docs: int) -> list[str]:
    """Generate representative Polish text paragraphs for local testing and bootstrapping."""
    # Seed texts across the four target genres
    seeds = {
        "01_nkjp_spoken_forum": [
            "Cześć wszystkim! Czy wiecie może, jak najszybciej dojechać na dworzec centralny? "
            "Pociąg odjeżdża za pół godziny, a na drogach są ogromne korki. Myślę, że metro będzie "
            "najlepszym rozwiązaniem. Co sądzicie o tym pomyśle? Dajcie znać, czy ktoś z was "
            "już tak jechał dzisiaj rano. Chciałbym zdążyć przed odjazdem, bo następny kurs jest dopiero jutro.",
            "Moim zdaniem powinniśmy spotkać się jutro po południu i przedyskutować wszystkie szczegóły "
            "naszego projektu. Wszyscy zgadzamy się, że czas nagli, a zadania nie zostały jeszcze "
            "równomiernie podzielone. Zróbmy tak: przygotujcie swoje notatki, a my sprawdzimy je razem "
            "i ustalimy ostateczny plan działania na najbliższe tygodnie.",
        ],
        "02_nkjp_literature": [
            "Stary zegar na wieży ratuszowej wybił północ, a chłodny wiatr powoli przetaczał opadłe liście "
            "wzdłuż wąskich brukowanych uliczek. Janusz stał pod arkadami kamienicy, wpatrując się "
            "w ciemną toń rzeki. Pamiętał jeszcze czasy, gdy całe miasto tętniło gwarem kupców i podróżnych, "
            "lecz tamtej nocy panowała absolutna cisza. Wydawało się, że nawet cienie na murach zastygły w bezruchu.",
            "Wiosenne słońce przedzierało się przez gęste gałęzie sosen, rzucając złociste plamy na leśną ścieżkę. "
            "Szli powoli, wsłuchując się w radosny śpiew ptaków i delikatny szum strumienia płynącego w dolinie. "
            "Każdy krok przynosił poczucie spokoju, którego tak bardzo brakowało im podczas długiej zimy w stolicy.",
        ],
        "03_nkjp_news": [
            "Wczoraj w ministerstwie gospodarki odbyła się oficjalna konferencja prasowa dotycząca "
            "nowych programów wsparcia dla przedsiębiorstw z sektora nowoczesnych technologii. "
            "Rząd zapowiedział przeznaczenie znaczących środków na badania i rozwój oraz ulgi podatkowe "
            "dla innowacyjnych firm. Eksperci podkreślają, że decyzja ta może przyczynić się do wzrostu "
            "konkurencyjności krajowego rynku w Europie Środkowo-Wschodniej.",
            "Główny Urząd Statystyczny opublikował najnowsze dane na temat dynamiki inflacji i wzrostu PKB "
            "w minionym kwartale. Wyniki wskazują na stopniową stabilizację cen żywności oraz surowców energetycznych, "
            "co spotkało się z pozytywną reakcją rynków finansowych i inwestorów zagranicznych.",
        ],
        "04_wikipedia": [
            "Kraków jest jednym z najstarszych miast w Polsce o bogatej historii i tradycji uniwersyteckiej. "
            "Przez wiele stuleci pełnił funkcję stolicy państwa oraz siedziby polskich królów na Wawelu. "
            "Współcześnie stanowi kluczowy ośrodek akademicki, kulturalny i gospodarczy kraju, a jego "
            "historyczne centrum zostało wpisane na pierwszą listę światowego dziedzictwa UNESCO w roku 1978.",
            "Wisła to najdłuższa rzeka Polski o długości ponad tysiąca kilometrów, uchodząca do Zatoki Gdańskiej. "
            "Jej dorzecze obejmuje znaczną część terytorium kraju, wpływając na warunki hydrologiczne "
            "oraz rozwój gospodarczy wielu miast położonych wzdłuż jej biegu od Beskidów aż po Morze Bałtyckie.",
        ],
    }

    base_texts = seeds.get(genre, seeds["03_nkjp_news"])
    docs: list[str] = []
    for i in range(target_docs):
        # Repeat and combine seed texts to form a natural document
        text = "\n\n".join(base_texts * 3) + f"\n\nDokument numer {i+1} w kategorii {genre}."
        docs.append(text)
    return docs


def build_polish_corpus(
    tier_name: str = "recommended",
    output_dir: Path | str | None = None,
    polimorf_path: Path | None = None,
    quick_test: bool = False,
    force_download: bool = False,
) -> int:
    """Build the complete general Polish corpus package according to the strategy."""
    tier: TierConfig = TIERS.get(tier_name, TIERS["recommended"])
    out_dir = get_default_output_dir(tier.name) if output_dir is None else Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("POLISH GENERAL CORPUS BUILDER")
    print(f"Tier: {tier.name} (target {tier.target_tokens:,} tokens, ~{tier.target_docs:,} docs)")
    print(f"Output Directory: {out_dir}")
    print(f"Quick Test Mode: {quick_test}")
    print("=" * 70)

    t0 = time.perf_counter()

    # 1. Fetch resources
    if not quick_test:
        ensure_all_text_sources(force=force_download)

    sjp_path = CACHE_DIR / "sjp_odm.zip"
    if polimorf_path is None:
        try:
            polimorf_path = get_polimorf_path(force=force_download)
        except Exception as e:
            print(f"[Notice] Live PoliMorf download skipped ({e}). Checking local cache...")
            cached_polimorf = CACHE_DIR / "polimorf-20260823.tab.gz"
            polimorf_path = cached_polimorf if cached_polimorf.exists() else None

    # 2. Ingest dictionary (PoliMorf, SJP odm.zip, or bootstrap)
    morfeusz = MorfeuszDictionary()
    if polimorf_path and polimorf_path.exists() and polimorf_path.stat().st_size > 0:
        max_rows = 50_000 if quick_test else None
        morfeusz.ingest_polimorf(polimorf_path, max_rows=max_rows, verbose=True)
    elif sjp_path.exists() and sjp_path.stat().st_size > 0:
        max_lines = 10_000 if quick_test else None
        morfeusz.ingest_sjp_odm(sjp_path, max_lines=max_lines, verbose=True)
    else:
        print("[Notice] Using internal core Polish morphological bootstrap for dictionary...")
        bootstrap_data = [
            ("jest", "być", "fin"), ("są", "być", "fin"), ("był", "być", "praet"), ("była", "być", "praet"),
            ("będzie", "być", "bedzie"), ("będą", "być", "bedzie"), ("być", "być", "inf"),
            ("człowiek", "człowiek", "subst"), ("ludzie", "człowiek", "subst"), ("ludzi", "człowiek", "subst"),
            ("dzień", "dzień", "subst"), ("dnia", "dzień", "subst"), ("dni", "dzień", "subst"),
            ("rok", "rok", "subst"), ("lata", "rok", "subst"), ("lat", "rok", "subst"),
            ("ręka", "ręka", "subst"), ("ręce", "ręka", "subst"), ("rąk", "ręka", "subst"),
            ("miasto", "miasto", "subst"), ("miasta", "miasto", "subst"), ("miast", "miasto", "subst"),
            ("nowy", "nowy", "adj"), ("nowa", "nowy", "adj"), ("nowe", "nowy", "adj"), ("nowych", "nowy", "adj"),
            ("dobry", "dobry", "adj"), ("dobra", "dobry", "adj"), ("dobre", "dobry", "adj"),
            ("robić", "robić", "inf"), ("robi", "robić", "fin"), ("robią", "robić", "fin"),
            ("mówić", "mówić", "inf"), ("mówi", "mówić", "fin"), ("mówią", "mówić", "fin"),
            ("iść", "iść", "inf"), ("idzie", "iść", "fin"), ("idą", "iść", "fin"), ("szedł", "iść", "praet"),
        ]
        for form, lemma, _pos in bootstrap_data:
            morfeusz.word_to_lemmas[form][lemma] += 1
            morfeusz.lemma_to_forms[lemma].add(form)

    # 3. Stream balanced documents into corpus.zip
    corpus_zip_path = out_dir / "corpus.zip"
    writer = BalancedCorpusWriter(corpus_zip_path)

    total_docs_to_generate = 20 if quick_test else tier.target_docs
    print(f"\n[CorpusBuilder] Writing multi-genre balanced documents to {corpus_zip_path.name}...")

    genre_streams = {
        "01_nkjp_spoken_forum": iter_spoken_forum_docs,
        "02_nkjp_literature": iter_literature_docs,
        "03_nkjp_news": iter_news_docs,
        "04_wikipedia": iter_wikipedia_docs,
    }

    for genre, g_cfg in GENRE_CONFIG.items():
        genre_docs = max(1, int(total_docs_to_generate * g_cfg["share"]))
        stream_fn = genre_streams.get(genre)
        added_docs = 0
        if stream_fn and not quick_test:
            doc_iter = stream_fn(genre_docs)
            added_docs = writer.add_documents_for_genre(genre, doc_iter, genre_docs)

        if added_docs < genre_docs:
            missing = genre_docs - added_docs
            if not quick_test and missing > 0:
                print(f"  [Notice] {genre} added {added_docs}/{genre_docs} docs; completing with {missing} seed documents.")
            fallback_iter = iter(generate_seed_documents(genre, missing))
            added_docs += writer.add_documents_for_genre(genre, fallback_iter, missing)

        print(f"  + Added {added_docs:,} docs for {genre}")

    # 4. Resolve homonyms using corpus term frequencies
    print("\n[CorpusBuilder] Resolving homonyms using corpus frequencies...")
    morfeusz.resolve_homonyms(lemma_frequency_fn=lambda lem: writer.term_freq.get(lem, 0))

    # 5. Morfeusz Paradigm Completion (Step 4 of Strategy)
    top_n_lemmas = 50 if quick_test else tier.top_lemmas_for_paradigms
    complete_paradigms(writer, morfeusz, top_n_lemmas=top_n_lemmas, verbose=True)

    writer.close()
    corpus_summary = writer.summary()
    print(
        f"\n[CorpusBuilder] Corpus archive finalized: "
        f"{corpus_summary['total_documents']:,} docs, "
        f"{corpus_summary['total_tokens']:,} tokens, "
        f"{corpus_summary['unique_vocabulary']:,} unique words "
        f"({corpus_summary['archive_size_bytes'] / (1024*1024):.2f} MB)."
    )

    # 6. Build and export Ground Truth (word, lemma, tf, df)
    print("\n[CorpusBuilder] Building Ground Truth table (word, lemma, tf, df)...")
    gt_records: list[tuple[str, str, int, int]] = []
    for word, tf in writer.term_freq.items():
        lemma = morfeusz.dominant_lemma.get(word, word)
        df = writer.doc_freq.get(word, 1)
        gt_records.append((word, lemma, tf, df))

    gt_parquet_path = out_dir / "ground_truth.parquet"
    export_records_to_parquet(gt_records, gt_parquet_path)
    print(f"[CorpusBuilder] Exported {len(gt_records):,} ground truth records to {gt_parquet_path.name}.")

    # 7. Generate 80/20 Lemma-Stratified Holdout Split
    train_records, test_records = create_lemma_stratified_split(gt_records, train_ratio=0.80)
    train_path = out_dir / "ground_truth_train.parquet"
    test_path = out_dir / "ground_truth_test.parquet"
    export_records_to_parquet(train_records, train_path)
    export_records_to_parquet(test_records, test_path)
    print(
        f"[CorpusBuilder] 80/20 Stratified Split: "
        f"{len(train_records):,} train records, {len(test_records):,} test records."
    )

    # 8. Snowball voc.txt Benchmark Dataset
    try:
        snowball_voc_records = build_snowball_voc_ground_truth(morfeusz)
        if snowball_voc_records:
            snowball_gt_path = out_dir / "snowball_voc_ground_truth.parquet"
            export_records_to_parquet(snowball_voc_records, snowball_gt_path)
            print(f"[CorpusBuilder] Exported {len(snowball_voc_records):,} Snowball voc records to {snowball_gt_path.name}.")
    except Exception as e:
        print(f"[Notice] Snowball voc.txt skipped: {e}")

    # 9. Write Domain README.md and metadata JSON
    domain_readme = out_dir / "README.md"
    domain_readme.write_text(
        f"""# Domain Corpus: Polish General Language (general)

Representative, balanced corpus for generic Polish language stemming and retrieval benchmarks.

## Characteristics
- **Tier**: `{tier.name}`
- **Total Documents**: {corpus_summary['total_documents']:,}
- **Total Tokens**: {corpus_summary['total_tokens']:,}
- **Unique Vocabulary**: {corpus_summary['unique_vocabulary']:,}
- **Ground Truth Source**: Morfeusz 2 / PoliMorf (2-Clause BSD)
- **Genres**:
  - `01_nkjp_spoken_forum/`: Spoken and dialogue transcripts
  - `02_nkjp_literature/`: Narrative fiction and prose
  - `03_nkjp_news/`: Journalism and press
  - `04_wikipedia/`: Polish Wikipedia articles
  - `99_morfeusz_paradigms/`: Paradigm completion for Top-{top_n_lemmas:,} lemmas

## Files
- `corpus.zip`: Universal hierarchical document archive.
- `ground_truth.parquet`: Full ground truth table `(word, lemma, tf, df)`.
- `ground_truth_train.parquet`: 80% lemma-stratified training partition.
- `ground_truth_test.parquet`: 20% held-out test partition (Zero-Shot lemma validation).
""",
        encoding="utf-8",
    )

    summary_file = out_dir / "build_summary.json"
    summary_file.write_text(
        json.dumps(
            {
                "tier": tier.name,
                "elapsed_seconds": round(time.perf_counter() - t0, 2),
                "summary": corpus_summary,
                # Top-level copy mirrors summary["audit_rates"] for direct
                # gate/consumer access; both reference the same writer dict.
                "audit_rates": corpus_summary["audit_rates"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    elapsed = time.perf_counter() - t0
    print(f"\n[CorpusBuilder] All tasks successfully completed in {elapsed:.2f}s!")
    return 0


def main() -> None:
    from .cli import main as cli_main

    sys.exit(cli_main())


if __name__ == "__main__":
    main()
