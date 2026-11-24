# Star Wars survey analysis

This project cleans and analyses the [FiveThirtyEight Star Wars survey](https://github.com/fivethirtyeight/data/tree/master/star-wars-survey) so the results can be reproduced end to end. The findings are in **[REPORT.md](REPORT.md)** and the data problems with their fixes are in **[PLAN.md](PLAN.md)**.

## Reproduce from scratch

You need Python 3.10 or later. The project was tested with Python 3.12, pandas 2.1, matplotlib 3.10 and pytest 9.

```bash
git clone <this repo> starwars-analysis
cd starwars-analysis

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Optional: re-download the raw data. A copy is already committed under data/raw/.
# The SHA-256 test in tests/test_data.py checks that the file is byte-identical.
curl -L -o data/raw/StarWars.csv https://raw.githubusercontent.com/fivethirtyeight/data/master/star-wars-survey/StarWars.csv

python src/clean.py                # -> data/clean/starwars_clean.csv, and prints a cleaning summary
python src/analysis_films.py       # Q1 and Q2 -> outputs/chart_film_ranking.png, chart_fans_vs_nonfans.png, films_results.json
python src/analysis_shot_first.py  # Q3 -> outputs/chart_shot_first_by_gender.png, shot_first_results.json
python -m pytest -v                # 57 tests that check the clean data against the raw file
```

Each script finds its files from the repo root, so you can run it from any directory. Run the scripts in the order above, because both analyses read the clean CSV.

## Layout

```
data/raw/StarWars.csv            original survey file (never modified; .gitattributes stops Git changing line endings)
data/clean/starwars_clean.csv    1,186 respondents x 40 snake_case columns
src/clean.py                     cleaning and validation
src/analysis_films.py            Q1: most-liked film; Q2: fans vs non-fans
src/analysis_shot_first.py       Q3: who shot first, by gender
tests/test_data.py               independent verifier: recomputes key numbers from the RAW file
outputs/                         charts (PNG) and results (JSON)
PLAN.md                          data problems found and how each is fixed
REPORT.md                        answers, charts, limitations
```
