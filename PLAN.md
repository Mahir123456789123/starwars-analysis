# PLAN — FiveThirtyEight Star Wars survey

Raw file: `data/raw/StarWars.csv` (downloaded from the FiveThirtyEight GitHub repo, 531,696 bytes). It is read-only: no script ever writes to `data/raw/`.

## 1. What the raw file looks like

- 1,188 physical lines: 1 header line, 1 sub-header line, and 1,186 respondents. The file has no trailing newline. Read naively, pandas gives shape (1187, 38).
- 38 columns. Only 10 header cells are distinct question texts. The other 28 come out as `Unnamed: N` because each multi-part question puts its text above the first sub-column only.
- RespondentID is a 10-digit integer from 3288372923 to 3292879998. Every row has one, none repeat, and the file is sorted by ID in descending order.

## 2. Every data problem found, and the fix for each

| # | Problem | Evidence | Fix in `src/clean.py` |
|---|---------|----------|------------------------|
| 1 | **The file is not UTF-8.** | `utf-8` decoding fails at byte 641 (`0x8c`). Only 2 bytes in the whole file are above 127. | Read with `encoding="cp1252"`. |
| 2 | **Garbage characters in a column name.** | Header 31 is `Do you consider yourself to be a fan of the Expanded Universe?` followed by bytes `0x8c 0xe6` (cp1252 `Œæ`), which is mojibake. | Every column is renamed explicitly by position (see §3), so the garbage is dropped. I also check that the header text matches what we expect, so a different file fails loudly. |
| 3 | **A second header row sits inside the data.** | Row 0 holds `Response` or a film or character name in every column, and RespondentID is NaN. | Use the sub-header only to check column order (each film and character label must match its position), then drop it. |
| 4 | **28 `Unnamed: N` columns.** | Columns 4–8, 10–14 and 16–28. | Give them meaningful names by position (§3). |
| 5 | **Multi-select "which films have you seen" is spread across 6 columns.** The value is the film title or NaN. | For example, col 3 holds `Star Wars: Episode I  The Phantom Menace` 673 times and NaN 513 times. | `seen_epN = column.notna()`, stored as a boolean. I first check that each column holds only one distinct non-null value and that it is the expected title. |
| 6 | **Film titles have a double space** where a dash was stripped (`Episode I  The Phantom Menace`). | Found in the sub-header for Episodes I–IV. | Not carried into the data. Titles are only used for the column-order check, after whitespace is collapsed. |
| 7 | **Rankings are stored as text** (`'1'`…`'6'`). | Read with `dtype=str`. | `pd.to_numeric(..., errors="raise")` into nullable `Int64`, then check the values are in {1..6}. |
| 8 | **2 respondents have incomplete rankings** (5 of 6 films ranked). | IDs 3290687830 (Ep III blank; ranks 1,2,4,5,3) and 3289450247 (Ep I blank; ranks 3,2,5,1,4). The other 834 rankers give a full permutation of 1–6, and 350 rank nothing. | Keep their 5 ranks as given and leave the missing one as NA. Add `rank_complete` (bool). Mean ranks use every non-missing rank, so these 2 add one fewer data point. Analyses can filter on `rank_complete` if needed. |
| 9 | **People ranked films they had not seen.** | 1,118 rank cells belong to films the respondent did not tick as seen. The survey appears to have forced a full ranking. | Not "fixed", because it is a real feature of the data. It goes in the report's limitations. Subagent A also reports a sensitivity check on respondents who saw all 6 films (471 people). |
| 10 | **Yes/No answers are stored as strings.** | Columns 1, 2, 30, 31, 32 hold only `Yes`, `No` or NaN. | Map to nullable `boolean` (True/False/NA). Any other value raises an error. |
| 11 | **Missing data comes from survey skip logic.** | 250 people said "No" to seeing any film, and every later Star Wars question is blank for them. 140 skipped all demographics. Income is missing for 328. | Keep NA. Don't impute. Keep all 1,186 respondents. Each analysis filters to the respondents who answered the relevant question, and the N is always reported. |
| 12 | **Inconsistent screener answers.** | 101 people answered "Yes, I've seen a Star Wars film" but ticked no films. Of these, 100 answered nothing else (no fan answer, ranks, characters or shot-first). 1 (fan = No) ranked all 6 and answered shot-first. | Keep the raw answer in `seen_any`. Add a derived `seen_count` (0–6). No rows are dropped. Analyses use the per-question answers directly, so these empty rows drop out naturally. |
| 13 | **`I don't understand this question`** is a real answer to "Which character shot first?" | 306 responses, alongside Han (325) and Greedo (197). | Recode to `han`, `greedo` and `dont_understand`. It is kept as its own category, not treated as missing. |
| 14 | **Long text categories** for character favourability. | Values such as `Neither favorably nor unfavorably (neutral)` and `Unfamiliar (N/A)`. | Recode to `very_favorable`, `somewhat_favorable`, `neutral`, `somewhat_unfavorable`, `very_unfavorable` and `unfamiliar`. Not needed for Q1–Q3 but cleaned for completeness. |
| 15 | **Ordinal demographics stored as free text.** | Age is `18-29`, `30-44`, `45-60` or `> 60`. Income is `$0 - $24,999` … `$150,000+`. | Keep the labels, normalise them (age to `18-29` … `60+`, income to `0-24999` … `150000+`), and document the order in the clean script as a constant. |
| 16 | **Looks like duplicates, but isn't.** | 0 duplicate IDs and 0 fully duplicated rows. 142 rows are identical once the ID is removed, but these are respondents who left almost everything blank (for example "No" to seen-any plus the same demographics). | No rows are de-duplicated, because they are different respondents. Uniqueness of `respondent_id` is checked with an assertion. |
| 17 | **The skip-logic structure should hold.** | Fan, ranks and shot-first are never answered by someone with `seen_any = No`. EU-fan is never answered unless EU-familiar is Yes. | Checked with assertions in clean.py, so a violation fails the run. |
| 18 | **No trailing newline; surrounding whitespace.** | The last line has no `\n`. No cell or header has leading or trailing whitespace. | Pandas already handles these, so no action is needed. |

**Row accounting:** 1,187 parsed rows go in. The sub-header row is dropped, so 1,186 respondent rows come out, with 38 raw columns becoming 40 clean columns.

## 3. Final clean columns (`data/clean/starwars_clean.csv`)

| Column | Type | From raw col |
|--------|------|--------------|
| `respondent_id` | int64 | 0 |
| `seen_any` | boolean | 1 |
| `fan` | boolean | 2 |
| `seen_ep1` … `seen_ep6` | bool | 3–8 |
| `seen_count` | int (0–6), derived | 3–8 |
| `rank_ep1` … `rank_ep6` | Int64 (1–6, NA) | 9–14 |
| `rank_complete` | bool, derived | 9–14 |
| `fav_han`, `fav_luke`, `fav_leia`, `fav_anakin`, `fav_obiwan`, `fav_palpatine`, `fav_vader`, `fav_lando`, `fav_boba`, `fav_c3po`, `fav_r2d2`, `fav_jarjar`, `fav_padme`, `fav_yoda` | category (6 levels, NA) | 15–28 |
| `shot_first` | `han` / `greedo` / `dont_understand` / NA | 29 |
| `eu_familiar` | boolean | 30 |
| `eu_fan` | boolean | 31 |
| `star_trek_fan` | boolean | 32 |
| `gender` | `male` / `female` / NA | 33 |
| `age` | `18-29` / `30-44` / `45-60` / `60+` / NA | 34 |
| `income` | `0-24999` / `25000-49999` / `50000-99999` / `100000-149999` / `150000+` / NA | 35 |
| `education` | `less_than_high_school` / `high_school` / `some_college` / `bachelor` / `graduate` / NA | 36 |
| `region` | snake_case census region (e.g. `east_north_central`) / NA | 37 |

Total: 1 + 2 + 6 + 1 + 6 + 1 + 14 + 1 + 3 + 5 = **40** columns.

## 4. Phase 1 (main agent)
- Add `requirements.txt` (pandas, matplotlib, pytest), plus `src/`, `tests/`, `outputs/` and `data/clean/`.
- Write `src/clean.py` as described above. It prints a cleaning summary: rows in and out, columns renamed, rows dropped and why, counts recoded, and the validation checks it passed.
- Commit with the message: `Phase 1: cleaning pipeline`.

## 5. Phase 2: three parallel subagents, with no shared files

| Agent | Question | May create ONLY |
|-------|----------|-----------------|
| **A** | Q1: most-liked film (mean rank, % ranked #1, number who have seen each film), plus a sensitivity check restricted to people who saw all 6. Q2: fans vs non-fans (mean rank per film by group, N per group). | `src/analysis_films.py`, `outputs/chart_film_ranking.png`, `outputs/chart_fans_vs_nonfans.png`, `outputs/films_results.json` |
| **B** | Q3: shot-first distribution overall and by gender (counts, %, N), plus a chi-square test computed by hand with numpy/pandas (no scipy dependency). | `src/analysis_shot_first.py`, `outputs/chart_shot_first_by_gender.png`, `outputs/shot_first_results.json` |
| **C** | Independent verifier. It must **not** read `src/clean.py`. It recomputes key numbers from the RAW CSV and compares them with the clean CSV: row count, Yes/No counts, seen-per-film counts, mean rank per film, unique respondent IDs, and ranks only in 1–6. | `tests/test_data.py` |

All three read `data/clean/starwars_clean.csv` (C also reads the raw file) and nothing else. Every script reads its input relative to the repo root, so the commands are the same however it is run.

## 6. Phase 3 (main agent)
- Run the analysis scripts, then `pytest -v`. Fix the root cause of any failure and report it.
- Write `REPORT.md`, filling every number in from the JSON outputs, and `README.md`.
- Commit after each phase.
