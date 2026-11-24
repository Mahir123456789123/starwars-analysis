"""Clean the FiveThirtyEight Star Wars survey.

Reads  data/raw/StarWars.csv            (never modified)
Writes data/clean/starwars_clean.csv

Run from anywhere:  python src/clean.py
See PLAN.md for the full list of data problems and fixes.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "StarWars.csv"
CLEAN_PATH = ROOT / "data" / "clean" / "starwars_clean.csv"

RAW_ENCODING = "cp1252"  # file is not valid UTF-8 (bytes 0x8c 0xe6 in one header)
EXPECTED_RAW_COLS = 38

FILMS = [
    "Star Wars: Episode I The Phantom Menace",
    "Star Wars: Episode II Attack of the Clones",
    "Star Wars: Episode III Revenge of the Sith",
    "Star Wars: Episode IV A New Hope",
    "Star Wars: Episode V The Empire Strikes Back",
    "Star Wars: Episode VI Return of the Jedi",
]
CHARACTERS = {  # sub-header label -> short name
    "Han Solo": "han", "Luke Skywalker": "luke", "Princess Leia Organa": "leia",
    "Anakin Skywalker": "anakin", "Obi Wan Kenobi": "obiwan",
    "Emperor Palpatine": "palpatine", "Darth Vader": "vader",
    "Lando Calrissian": "lando", "Boba Fett": "boba", "C-3P0": "c3po",
    "R2 D2": "r2d2", "Jar Jar Binks": "jarjar", "Padme Amidala": "padme",
    "Yoda": "yoda",
}

# Column names by raw position. Explicit so that garbled / "Unnamed" headers never leak through.
COLUMN_MAP: dict[int, str] = {0: "respondent_id", 1: "seen_any", 2: "fan"}
COLUMN_MAP.update({3 + i: f"seen_ep{i + 1}" for i in range(6)})
COLUMN_MAP.update({9 + i: f"rank_ep{i + 1}" for i in range(6)})
COLUMN_MAP.update({15 + i: f"fav_{c}" for i, c in enumerate(CHARACTERS.values())})
COLUMN_MAP.update({29: "shot_first", 30: "eu_familiar", 31: "eu_fan",
                   32: "star_trek_fan", 33: "gender", 34: "age", 35: "income",
                   36: "education", 37: "region"})

# Expected start of the (non-Unnamed) raw header at each position: guards against a different file.
EXPECTED_HEADER_PREFIX = {
    0: "RespondentID", 1: "Have you seen any of the 6 films", 2: "Do you consider yourself to be a fan of the Star Wars",
    3: "Which of the following Star Wars films have you seen", 9: "Please rank the Star Wars films",
    15: "Please state whether you view the following characters", 29: "Which character shot first",
    30: "Are you familiar with the Expanded Universe", 31: "Do you consider yourself to be a fan of the Expanded Universe",
    32: "Do you consider yourself to be a fan of the Star Trek", 33: "Gender", 34: "Age",
    35: "Household Income", 36: "Education", 37: "Location (Census Region)",
}

YES_NO = {"Yes": True, "No": False}
FAVOURABILITY = {
    "Very favorably": "very_favorable",
    "Somewhat favorably": "somewhat_favorable",
    "Neither favorably nor unfavorably (neutral)": "neutral",
    "Somewhat unfavorably": "somewhat_unfavorable",
    "Very unfavorably": "very_unfavorable",
    "Unfamiliar (N/A)": "unfamiliar",
}
SHOT_FIRST = {"Han": "han", "Greedo": "greedo", "I don't understand this question": "dont_understand"}
GENDER = {"Male": "male", "Female": "female"}
AGE = {"18-29": "18-29", "30-44": "30-44", "45-60": "45-60", "> 60": "60+"}
INCOME = {
    "$0 - $24,999": "0-24999", "$25,000 - $49,999": "25000-49999",
    "$50,000 - $99,999": "50000-99999", "$100,000 - $149,999": "100000-149999",
    "$150,000+": "150000+",
}
EDUCATION = {
    "Less than high school degree": "less_than_high_school", "High school degree": "high_school",
    "Some college or Associate degree": "some_college", "Bachelor degree": "bachelor",
    "Graduate degree": "graduate",
}
# Ordered levels for ordinal columns (for analysis scripts that want them).
ORDER = {
    "age": list(AGE.values()), "income": list(INCOME.values()),
    "education": list(EDUCATION.values()), "favourability": list(FAVOURABILITY.values()),
}


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def recode(series: pd.Series, mapping: dict, name: str, dtype: str = "string") -> pd.Series:
    """Map raw strings to clean values; any unexpected non-null value is an error."""
    unexpected = set(series.dropna().unique()) - set(mapping)
    if unexpected:
        raise ValueError(f"{name}: unexpected values {sorted(unexpected)}")
    return series.map(mapping).astype(dtype)


def load_raw(path: Path = RAW_PATH) -> tuple[pd.DataFrame, pd.Series]:
    """Return (respondent rows as strings, sub-header row)."""
    raw = pd.read_csv(path, encoding=RAW_ENCODING, dtype=str, keep_default_na=False, na_values=[""])
    if raw.shape[1] != EXPECTED_RAW_COLS:
        raise ValueError(f"expected {EXPECTED_RAW_COLS} columns, got {raw.shape[1]}")
    for pos, prefix in EXPECTED_HEADER_PREFIX.items():
        if not raw.columns[pos].startswith(prefix):
            raise ValueError(f"column {pos}: header {raw.columns[pos]!r} does not start with {prefix!r}")
    subheader = raw.iloc[0]
    if pd.notna(subheader.iloc[0]):
        raise ValueError("expected the second line to be a sub-header with blank RespondentID")
    return raw.iloc[1:].reset_index(drop=True), subheader


def check_subheader(subheader: pd.Series) -> None:
    """The sub-header tells us which film/character each 'Unnamed' column holds; verify our mapping."""
    for i, film in enumerate(FILMS):
        for start in (3, 9):
            got = _norm_ws(subheader.iloc[start + i])
            if got != film:
                raise ValueError(f"column {start + i}: sub-header {got!r} != {film!r}")
    for i, label in enumerate(CHARACTERS):
        got = _norm_ws(subheader.iloc[15 + i])
        if got != label:
            raise ValueError(f"column {15 + i}: sub-header {got!r} != {label!r}")


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    notes: list[str] = []
    df = raw.copy()
    df.columns = [COLUMN_MAP[i] for i in range(df.shape[1])]
    notes.append(f"renamed {df.shape[1]} columns by position "
                 f"({sum(c.startswith('Unnamed') for c in raw.columns)} were 'Unnamed', 1 had garbage bytes)")

    out = pd.DataFrame(index=df.index)
    out["respondent_id"] = df["respondent_id"].astype("int64")

    for col in ["seen_any", "fan"]:
        out[col] = recode(df[col], YES_NO, col, "boolean")

    for i, film in enumerate(FILMS, start=1):
        col = df[f"seen_ep{i}"]
        values = {_norm_ws(v) for v in col.dropna().unique()}
        if values - {film}:
            raise ValueError(f"seen_ep{i}: unexpected values {values}")
        out[f"seen_ep{i}"] = col.notna()
    seen_cols = [f"seen_ep{i}" for i in range(1, 7)]
    out["seen_count"] = out[seen_cols].sum(axis=1).astype("int64")
    notes.append("multi-select 'films seen' (title text or blank) -> 6 boolean seen_epN columns + seen_count")

    rank_cols = [f"rank_ep{i}" for i in range(1, 7)]
    for col in rank_cols:
        out[col] = pd.to_numeric(df[col], errors="raise").astype("Int64")
    notes.append("rank text '1'..'6' -> nullable integers")
    n_ranked = out[rank_cols].notna().sum(axis=1)
    out["rank_complete"] = n_ranked == 6

    for raw_label, short in CHARACTERS.items():
        out[f"fav_{short}"] = recode(df[f"fav_{short}"], FAVOURABILITY, f"fav_{short}")
    notes.append("14 character favourability columns -> short labels "
                 f"({', '.join(FAVOURABILITY.values())})")

    out["shot_first"] = recode(df["shot_first"], SHOT_FIRST, "shot_first")
    for col in ["eu_familiar", "eu_fan", "star_trek_fan"]:
        out[col] = recode(df[col], YES_NO, col, "boolean")
    out["gender"] = recode(df["gender"], GENDER, "gender")
    out["age"] = recode(df["age"], AGE, "age")
    out["income"] = recode(df["income"], INCOME, "income")
    out["education"] = recode(df["education"], EDUCATION, "education")
    regions = df["region"].dropna().unique()
    out["region"] = recode(df["region"], {r: re.sub(r"\W+", "_", r.lower()).strip("_") for r in regions},
                           "region")
    notes.append("Yes/No strings -> booleans (seen_any, fan, eu_familiar, eu_fan, star_trek_fan); "
                 "shot_first, gender, age, income, education, region -> short snake_case labels")
    return out, notes


def validate(df: pd.DataFrame) -> list[str]:
    """Structural checks; raise on any failure, return descriptions of checks passed."""
    rank_cols = [f"rank_ep{i}" for i in range(1, 7)]
    seen_cols = [f"seen_ep{i}" for i in range(1, 7)]
    checks = []

    def check(cond: bool, msg: str) -> None:
        if not bool(cond):
            raise AssertionError(f"validation failed: {msg}")
        checks.append(msg)

    check(df["respondent_id"].is_unique, "respondent_id is unique")
    ranks = df[rank_cols]
    check(ranks.stack().between(1, 6).all(), "all ranks are within 1..6")
    full = ranks[df["rank_complete"]]
    check((full.apply(lambda r: sorted(r.tolist()), axis=1) == pd.Series([[1, 2, 3, 4, 5, 6]] * len(full),
                                                                       index=full.index)).all(),
          "every complete ranking is a permutation of 1..6")
    partial = ranks[~df["rank_complete"]]
    partial = partial[partial.notna().any(axis=1)]
    check(all(len(set(r.dropna())) == r.notna().sum() for _, r in partial.iterrows()),
          "partial rankings contain no repeated rank")
    not_seen = df["seen_any"] == False  # noqa: E712  (nullable boolean)
    for col in ["fan", "shot_first", *rank_cols]:
        check(df.loc[not_seen, col].isna().all(), f"{col} is blank for everyone with seen_any = No")
    check(not df.loc[not_seen, seen_cols].any(axis=None), "no films ticked by anyone with seen_any = No")
    check(df.loc[df["eu_familiar"] != True, "eu_fan"].isna().all(),  # noqa: E712
          "eu_fan only answered when eu_familiar = Yes")
    return checks


def main() -> pd.DataFrame:
    raw, subheader = load_raw()
    check_subheader(subheader)
    rows_in = len(raw) + 1  # + the sub-header row
    df, notes = clean(raw)
    checks = validate(df)

    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CLEAN_PATH, index=False, encoding="utf-8", lineterminator="\n")

    rank_cols = [f"rank_ep{i}" for i in range(1, 7)]
    n_ranked = df[rank_cols].notna().sum(axis=1)
    inconsistent = ((df["seen_any"] == True) & (df["seen_count"] == 0)).sum()  # noqa: E712
    ranked_unseen = sum((df[f"rank_ep{i}"].notna() & ~df[f"seen_ep{i}"]).sum() for i in range(1, 7))

    print("=== Cleaning summary ===")
    print(f"raw file      : {RAW_PATH.relative_to(ROOT)} (encoding {RAW_ENCODING})")
    print(f"rows in       : {rows_in} parsed rows (1 embedded sub-header + {len(raw)} respondents)")
    print(f"rows dropped  : 1 (the embedded sub-header row); 0 respondents dropped")
    print(f"rows out      : {len(df)}")
    print(f"columns       : {raw.shape[1]} raw -> {df.shape[1]} clean")
    print("changes:")
    for n in notes:
        print(f"  - {n}")
    print("data notes (kept, not fixed):")
    print(f"  - respondents with a full ranking (6 films): {(n_ranked == 6).sum()}")
    print(f"  - respondents with a partial ranking: {n_ranked.between(1, 5).sum()} "
          f"(ids {df.loc[n_ranked.between(1, 5), 'respondent_id'].tolist()})")
    print(f"  - respondents with no ranking: {(n_ranked == 0).sum()}")
    print(f"  - rank values given to films the respondent did not tick as seen: {ranked_unseen}")
    print(f"  - said they had seen a film (seen_any=Yes) but ticked none: {inconsistent}")
    print("missing values per key column:")
    for col in ["fan", "rank_ep1", "shot_first", "gender", "age", "income", "education", "region"]:
        print(f"  - {col:<11}: {df[col].isna().sum()}")
    print("validation checks passed:")
    for c in checks:
        print(f"  - {c}")
    print(f"wrote {CLEAN_PATH.relative_to(ROOT)}")
    return df


if __name__ == "__main__":
    main()
