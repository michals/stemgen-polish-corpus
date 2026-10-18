"""Independent zero-foreign-fragment gate for built corpus tiers.

Re-tokenizes every stored ``corpus.zip`` doc and the ``ground_truth.parquet``
word column with the shared :func:`tokenize` / :func:`is_valid_token`
contract, then cross-checks the script-measured evidence against the
writer-reported ``audit_rates`` in ``build_summary.json``.

The script never reads writer memory — every number it checks is derived
from stored bytes — so a passing gate means the artifacts themselves are
clean, not that the writer agrees with itself (no self-grading).

X4 detects observable residue in stored bytes; absence of salvage
derivation (Polish-looking fragments kept from foreign words) is pinned
by test_audit_row_leaves_no_salvage, not by this gate.

Cross-checks (any mismatch fails the gate):
  X1 stored/counts agreement — the per-word TF multiset re-tokenized from
     stored docs (all genres, paradigms included) equals the GT word->tf map.
  X2 tokens_kept agreement — script-measured non-paradigm stored tokens equal
     the writer-reported global ``tokens_kept``.
  X3 rate arithmetic — writer-reported rates recompute from reported counts.
  X4 zero fragments — no foreign/digit/control residue in docs or GT words.

Exit 0 iff all cross-checks pass; nonzero otherwise. ``[Verify]`` print tags.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from polish_corpus.text_cleaning import TOKEN_RE, is_valid_token, tokenize

# Polish alphabet class, mirrored from text_cleaning for gate independence:
# the gate must not share the private regex, only the public contract above.
_POLISH_LETTER_RE = re.compile(r"[a-zA-ZąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")

PARADIGM_GENRE = "99_morfeusz_paradigms"

# Core Polish function words (at least 14 of the top-20 highest-TF words must be from this set)
_CORE_POLISH_FUNCTION_WORDS = {
    "w", "i", "na", "z", "do", "nie", "się", "to", "o", "jak", "że", "po",
    "od", "przez", "dla", "za", "który", "których", "które", "która", "tym",
    "tego", "ten", "tej", "te", "jest", "był", "była", "było", "są", "być",
    "oraz", "ale", "czy", "już", "tylko", "tak", "jego", "jej", "ich", "przy",
    "jako", "przed", "pod", "nad", "bez", "ze", "we", "co", "gdy", "lub",
}

CANARY_LEMMA_PROBES: dict[str, set[str]] = {
    # Homonyms that previously resolved to 'mama', 'maja', or self-lemmas:
    "mam": {"mieć"},
    "mają": {"mieć"},
    "miał": {"mieć"},
    "jest": {"być"},
    "są": {"być"},
    "będzie": {"być"},
    # Superlatives that previously missed PoliMorf and mapped to themselves:
    "najstarszy": {"stary"},
    "najstarszych": {"stary"},
    "najważniejsze": {"ważny"},
    "największe": {"duży", "wielki"},
    "najlepszy": {"dobry"},
    # Verbal nouns & participles that previously split from their parent verb:
    "badania": {"badać"},
    "zadania": {"zadać", "zadanie"},
    "związane": {"związać"},
    "wpisane": {"wpisać"},
    "wystarczający": {"wystarczać"},
    # Suppletive nouns:
    "ludzie": {"człowiek"},
    "ludzi": {"człowiek"},
    "lata": {"rok"},
    "latach": {"rok"},
    "dnia": {"dzień"},
}


def scan_text(text: str) -> list[str]:
    """Return violation descriptions for foreign/digit residue in stored text."""
    violations: list[str] = []
    for hit in TOKEN_RE.findall(text):
        if not is_valid_token(hit):
            violations.append(f"invalid-token {hit!r}")
    for ch in text:
        if ch in ("\n", "\t"):
            continue
        if ch == "\ufffd" or unicodedata.category(ch).startswith("C"):
            violations.append(f"stripped-char U+{ord(ch):04X}")
        elif ch.isdigit():
            violations.append(f"digit-char {ch!r}")
        elif unicodedata.category(ch).startswith("L") and _POLISH_LETTER_RE.fullmatch(ch) is None:
            violations.append(f"foreign-char {ch!r} (U+{ord(ch):04X})")
    return violations


@dataclass
class GenreScan:
    """Per-genre scan outcome for one zip subdirectory."""

    genre: str
    docs: int = 0
    tokens: int = 0
    unique_doc_hashes: set[str] = field(default_factory=set)
    sentence_terminators: int = 0
    violations: list[str] = field(default_factory=list)


@dataclass
class GroundTruthScan:
    """Outcome of the GT word-column scan."""

    words: int = 0
    invalid_words: list[str] = field(default_factory=list)
    tf_total: int = 0


@dataclass
class GateReport:
    """Full gate outcome across zip docs, GT parquet, and summary cross-check."""

    genres: dict[str, GenreScan] = field(default_factory=dict)
    gt: GroundTruthScan = field(default_factory=GroundTruthScan)
    writer_rates: dict = field(default_factory=dict)
    cross_checks: dict[str, bool] = field(default_factory=dict)
    telemetry: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def doc_violations(self) -> int:
        """Return total stored-doc violation count across genres."""
        return sum(len(scan.violations) for scan in self.genres.values())

    @property
    def passed(self) -> bool:
        """Return True iff zero fragments and every cross-check agrees."""
        return (
            not self.errors
            and not self.gt.invalid_words
            and self.doc_violations == 0
            and all(self.cross_checks.values())
            and bool(self.cross_checks)
        )


def scan_corpus_zip(zip_path: Path) -> tuple[dict[str, GenreScan], dict[str, int]]:
    """Re-tokenize every stored doc; return per-genre scans plus TF multiset."""
    genres: dict[str, GenreScan] = {}
    tf: dict[str, int] = {}
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            genre = name.split("/", 1)[0] if "/" in name else "(root)"
            scan = genres.setdefault(genre, GenreScan(genre))
            try:
                text = archive.read(name).decode("utf-8")
            except UnicodeDecodeError:
                scan.violations.append(f"undecodable-bytes {name}")
                continue
            scan.docs += 1
            if genre != PARADIGM_GENRE:
                h = hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()
                scan.unique_doc_hashes.add(h)
                scan.sentence_terminators += sum(text.count(p) for p in (".", "!", "?"))
            tokens = [t.lower() for t in tokenize(text)]
            scan.tokens += len(tokens)
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            for violation in scan_text(text):
                scan.violations.append(f"{name}: {violation}")
    return genres, tf


def scan_ground_truth(
    parquet_path: Path,
) -> tuple[GroundTruthScan, dict[str, int], dict[str, str]]:
    """Scan the GT table; return scan outcome, word->tf map, and word->lemma map."""
    import pyarrow.parquet as pq

    scan = GroundTruthScan()
    gt_tf: dict[str, int] = {}
    gt_word_to_lemma: dict[str, str] = {}
    table = pq.read_table(parquet_path, columns=["word", "lemma", "tf"])
    words = table.column("word").to_pylist()
    lemmas = table.column("lemma").to_pylist()
    tfs = table.column("tf").to_pylist()
    for word, lemma, tf_value in zip(words, lemmas, tfs, strict=True):
        w_str = str(word)
        l_str = str(lemma)
        scan.words += 1
        scan.tf_total += int(tf_value)
        gt_tf[w_str] = int(tf_value)
        gt_word_to_lemma[w_str] = l_str
        if not is_valid_token(w_str):
            scan.invalid_words.append(w_str)
    return scan, gt_tf, gt_word_to_lemma


def _rates_recompute_ok(entry: dict) -> bool:
    """Return True iff a writer rate entry recomputes from its own counts."""
    import math

    foreign = entry.get("foreign_dropped", 0)
    digit = entry.get("digit_dropped", 0)
    kept = entry.get("tokens_kept", 0)
    if entry.get("dropped_total", 0) != foreign + digit:
        return False
    denom = foreign + digit + kept
    expected_foreign = (foreign / denom) if denom else 0.0
    expected_digit = (digit / denom) if denom else 0.0
    return math.isclose(
        entry.get("foreign_fragment_rate", -1.0), expected_foreign, rel_tol=1e-9, abs_tol=1e-12
    ) and math.isclose(
        entry.get("digit_token_rate", -1.0), expected_digit, rel_tol=1e-9, abs_tol=1e-12
    )


def check_dist_dir(dist_dir: Path) -> GateReport:
    """Run the full gate against stored build artifacts in ``dist_dir``."""
    report = GateReport()
    dist_dir = Path(dist_dir)
    zip_path = dist_dir / "corpus.zip"
    parquet_path = dist_dir / "ground_truth.parquet"
    summary_path = dist_dir / "build_summary.json"
    for path in (zip_path, parquet_path, summary_path):
        if not path.exists():
            report.errors.append(f"missing artifact {path}")
    if report.errors:
        return report

    try:
        report.genres, stored_tf = scan_corpus_zip(zip_path)
    except zipfile.BadZipFile as err:
        report.errors.append(f"unreadable corpus.zip: {err}")
        return report
    try:
        report.gt, gt_tf, gt_word_to_lemma = scan_ground_truth(parquet_path)
    except Exception as err:  # ArrowInvalid, ValueError (ragged columns), OSError
        report.errors.append(f"unreadable ground_truth.parquet: {err}")
        return report
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as err:
        report.errors.append(f"unreadable build_summary.json: {err}")
        return report
    rates = summary.get("audit_rates") or summary.get("summary", {}).get("audit_rates") or {}
    report.writer_rates = rates

    # X1: stored/counts agreement — re-tokenized TF equals GT word->tf exactly.
    report.cross_checks["stored_counts_agree"] = stored_tf == gt_tf
    # X2: script-measured non-paradigm stored tokens equal writer tokens_kept.
    stored_kept = sum(
        scan.tokens for genre, scan in report.genres.items() if genre != PARADIGM_GENRE
    )
    global_entry = rates.get("global", {}) if isinstance(rates, dict) else {}
    report.cross_checks["tokens_kept_agree"] = isinstance(
        global_entry, dict
    ) and stored_kept == global_entry.get("tokens_kept", -1)
    # X3: writer rate arithmetic recomputes from writer counts.
    entries = [global_entry] if isinstance(global_entry, dict) else []
    per_genre = rates.get("per_genre", {}) if isinstance(rates, dict) else {}
    if isinstance(per_genre, dict):
        entries.extend(e for e in per_genre.values() if isinstance(e, dict))
    report.cross_checks["rate_arithmetic_ok"] = bool(entries) and all(
        _rates_recompute_ok(e) for e in entries
    )
    # X4: zero fragments in stored docs and GT words.
    report.cross_checks["zero_fragments"] = (
        report.doc_violations == 0 and not report.gt.invalid_words
    )

    # Compute telemetry across natural (non-paradigm) genres:
    natural_scans = [scan for genre, scan in report.genres.items() if genre != PARADIGM_GENRE]
    total_natural_docs = sum(s.docs for s in natural_scans)
    total_natural_tokens = sum(s.tokens for s in natural_scans)
    all_unique_hashes = set().union(*(s.unique_doc_hashes for s in natural_scans)) if natural_scans else set()
    unique_doc_ratio = (len(all_unique_hashes) / total_natural_docs) if total_natural_docs > 0 else 1.0
    mean_doc_len = (total_natural_tokens / total_natural_docs) if total_natural_docs > 0 else 0.0
    total_sentence_terminators = sum(s.sentence_terminators for s in natural_scans)
    words_per_sent = (total_natural_tokens / total_sentence_terminators) if total_sentence_terminators > 0 else 0.0

    # Top-20 words analysis
    sorted_words = sorted(gt_tf.items(), key=lambda item: item[1], reverse=True)
    top_20 = [w for w, _ in sorted_words[:20]]
    top20_func_count = sum(1 for w in top_20 if w in _CORE_POLISH_FUNCTION_WORDS)
    content_word_spikes = [
        (w, tf, tf / report.gt.tf_total)
        for w, tf in sorted_words
        if len(w) >= 6 and report.gt.tf_total > 0 and (tf / report.gt.tf_total) > 0.002
    ]
    max_content_spike = content_word_spikes[0] if content_word_spikes else None

    # Lemma clustering diversity
    non_identity_count = sum(1 for w, lem in gt_word_to_lemma.items() if w != lem)
    lemma_cluster_ratio = (non_identity_count / len(gt_word_to_lemma)) if gt_word_to_lemma else 0.0

    # Canary lemma probes
    canary_violations: list[str] = []
    canary_tested: int = 0
    for probe_word, allowed_lemmas in CANARY_LEMMA_PROBES.items():
        if probe_word in gt_word_to_lemma:
            canary_tested += 1
            actual = gt_word_to_lemma[probe_word]
            if actual not in allowed_lemmas:
                canary_violations.append(
                    f"{probe_word} -> {actual!r} (expected one of {sorted(allowed_lemmas)})"
                )

    report.telemetry = {
        "natural_docs": total_natural_docs,
        "unique_docs": len(all_unique_hashes),
        "unique_doc_ratio": unique_doc_ratio,
        "mean_doc_len": mean_doc_len,
        "words_per_sentence": words_per_sent,
        "top20_function_words": top20_func_count,
        "max_content_spike": max_content_spike,
        "non_identity_lemma_ratio": lemma_cluster_ratio,
        "canary_tested": canary_tested,
        "canary_violations": canary_violations,
    }

    # Cross-check X5: Document uniqueness & length integrity
    if total_natural_docs >= 50:
        report.cross_checks["unique_natural_docs"] = (
            unique_doc_ratio >= 0.995 and mean_doc_len >= 400.0
        )
    else:
        report.cross_checks["unique_natural_docs"] = unique_doc_ratio >= 0.995

    # Cross-check X6: Zipfian top-words sanity
    if len(gt_tf) >= 20:
        report.cross_checks["zipf_top_words_sanity"] = (
            top20_func_count >= 14 and not bool(content_word_spikes)
        )
    else:
        report.cross_checks["zipf_top_words_sanity"] = True

    # Cross-check X7: Lemma clustering diversity
    if len(gt_word_to_lemma) >= 50:
        report.cross_checks["lemma_clustering_diversity"] = lemma_cluster_ratio >= 0.55
    else:
        report.cross_checks["lemma_clustering_diversity"] = True

    # Cross-check X8: Morphological Canary Probes
    report.cross_checks["canary_lemma_probes"] = len(canary_violations) == 0

    return report


def print_report(report: GateReport) -> None:
    """Print per-genre fragment counts, measured rates, and cross-checks."""
    for genre in sorted(report.genres):
        scan = report.genres[genre]
        tok_viol = sum(1 for v in scan.violations if v.startswith("invalid-token"))
        rate = (tok_viol / scan.tokens) if scan.tokens else 0.0
        print(
            f"[Verify] genre {genre}: docs={scan.docs} tokens={scan.tokens} "
            f"fragments={len(scan.violations)} token_rate={rate:.6f}"
        )
        for violation in scan.violations[:10]:
            print(f"[Verify]   violation: {violation}")
    print(
        f"[Verify] ground_truth: words={report.gt.words} "
        f"invalid={len(report.gt.invalid_words)} tf_total={report.gt.tf_total}"
    )
    for word in report.gt.invalid_words[:10]:
        print(f"[Verify]   invalid GT word: {word!r}")
    global_entry = (
        report.writer_rates.get("global", {}) if isinstance(report.writer_rates, dict) else {}
    )
    if isinstance(global_entry, dict) and global_entry:
        print(
            f"[Verify] writer audit_rates global: foreign={global_entry.get('foreign_fragment_rate')} "
            f"digit={global_entry.get('digit_token_rate')} "
            f"dropped={global_entry.get('dropped_total')} kept={global_entry.get('tokens_kept')}"
        )

    t = report.telemetry
    if t:
        print(
            f"[Verify] telemetry: natural_docs={t['natural_docs']} "
            f"unique_docs={t['unique_docs']} (ratio={t['unique_doc_ratio']:.4f}) "
            f"mean_doc_len={t['mean_doc_len']:.1f} words_per_sent={t['words_per_sentence']:.1f}"
        )
        spike_str = (
            f"{t['max_content_spike'][0]!r} (share={t['max_content_spike'][2]:.4f})"
            if t["max_content_spike"]
            else "none"
        )
        print(
            f"[Verify] telemetry: top20_function_words={t['top20_function_words']}/20 "
            f"max_content_word_spike={spike_str}"
        )
        print(
            f"[Verify] telemetry: non_identity_lemma_ratio={t['non_identity_lemma_ratio']:.4f}"
        )
        print(
            f"[Verify] telemetry: canary_probes_tested={t['canary_tested']} "
            f"violations={len(t['canary_violations'])}"
        )
        for viol in t["canary_violations"][:10]:
            print(f"[Verify]   canary violation: {viol}")

    for name, ok in report.cross_checks.items():
        print(f"[Verify] cross-check {name}: {'OK' if ok else 'MISMATCH'}")
    for error in report.errors:
        print(f"[Verify] error: {error}")
    print(f"[Verify] gate: {'PASS' if report.passed else 'FAIL'}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry: run the gate against ``--dist-dir`` (default dist/sm)."""
    parser = argparse.ArgumentParser(description="Zero-foreign-fragment gate for built tiers.")
    parser.add_argument(
        "--dist-dir",
        default="dist/sm",
        help="Build output dir holding corpus.zip + parquet + summary",
    )
    args = parser.parse_args(argv)
    report = check_dist_dir(Path(args.dist_dir))
    print_report(report)
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
