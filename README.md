# Polish Corpus Builder (`stemgen-polish-corpus`)

A reproducible, standalone data pipeline for compiling balanced, multi-genre generic Polish language corpora and gold-standard morphological ground-truth datasets for Information Retrieval (IR), BM25/BM25F benchmarking, and stemmer training (such as [Snowball](https://snowballstem.org/)).

---

## Key Features

1. **Multi-Genre Balanced Sampling**:
   - **`01_nkjp_spoken_forum` (25% token mass)**: Spoken dialogues, Sejm parliamentary transcripts, and forum discussions from NKJP1M. Essential for 1st- and 2nd-person verb conjugations (`-em`, `-eś`, `-śmy`, `-ście`).
   - **`02_nkjp_literature` (20% token mass)**: Classic narrative fiction and prose from Wolne Lektury (*Lalka*, *Faraon*, *Krzyżacy*, *Quo Vadis*, *Chłopi*, *Pan Tadeusz*).
   - **`03_nkjp_news` (15% token mass)**: Modern Polish journalism and press articles.
   - **`04_wikipedia` (40% token mass)**: Clean encyclopedic articles from Polish Wikipedia (WikiNeural).

2. **Gold-Standard Morphological Ground Truth**:
   - Ingests over 4.2 million inflected Polish word forms mapped to base lemmas from **Morfeusz 2 / PoliMorf** (Institute of Computer Science, Polish Academy of Sciences) and **SJP**.
   - **Proper Noun Filtering**: Discards capitalized proper nouns, geographic names, and surnames *before* lowercasing (`lemma[0].isupper()`).
   - **Homonym Qualifier Stripping**: Normalizes qualifiers (`zamek:s1` $\to$ `zamek`, `piec:v` $\to$ `piec`).
   - **Frequency Dominance Disambiguation**: Enforces strict $1\text{ word} \to 1\text{ dominant lemma}$ partitioning based on empirical corpus frequency.

3. **Inflectional Paradigm Completion (`99_morfeusz_paradigms`)**:
   - Guarantees that all standard declensional and conjugational inflections for top lemmas exist in the corpus archive with a floor of $\text{TF} \ge 1, \text{DF} \ge 1$.

4. **Zero-Shot Evaluation Splits**:
   - Generates an **80/20 Lemma-Stratified Holdout Split** (holding out all surface forms of test lemmas together) to test zero-shot generalization on unseen vocabulary.
   - Automatically cross-references and annotates official `snowball-data/polish/voc.txt` for regression testing.

---

## Corpus Tiers

| Tier | Target Docs | Target Tokens | Unique Vocabulary ($|V|$) | Paradigms Completed | ZIP Size |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`sm`** | 4,400 | ~2.4M | ~264,000 | Top 5,000 | ~10 MB |
| **`md`** | 10,100 | ~5.5M | ~421,000 | Top 10,000 | ~23 MB |
| **`lg`** | 25,000 | ~13.4M | ~523,000 | Top 15,000 | ~56 MB |

---

## Installation & Requirements

Requires **Python >= 3.10**.

```bash
git clone https://github.com/michals/stemgen-polish-corpus.git
cd stemgen-polish-corpus

# Using uv (recommended):
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Or using standard python venv + pip:
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

---

## Usage

After installation, run with the `stemgen-polish-corpus` command or via `python -m polish_corpus`:

### 1. Quick Verification Run
```bash
stemgen-polish-corpus --quick-test
# or: python -m polish_corpus --quick-test
```

### 2. Build MD Corpus (~5.5M tokens, 421k vocabulary)
Generates into `./dist/md/` by default:
```bash
stemgen-polish-corpus --tier md
# or simply: stemgen-polish-corpus
```

### 3. Build SM Tier (Fast / CI Profile)
Generates into `./dist/sm/` by default:
```bash
stemgen-polish-corpus --tier sm
```

### 4. Build LG Tier (Exhaustive Profile)
Generates into `./dist/lg/` by default:
```bash
stemgen-polish-corpus --tier lg
```

---

## Output Structure

Each tier directory (e.g. `dist/md/`, `dist/sm/`, `dist/lg/`) contains:
```text
dist/md/
├── corpus.zip                       # Hierarchical ZIP of ~500-word .txt docs
├── ground_truth.parquet             # Full ground truth (word, lemma, tf, df)
├── ground_truth_train.parquet       # 80% lemma-stratified training partition
├── ground_truth_test.parquet        # 20% held-out test partition (zero-shot test)
├── snowball_voc_ground_truth.parquet# Official Snowball voc.txt annotated with gold lemmas
├── build_summary.json               # Detailed statistics, tokens, and elapsed time
└── README.md                        # Tier-specific metadata
```

---

## Data Sources & Licensing

All sources used by this builder are open and legally permissive:
* **Morfeusz 2 / PoliMorf**: 2-Clause BSD License (IPI PAN, Institute of Computer Science PAS).
* **SJP (Słownik Języka Polskiego)**: Apache 2.0 / CC-BY-4.0 / GPL.
* **NKJP1M (National Corpus of Polish 1-Million Subcorpus)**: Creative Commons Attribution 4.0 International (CC-BY-4.0).
* **Wolne Lektury**: Public Domain / CC-BY-SA.
* **WikiNeural (Polish Wikipedia slice)**: CC-BY-SA 4.0.
* **Snowball Polish Vocabulary**: 3-Clause BSD License.

The code in this repository is licensed under the **BSD 3-Clause License**.
