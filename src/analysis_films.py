"""Film-level analysis of the Star Wars survey.

Q1. Which film is most liked (mean rank, median, #1 share, seen counts)?
Q2. Do fans rank the films differently from non-fans?

Reads data/clean/starwars_clean.csv and writes:
  outputs/films_results.json
  outputs/chart_film_ranking.png
  outputs/chart_fans_vs_nonfans.png
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean" / "starwars_clean.csv"
OUT = ROOT / "outputs"

EPS = ["ep1", "ep2", "ep3", "ep4", "ep5", "ep6"]
TITLES = {
    "ep1": "Episode I: The Phantom Menace",
    "ep2": "Episode II: Attack of the Clones",
    "ep3": "Episode III: Revenge of the Sith",
    "ep4": "Episode IV: A New Hope",
    "ep5": "Episode V: The Empire Strikes Back",
    "ep6": "Episode VI: Return of the Jedi",
}
SHORT = {
    "ep1": "I: The Phantom Menace",
    "ep2": "II: Attack of the Clones",
    "ep3": "III: Revenge of the Sith",
    "ep4": "IV: A New Hope",
    "ep5": "V: The Empire Strikes Back",
    "ep6": "VI: Return of the Jedi",
}

# Palette (dataviz reference palette, light mode)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#c9c8c3"
BLUE = "#2a78d6"    # categorical slot 1
ORANGE = "#eb6834"  # categorical slot 2
GRID = "#e6e5e1"

BOOL_MAP = {"True": True, "False": False, "true": True, "false": False}


def r3(x):
    """Round to 3 dp and return a native float (None for NaN)."""
    if x is None:
        return None
    x = float(x)
    if math.isnan(x):
        return None
    return round(x, 3)


def load() -> pd.DataFrame:
    df = pd.read_csv(CLEAN, dtype=str, keep_default_na=False)
    for c in ["fan", "rank_complete"] + [f"seen_{e}" for e in EPS]:
        df[c] = df[c].str.strip().map(BOOL_MAP).astype("boolean")
    df["seen_count"] = pd.to_numeric(df["seen_count"]).astype(int)
    for e in EPS:
        df[f"rank_{e}"] = pd.to_numeric(df[f"rank_{e}"].replace("", np.nan)).astype("Int64")
    return df


def ranks(df: pd.DataFrame, e: str) -> pd.Series:
    return df[f"rank_{e}"].dropna().astype(float)


def welch_t(a: pd.Series, b: pd.Series):
    na, nb = len(a), len(b)
    va, vb = a.var(ddof=1), b.var(ddof=1)
    se = math.sqrt(va / na + vb / nb)
    t = (a.mean() - b.mean()) / se
    df_ = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    return t, df_


def ci95(s: pd.Series):
    m, sd, n = s.mean(), s.std(ddof=1), len(s)
    h = 1.96 * sd / math.sqrt(n)
    return m - h, m + h


# ---------------------------------------------------------------- Q1
def q1(df: pd.DataFrame) -> dict:
    rank_cols = [f"rank_{e}" for e in EPS]
    rankers = df[rank_cols].notna().any(axis=1)
    n_seen_any = int((df["seen_count"] >= 1).sum())

    films = []
    ranked_unseen_total = 0
    for e in EPS:
        r = ranks(df, e)
        n = len(r)
        n_first = int((r == 1).sum())
        n_seen = int(df[f"seen_{e}"].fillna(False).sum())
        ranked_unseen = int((df[f"rank_{e}"].notna() & ~df[f"seen_{e}"].fillna(False)).sum())
        ranked_unseen_total += ranked_unseen
        films.append({
            "episode": e,
            "title": TITLES[e],
            "mean_rank": r3(r.mean()),
            "median_rank": r3(r.median()),
            "sd_rank": r3(r.std(ddof=1)),
            "n_ranks": n,
            "n_ranked_first": n_first,
            "pct_ranked_first": r3(100 * n_first / n),
            "n_seen": n_seen,
            "pct_seen_of_seen_any": r3(100 * n_seen / n_seen_any),
            "n_ranked_but_not_seen": ranked_unseen,
        })
    winner = min(films, key=lambda f: f["mean_rank"])
    order = [f["episode"] for f in sorted(films, key=lambda f: f["mean_rank"])]

    # Sensitivity: only respondents who saw all six films
    six = df[df["seen_count"] == 6]
    sens_films = []
    for e in EPS:
        r = ranks(six, e)
        sens_films.append({"episode": e, "title": TITLES[e],
                           "mean_rank": r3(r.mean()), "n_ranks": len(r)})
    sens_winner = min(sens_films, key=lambda f: f["mean_rank"])
    sens_order = [f["episode"] for f in sorted(sens_films, key=lambda f: f["mean_rank"])]

    # Rankers who saw nothing at all
    rankers_seen_none = int((rankers & (df["seen_count"] == 0)).sum())

    return {
        "n_respondents": int(len(df)),
        "n_seen_any": n_seen_any,
        "n_rankers": int(rankers.sum()),
        "n_complete_rankings": int(df["rank_complete"].fillna(False).sum()),
        "n_ranked_but_not_seen_total": ranked_unseen_total,
        "n_rankers_with_seen_count_0": rankers_seen_none,
        "films": films,
        "order_best_to_worst": order,
        "most_liked": {"episode": winner["episode"], "title": winner["title"],
                       "mean_rank": winner["mean_rank"]},
        "sensitivity_seen_all_six": {
            "n_respondents": int(len(six)),
            "n_rankers": int(six[rank_cols].notna().any(axis=1).sum()),
            "films": sens_films,
            "order_best_to_worst": sens_order,
            "most_liked": {"episode": sens_winner["episode"], "title": sens_winner["title"],
                           "mean_rank": sens_winner["mean_rank"]},
            "winner_changes": sens_winner["episode"] != winner["episode"],
        },
    }


# ---------------------------------------------------------------- Q2
def q2(df: pd.DataFrame) -> dict:
    fans = df[df["fan"] == True]  # noqa: E712  (nullable boolean; blanks excluded)
    non = df[df["fan"] == False]  # noqa: E712
    rank_cols = [f"rank_{e}" for e in EPS]

    films = []
    for e in EPS:
        a, b = ranks(fans, e), ranks(non, e)
        t, dof = welch_t(a, b)
        fa, fb = ci95(a), ci95(b)
        films.append({
            "episode": e,
            "title": TITLES[e],
            "fan_mean_rank": r3(a.mean()),
            "fan_n": len(a),
            "fan_ci95": [r3(fa[0]), r3(fa[1])],
            "nonfan_mean_rank": r3(b.mean()),
            "nonfan_n": len(b),
            "nonfan_ci95": [r3(fb[0]), r3(fb[1])],
            "diff_fan_minus_nonfan": r3(a.mean() - b.mean()),
            "welch_t": r3(t),
            "welch_df": r3(dof),
        })
    fan_order = [f["episode"] for f in sorted(films, key=lambda f: f["fan_mean_rank"])]
    non_order = [f["episode"] for f in sorted(films, key=lambda f: f["nonfan_mean_rank"])]
    return {
        "n_fans": int(len(fans)),
        "n_nonfans": int(len(non)),
        "n_fan_blank": int(df["fan"].isna().sum()),
        "n_fan_rankers": int(fans[rank_cols].notna().any(axis=1).sum()),
        "n_nonfan_rankers": int(non[rank_cols].notna().any(axis=1).sum()),
        "films": films,
        "fan_top_film": {"episode": fan_order[0], "title": TITLES[fan_order[0]]},
        "nonfan_top_film": {"episode": non_order[0], "title": TITLES[non_order[0]]},
        "fan_order_best_to_worst": fan_order,
        "nonfan_order_best_to_worst": non_order,
        "note": "Negative diff = fans rank the film better (lower). |welch_t| > ~1.96 "
                "suggests a difference beyond sampling noise at roughly the 5% level.",
    }


# ---------------------------------------------------------------- charts
def style_axes(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(INK_2)
    ax.tick_params(colors=INK_2, length=0, labelsize=10)
    ax.tick_params(axis="y", labelcolor=INK, labelsize=10.5)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def chart_ranking(res: dict, path: Path):
    films = sorted(res["films"], key=lambda f: f["mean_rank"])  # best first
    win = res["most_liked"]["episode"]
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style_axes(ax)

    y = np.arange(len(films))[::-1]  # best on top
    vals = [f["mean_rank"] for f in films]
    colors = [BLUE if f["episode"] == win else MUTED for f in films]
    ax.barh(y, vals, height=0.62, color=colors, edgecolor=SURFACE, linewidth=2)
    for yi, f in zip(y, films):
        bold = f["episode"] == win
        ax.text(f["mean_rank"] + 0.06, yi,
                f"{f['mean_rank']:.2f}   ·   seen by {f['n_seen']:,}",
                va="center", ha="left", fontsize=9.5,
                color=INK if bold else INK_2, fontweight="bold" if bold else "normal")
    ax.set_yticks(y, [SHORT[f["episode"]] for f in films])
    ax.set_xlim(0, 6)
    ax.set_xticks(range(0, 7))
    ax.set_xlabel("Mean rank (1 = favourite, 6 = least favourite) — lower is better",
                  color=INK_2, fontsize=10)

    fig.suptitle(f"{SHORT[win].split(': ', 1)[1]} is the best-loved Star Wars film",
                 x=0.02, ha="left", fontsize=14.5, fontweight="bold", color=INK, y=0.97)
    fig.text(0.02, 0.905,
             "Mean rank given by survey respondents who ranked the six films; "
             "shorter bar = better liked",
             ha="left", fontsize=10, color=INK_2)
    fig.text(0.02, 0.02,
             f"n = {res['n_rankers']:,} respondents who ranked at least one film "
             f"(of {res['n_respondents']:,} surveyed). 'Seen by' counts all respondents "
             f"who said they saw the film.",
             ha="left", fontsize=8.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.05, 1, 0.89))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def chart_fans(res: dict, path: Path):
    films = sorted(res["films"], key=lambda f: f["fan_mean_rank"])  # by fans' order
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style_axes(ax)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.yaxis.grid(False)

    y = np.arange(len(films))[::-1]
    for yi, f in zip(y, films):
        a, b = f["fan_mean_rank"], f["nonfan_mean_rank"]
        ax.plot([a, b], [yi, yi], color=MUTED, linewidth=2, zorder=1, solid_capstyle="round")
        ax.errorbar(a, yi, xerr=[[a - f["fan_ci95"][0]], [f["fan_ci95"][1] - a]],
                    fmt="none", ecolor=BLUE, elinewidth=1.2, capsize=3, zorder=2)
        ax.errorbar(b, yi, xerr=[[b - f["nonfan_ci95"][0]], [f["nonfan_ci95"][1] - b]],
                    fmt="none", ecolor=ORANGE, elinewidth=1.2, capsize=3, zorder=2)
        ax.scatter([a], [yi], s=80, color=BLUE, edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.scatter([b], [yi], s=80, color=ORANGE, edgecolor=SURFACE, linewidth=2, zorder=3,
                   marker="D")
        d = f["diff_fan_minus_nonfan"]
        ax.text(6.05, yi, f"{d:+.2f}", va="center", ha="left", fontsize=9.5,
                color=INK if abs(f["welch_t"]) >= 1.96 else INK_2,
                fontweight="bold" if abs(f["welch_t"]) >= 1.96 else "normal")
    ax.text(6.05, y[0] + 0.62, "fan − non-fan", ha="left", va="center",
            fontsize=8.5, color=INK_2)
    ax.set_yticks(y, [SHORT[f["episode"]] for f in films])
    ax.set_xlim(1, 6)
    ax.set_ylim(-0.6, len(films) - 0.2)
    ax.set_xlabel("Mean rank (1 = favourite, 6 = least favourite) — lower is better",
                  color=INK_2, fontsize=10)

    fan_n = res["n_fan_rankers"]
    non_n = res["n_nonfan_rankers"]
    h1 = ax.scatter([], [], s=80, color=BLUE, edgecolor=SURFACE, label=f"Fans (n = {fan_n})")
    h2 = ax.scatter([], [], s=80, color=ORANGE, edgecolor=SURFACE, marker="D",
                    label=f"Non-fans (n = {non_n})")
    leg = ax.legend(handles=[h1, h2], loc="lower right", frameon=False, fontsize=9.5,
                    bbox_to_anchor=(1.0, 1.0), ncol=2, borderaxespad=0.2)
    for t in leg.get_texts():
        t.set_color(INK)

    # Title states the finding, computed from the data
    biggest = max(res["films"], key=lambda f: abs(f["diff_fan_minus_nonfan"]))
    same_top = res["fan_top_film"]["episode"] == res["nonfan_top_film"]["episode"]
    top = SHORT[res["fan_top_film"]["episode"]].split(": ", 1)[1]
    orig_better = all(f["diff_fan_minus_nonfan"] < 0 for f in res["films"]
                      if f["episode"] in ("ep4", "ep5", "ep6"))
    preq_worse = all(f["diff_fan_minus_nonfan"] > 0 for f in res["films"]
                     if f["episode"] in ("ep1", "ep2", "ep3"))
    if orig_better and preq_worse:
        title = "Fans rank the original trilogy higher; non-fans rate the prequels higher"
    else:
        title = "Fans and non-fans rank the Star Wars films differently"
    agree = (f"both groups rank {top} first" if same_top else
             f"fans pick {top}, non-fans pick "
             f"{SHORT[res['nonfan_top_film']['episode']].split(': ', 1)[1]}")
    fig.suptitle(title, x=0.02, ha="left", fontsize=13.5, fontweight="bold", color=INK, y=0.97)
    fig.text(0.02, 0.905,
             f"Mean rank by group with 95% CI; {agree}. Largest gap: "
             f"{SHORT[biggest['episode']].split(': ', 1)[1]} "
             f"({biggest['diff_fan_minus_nonfan']:+.2f})",
             ha="left", fontsize=10, color=INK_2)
    fig.text(0.02, 0.02,
             f"n = rankers per film (fans {min(f['fan_n'] for f in films)}–"
             f"{max(f['fan_n'] for f in films)}, non-fans {min(f['nonfan_n'] for f in films)}–"
             f"{max(f['nonfan_n'] for f in films)}); respondents with blank fan answer excluded. "
             "Bold gap = |Welch t| ≥ 1.96.",
             ha="left", fontsize=8.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.05, 0.97, 0.86))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


# ---------------------------------------------------------------- main
def summary(r1: dict, r2: dict) -> str:
    L = []
    L.append(f"Q1  Most-liked film  (n respondents={r1['n_respondents']}, "
             f"seen any={r1['n_seen_any']}, rankers={r1['n_rankers']}, "
             f"complete rankings={r1['n_complete_rankings']})")
    L.append(f"    {'film':<36}{'mean':>6}{'med':>5}{'N':>5}{'#1':>5}{'#1%':>7}"
             f"{'seen':>6}{'seen%':>7}{'rk!seen':>8}")
    for f in sorted(r1["films"], key=lambda f: f["mean_rank"]):
        L.append(f"    {f['title']:<36}{f['mean_rank']:>6.3f}{f['median_rank']:>5.1f}"
                 f"{f['n_ranks']:>5}{f['n_ranked_first']:>5}{f['pct_ranked_first']:>7.1f}"
                 f"{f['n_seen']:>6}{f['pct_seen_of_seen_any']:>7.1f}"
                 f"{f['n_ranked_but_not_seen']:>8}")
    L.append(f"    Winner: {r1['most_liked']['title']} (mean rank {r1['most_liked']['mean_rank']})")
    L.append(f"    Ranks given for films not seen: {r1['n_ranked_but_not_seen_total']} "
             f"(rankers with seen_count 0: {r1['n_rankers_with_seen_count_0']})")
    s = r1["sensitivity_seen_all_six"]
    L.append(f"    Sensitivity (seen all 6, n={s['n_respondents']}, rankers={s['n_rankers']}): "
             f"winner {s['most_liked']['title']} ({s['most_liked']['mean_rank']}); "
             f"changes={s['winner_changes']}; order={' > '.join(s['order_best_to_worst'])}")
    L.append("")
    L.append(f"Q2  Fans (n={r2['n_fans']}, rankers={r2['n_fan_rankers']}) vs non-fans "
             f"(n={r2['n_nonfans']}, rankers={r2['n_nonfan_rankers']}); blank fan={r2['n_fan_blank']}")
    L.append(f"    {'film':<36}{'fan':>7}{'nF':>5}{'non':>7}{'nN':>5}{'diff':>8}{'t':>8}")
    for f in r2["films"]:
        L.append(f"    {f['title']:<36}{f['fan_mean_rank']:>7.3f}{f['fan_n']:>5}"
                 f"{f['nonfan_mean_rank']:>7.3f}{f['nonfan_n']:>5}"
                 f"{f['diff_fan_minus_nonfan']:>+8.3f}{f['welch_t']:>8.2f}")
    L.append(f"    Fan order:     {' > '.join(r2['fan_order_best_to_worst'])}")
    L.append(f"    Non-fan order: {' > '.join(r2['nonfan_order_best_to_worst'])}")
    return "\n".join(L)


def main():
    OUT.mkdir(exist_ok=True)
    df = load()
    r1, r2 = q1(df), q2(df)
    with open(OUT / "films_results.json", "w", encoding="utf-8") as fh:
        json.dump({"q1": r1, "q2": r2}, fh, indent=2, ensure_ascii=False)
    chart_ranking(r1, OUT / "chart_film_ranking.png")
    chart_fans(r2, OUT / "chart_fans_vs_nonfans.png")
    print(summary(r1, r2))


if __name__ == "__main__":
    main()
