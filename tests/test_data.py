"""Independent verification of data/clean/starwars_clean.csv against the raw survey.

Everything here is recomputed directly from data/raw/StarWars.csv with a
self-contained parser (csv module, cp1252 decoding). Nothing from src/ is used.
"""
import csv
import hashlib
import io
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "StarWars.csv"
CLEAN_PATH = ROOT / "data" / "clean" / "starwars_clean.csv"

# SHA-256 of data/raw/StarWars.csv as downloaded (FiveThirtyEight, cp1252-encoded).
RAW_SHA256 = "8b4ae2a4ce59d124ac98ce5810a22bca5710e1dcd644fb7cb26344811ba3f989"

FILMS = [1, 2, 3, 4, 5, 6]

# Raw column positions, derived from the header + sub-header rows (38 columns).
COL_ID = 0
YESNO_COLS = {  # clean column -> raw column index
    "seen_any": 1,
    "fan": 2,
    "eu_familiar": 30,
    "eu_fan": 31,
    "star_trek_fan": 32,
}
SEEN_COLS = {ep: 2 + ep for ep in FILMS}  # cols 3..8
RANK_COLS = {ep: 8 + ep for ep in FILMS}  # cols 9..14
COL_SHOT = 29
COL_GENDER = 33

ROMAN = ["I", "II", "III", "IV", "V", "VI"]


# --------------------------------------------------------------------------- #
# Raw parsing helpers (self-contained)
# --------------------------------------------------------------------------- #
def _read_raw_rows():
    text = RAW_PATH.read_bytes().decode("cp1252")
    return list(csv.reader(io.StringIO(text, newline="")))


def _map_yesno(v):
    v = v.strip()
    return {"Yes": "True", "No": "False", "": ""}[v]


def _map_shot(v):
    v = v.strip()
    if v == "":
        return ""
    if v == "Han":
        return "han"
    if v == "Greedo":
        return "greedo"
    if v.startswith("I don"):
        return "dont_understand"
    raise ValueError(f"unexpected shot-first answer {v!r}")


def _map_gender(v):
    return {"Male": "male", "Female": "female", "": ""}[v.strip()]


def _parse_rank(v):
    v = v.strip()
    if v == "":
        return None
    f = float(v)
    assert f == int(f), f"non-integer raw rank {v!r}"
    return int(f)


@pytest.fixture(scope="module")
def raw_all_rows():
    return _read_raw_rows()


@pytest.fixture(scope="module")
def raw_rows(raw_all_rows):
    """Raw respondent rows: data after the header, embedded sub-header removed."""
    header, subheader = raw_all_rows[0], raw_all_rows[1]
    # Sanity-check our hard-coded positions against the header/sub-header.
    assert header[COL_ID] == "RespondentID"
    assert subheader[COL_ID] == "" and subheader[1] == "Response"
    assert header[COL_SHOT] == "Which character shot first?"
    assert header[COL_GENDER] == "Gender"
    assert header[30].startswith("Are you familiar with the Expanded Universe")
    assert header[31].startswith("Do you consider yourself to be a fan of the Expanded Universe")
    assert header[32].startswith("Do you consider yourself to be a fan of the Star Trek")
    assert header[3].startswith("Which of the following Star Wars films have you seen")
    assert header[9].startswith("Please rank the Star Wars films")
    for ep in FILMS:
        assert f"Episode {ROMAN[ep - 1]} " in subheader[SEEN_COLS[ep]]
        assert f"Episode {ROMAN[ep - 1]} " in subheader[RANK_COLS[ep]]
    rows = [r for r in raw_all_rows[2:]]
    assert all(len(r) == len(header) for r in rows)
    return rows


@pytest.fixture(scope="module")
def raw_df(raw_rows):
    """Raw rows converted to the clean contract's vocabulary, indexed by respondent_id."""
    recs = []
    for r in raw_rows:
        rec = {"respondent_id": r[COL_ID].strip()}
        for col, idx in YESNO_COLS.items():
            rec[col] = _map_yesno(r[idx])
        for ep in FILMS:
            rec[f"seen_ep{ep}"] = "True" if r[SEEN_COLS[ep]].strip() else "False"
            rec[f"rank_ep{ep}"] = _parse_rank(r[RANK_COLS[ep]])
        rec["shot_first"] = _map_shot(r[COL_SHOT])
        rec["gender"] = _map_gender(r[COL_GENDER])
        recs.append(rec)
    return pd.DataFrame(recs)


@pytest.fixture(scope="module")
def clean_df():
    return pd.read_csv(CLEAN_PATH, dtype=str, keep_default_na=False)


def _clean_rank(series):
    return series.map(lambda v: None if v.strip() == "" else float(v))


# --------------------------------------------------------------------------- #
# 9. Raw file integrity
# --------------------------------------------------------------------------- #
def test_raw_file_sha256_unchanged():
    """The raw CSV must be byte-identical to the file as downloaded."""
    assert hashlib.sha256(RAW_PATH.read_bytes()).hexdigest() == RAW_SHA256


def test_raw_file_is_not_utf8():
    """The raw file is cp1252, not UTF-8; if it decodes as UTF-8 someone re-saved it."""
    with pytest.raises(UnicodeDecodeError):
        RAW_PATH.read_bytes().decode("utf-8")


# --------------------------------------------------------------------------- #
# 1-2. Rows and respondent identity
# --------------------------------------------------------------------------- #
def test_row_count_matches_raw(raw_all_rows, raw_rows, clean_df):
    """Clean has one row per raw respondent (header + embedded sub-header excluded)."""
    assert len(raw_rows) == len(raw_all_rows) - 2
    n_nonblank_ids = sum(1 for r in raw_rows if r[COL_ID].strip())
    assert len(clean_df) == len(raw_rows) == n_nonblank_ids


def test_no_subheader_row_in_clean(clean_df):
    """The embedded 'Response' sub-header row must not survive into clean."""
    assert not (clean_df == "Response").any().any()
    assert (clean_df["respondent_id"].str.strip() != "").all()


def test_respondent_id_is_integer(clean_df):
    """respondent_id values are plain integers."""
    assert clean_df["respondent_id"].str.fullmatch(r"\d+").all()


def test_respondent_ids_unique_and_equal_raw(raw_df, clean_df):
    """respondent_id is unique in clean and the ID set equals the raw ID set exactly."""
    assert clean_df["respondent_id"].is_unique
    assert raw_df["respondent_id"].is_unique
    clean_ids = set(clean_df["respondent_id"].astype("int64"))
    raw_ids = set(raw_df["respondent_id"].astype("int64"))
    assert clean_ids == raw_ids


# --------------------------------------------------------------------------- #
# 3. Yes/No questions
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("col", list(YESNO_COLS))
def test_yesno_counts(col, raw_rows, clean_df):
    """Raw Yes/No/blank counts equal clean True/False/blank counts."""
    idx = YESNO_COLS[col]
    raw_vals = [r[idx].strip() for r in raw_rows]
    assert set(raw_vals) <= {"Yes", "No", ""}
    assert set(clean_df[col]) <= {"True", "False", ""}
    assert raw_vals.count("Yes") == (clean_df[col] == "True").sum()
    assert raw_vals.count("No") == (clean_df[col] == "False").sum()
    assert raw_vals.count("") == (clean_df[col] == "").sum()


# --------------------------------------------------------------------------- #
# 4. Seen counts
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ep", FILMS)
def test_seen_count_per_film(ep, raw_rows, clean_df):
    """Number of respondents who saw each film matches the non-blank raw cells."""
    raw_n = sum(1 for r in raw_rows if r[SEEN_COLS[ep]].strip())
    col = f"seen_ep{ep}"
    assert set(clean_df[col]) <= {"True", "False"}
    assert (clean_df[col] == "True").sum() == raw_n


def test_seen_count_column(clean_df):
    """seen_count equals the number of seen_ep* flags that are True."""
    expected = sum((clean_df[f"seen_ep{ep}"] == "True").astype(int) for ep in FILMS)
    assert (clean_df["seen_count"].astype(int) == expected).all()


# --------------------------------------------------------------------------- #
# 5-6. Rankings
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("ep", FILMS)
def test_rank_mean_and_n_per_film(ep, raw_rows, clean_df):
    """Mean rank and number of ranks per film match values computed from raw text."""
    raw_ranks = [_parse_rank(r[RANK_COLS[ep]]) for r in raw_rows]
    raw_ranks = [x for x in raw_ranks if x is not None]
    clean_ranks = _clean_rank(clean_df[f"rank_ep{ep}"]).dropna()
    assert len(clean_ranks) == len(raw_ranks)
    assert clean_ranks.mean() == pytest.approx(sum(raw_ranks) / len(raw_ranks), abs=1e-9)


@pytest.mark.parametrize("ep", FILMS)
def test_rank_values_integer_1_to_6(ep, clean_df):
    """Clean ranks are blank or integer-valued in 1..6."""
    vals = clean_df[f"rank_ep{ep}"]
    nonblank = vals[vals.str.strip() != ""]
    assert nonblank.str.fullmatch(r"[1-6]").all(), sorted(set(nonblank))


def test_complete_rankings_are_permutations(clean_df):
    """rank_complete is True iff all 6 ranks are present; complete rows are permutations of 1..6."""
    ranks = pd.DataFrame({ep: _clean_rank(clean_df[f"rank_ep{ep}"]) for ep in FILMS})
    complete = ranks.notna().all(axis=1)
    assert ((clean_df["rank_complete"] == "True") == complete).all()
    assert set(clean_df["rank_complete"]) <= {"True", "False"}
    for _, row in ranks[complete].iterrows():
        assert sorted(int(v) for v in row) == FILMS


# --------------------------------------------------------------------------- #
# 7. Categorical counts
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("category", ["han", "greedo", "dont_understand", ""])
def test_shot_first_counts(category, raw_df, clean_df):
    """Shot-first counts per category (incl. blank) match raw."""
    assert set(clean_df["shot_first"]) <= {"han", "greedo", "dont_understand", ""}
    assert (clean_df["shot_first"] == category).sum() == (raw_df["shot_first"] == category).sum()


@pytest.mark.parametrize("category", ["male", "female", ""])
def test_gender_counts(category, raw_df, clean_df):
    """Gender counts per category (incl. blank) match raw."""
    assert set(clean_df["gender"]) <= {"male", "female", ""}
    assert (clean_df["gender"] == category).sum() == (raw_df["gender"] == category).sum()


# --------------------------------------------------------------------------- #
# 8. Per-respondent alignment
# --------------------------------------------------------------------------- #
ALIGN_COLS = (
    [f"seen_ep{ep}" for ep in FILMS]
    + [f"rank_ep{ep}" for ep in FILMS]
    + ["fan", "seen_any", "eu_familiar", "eu_fan", "star_trek_fan", "shot_first", "gender"]
)


@pytest.mark.parametrize("col", ALIGN_COLS)
def test_per_respondent_alignment(col, raw_df, clean_df):
    """Joined on respondent_id, every respondent's value matches raw (catches column shifts)."""
    raw = raw_df.set_index(raw_df["respondent_id"].astype("int64"))[col]
    clean = clean_df.set_index(clean_df["respondent_id"].astype("int64"))[col]
    if col.startswith("rank_ep"):
        clean = _clean_rank(clean)
        raw = raw.map(lambda v: None if v is None or pd.isna(v) else float(v))
    joined = pd.concat({"raw": raw, "clean": clean}, axis=1, join="outer")
    assert len(joined) == len(raw) == len(clean)
    both_na = joined["raw"].isna() & joined["clean"].isna()
    mismatch = joined[~both_na & (joined["raw"] != joined["clean"])]
    assert mismatch.empty, f"{len(mismatch)} mismatches in {col}:\n{mismatch.head(10)}"
