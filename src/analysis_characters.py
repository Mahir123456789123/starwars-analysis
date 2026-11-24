"""Character favourability (Q4).

Q4. Which Star Wars character is the most liked and the most disliked?

Net favourability = (% very + somewhat favourable) - (% somewhat + very unfavourable),
as a % of the people who RATED the character. "Rated" means gave one of the five
opinion answers (very/somewhat favourable, neutral, somewhat/very unfavourable).
"Unfamiliar (N/A)" and blank are not ratings and are excluded from the
denominator; the unfamiliar share is reported separately.

Reads data/clean/starwars_clean.csv and writes:
  outputs/character_results.json
  outputs/chart_character_favourability.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean" / "starwars_clean.csv"
OUT = ROOT / "outputs"

CHARACTERS = {  # clean column suffix -> display name (order as in the survey)
    "han": "Han Solo", "luke": "Luke Skywalker", "leia": "Princess Leia",
    "anakin": "Anakin Skywalker", "obiwan": "Obi-Wan Kenobi",
    "palpatine": "Emperor Palpatine", "vader": "Darth Vader",
    "lando": "Lando Calrissian", "boba": "Boba Fett", "c3po": "C-3PO",
    "r2d2": "R2-D2", "jarjar": "Jar Jar Binks", "padme": "Padme Amidala",
    "yoda": "Yoda",
}
FAVOURABLE = ["very_favorable", "somewhat_favorable"]
UNFAVOURABLE = ["somewhat_unfavorable", "very_unfavorable"]
RATED = FAVOURABLE + ["neutral"] + UNFAVOURABLE
LEVELS = RATED + ["unfamiliar"]

# Palette (same reference palette as the other analysis scripts)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e6e5e1"
BLUE, BLUE_LIGHT = "#2a78d6", "#9cc2ee"
ORANGE, ORANGE_LIGHT = "#eb6834", "#f5b89f"


def net_favourability(responses: pd.Series) -> dict:
    """Score one character's responses (clean labels, '' = blank)."""
    unexpected = set(responses[responses != ""]) - set(LEVELS)
    if unexpected:
        raise ValueError(f"unexpected favourability values: {unexpected}")
    counts = {lvl: int((responses == lvl).sum()) for lvl in LEVELS}
    n_rated = sum(counts[l] for l in RATED)
    n_fav = sum(counts[l] for l in FAVOURABLE)
    n_unfav = sum(counts[l] for l in UNFAVOURABLE)
    n_answered = n_rated + counts["unfamiliar"]
    pct = lambda k: round(100 * k / n_rated, 1)  # noqa: E731
    return {
        "counts": counts,
        "n_rated": n_rated,
        "n_answered": n_answered,
        "n_blank": int((responses == "").sum()),
        "pct_very_favorable": pct(counts["very_favorable"]),
        "pct_somewhat_favorable": pct(counts["somewhat_favorable"]),
        "pct_neutral": pct(counts["neutral"]),
        "pct_somewhat_unfavorable": pct(counts["somewhat_unfavorable"]),
        "pct_very_unfavorable": pct(counts["very_unfavorable"]),
        "pct_favorable": pct(n_fav),
        "pct_unfavorable": pct(n_unfav),
        "net_favourability": round(100 * (n_fav - n_unfav) / n_rated, 1),
        "pct_unfamiliar_of_answered": round(100 * counts["unfamiliar"] / n_answered, 1),
    }


def analyse(df: pd.DataFrame) -> dict:
    chars = []
    for key, name in CHARACTERS.items():
        res = net_favourability(df[f"fav_{key}"])
        chars.append({"character": key, "name": name, **res})
    chars.sort(key=lambda c: c["net_favourability"], reverse=True)
    return {
        "definition": "net_favourability = (very+somewhat favourable - somewhat+very unfavourable) "
                      "/ n_rated * 100; n_rated excludes 'unfamiliar' and blank",
        "n_respondents": int(len(df)),
        "characters": chars,  # sorted best -> worst net score
        "most_liked": {k: chars[0][k] for k in ("character", "name", "net_favourability")},
        "most_disliked": {k: chars[-1][k] for k in ("character", "name", "net_favourability")},
        "most_unfavourable_share": max(
            ({k: c[k] for k in ("character", "name", "pct_unfavorable")} for c in chars),
            key=lambda c: c["pct_unfavorable"]),
    }


def chart(res: dict, path: Path):
    chars = res["characters"]  # best first
    fig, ax = plt.subplots(figsize=(9, 7), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(INK_2)
    ax.tick_params(colors=INK_2, length=0, labelsize=10)
    ax.tick_params(axis="y", labelcolor=INK, labelsize=10.5)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)

    y = np.arange(len(chars))[::-1]
    h = 0.66
    vf = np.array([c["pct_very_favorable"] for c in chars])
    sf = np.array([c["pct_somewhat_favorable"] for c in chars])
    su = np.array([c["pct_somewhat_unfavorable"] for c in chars])
    vu = np.array([c["pct_very_unfavorable"] for c in chars])
    # Diverging stack: favourable to the right of 0, unfavourable to the left.
    ax.barh(y, vf, height=h, color=BLUE, label="Very favourable")
    ax.barh(y, sf, left=vf, height=h, color=BLUE_LIGHT, label="Somewhat favourable")
    ax.barh(y, -su, height=h, color=ORANGE_LIGHT, label="Somewhat unfavourable")
    ax.barh(y, -vu, left=-su, height=h, color=ORANGE, label="Very unfavourable")
    ax.axvline(0, color=INK_2, linewidth=0.8)

    ax.set_xlim(-65, 128)
    for yi, c, right in zip(y, chars, vf + sf):
        net = c["net_favourability"]
        ax.text(right + 1.5, yi, f"net {net:+.1f}", va="center", ha="left", fontsize=9.5,
                fontweight="bold", color=BLUE if net >= 0 else ORANGE)
        ax.text(127, yi, f"{c['pct_unfamiliar_of_answered']:.0f}%", va="center", ha="right",
                fontsize=9, color=INK_2)
    ax.text(127, y[0] + 0.75, "unfamiliar", va="bottom", ha="right", fontsize=8.5, color=INK_2)

    labels = [f"{c['name']}  (n={c['n_rated']})" for c in chars]
    ax.set_yticks(y, labels)
    ticks = [-60, -40, -20, 0, 20, 40, 60, 80, 100]
    ax.set_xticks(ticks, [f"{abs(t)}%" for t in ticks])
    ax.set_xlabel("% of people who rated the character  (← unfavourable  |  favourable →)",
                  color=INK_2, fontsize=10)
    leg = ax.legend(loc="lower center", bbox_to_anchor=(0.42, 1.0), ncol=4, frameon=False,
                    fontsize=9, handlelength=1.2, columnspacing=1.2)
    for t in leg.get_texts():
        t.set_color(INK)

    best, worst = res["most_liked"], res["most_disliked"]
    fig.suptitle(f"{best['name']} is the best-liked character; {worst['name']} the most disliked",
                 x=0.02, ha="left", fontsize=13.5, fontweight="bold", color=INK, y=0.975)
    fig.text(0.02, 0.925,
             f"Net favourability = % favourable − % unfavourable  "
             f"({best['name']} {best['net_favourability']:+.1f}, "
             f"{worst['name']} {worst['net_favourability']:+.1f}). Neutral answers fill the gap.",
             ha="left", fontsize=9.5, color=INK_2)
    fig.text(0.02, 0.015,
             "n = respondents who gave an opinion (very/somewhat favourable, neutral, somewhat/very "
             "unfavourable); 'Unfamiliar' and blanks excluded.\n"
             "Right column: share of answerers who said they were unfamiliar with the character.",
             ha="left", fontsize=8.2, color=INK_2)
    fig.tight_layout(rect=(0, 0.06, 1, 0.885))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def summary(res: dict) -> str:
    L = [f"Q4  Character net favourability (n respondents={res['n_respondents']})",
         f"    {'character':<20}{'net':>7}{'fav%':>7}{'unfav%':>8}{'neut%':>7}"
         f"{'n_rated':>9}{'unfam%':>8}"]
    for c in res["characters"]:
        L.append(f"    {c['name']:<20}{c['net_favourability']:>+7.1f}{c['pct_favorable']:>7.1f}"
                 f"{c['pct_unfavorable']:>8.1f}{c['pct_neutral']:>7.1f}{c['n_rated']:>9}"
                 f"{c['pct_unfamiliar_of_answered']:>8.1f}")
    L.append(f"    Most liked:    {res['most_liked']['name']} ({res['most_liked']['net_favourability']:+.1f})")
    L.append(f"    Most disliked: {res['most_disliked']['name']} "
             f"({res['most_disliked']['net_favourability']:+.1f})")
    u = res["most_unfavourable_share"]
    L.append(f"    Highest unfavourable share: {u['name']} ({u['pct_unfavorable']:.1f}%)")
    return "\n".join(L)


def main():
    OUT.mkdir(exist_ok=True)
    df = pd.read_csv(CLEAN, dtype=str, keep_default_na=False)
    res = analyse(df)
    with open(OUT / "character_results.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2, ensure_ascii=False)
    chart(res, OUT / "chart_character_favourability.png")
    print(summary(res))
    print("Wrote outputs/character_results.json and outputs/chart_character_favourability.png")


if __name__ == "__main__":
    main()
