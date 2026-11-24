"""Q3: Who do respondents think shot first (Han or Greedo), and does it differ by gender?

Reads data/clean/starwars_clean.csv and writes:
  - outputs/shot_first_results.json
  - outputs/chart_shot_first_by_gender.png

Chi-square p-values are computed without scipy using closed-form survival
functions (dof=1: erfc(sqrt(chi2/2)); dof=2: exp(-chi2/2)).
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
DATA = ROOT / "data" / "clean" / "starwars_clean.csv"
OUT_DIR = ROOT / "outputs"
OUT_JSON = OUT_DIR / "shot_first_results.json"
OUT_PNG = OUT_DIR / "chart_shot_first_by_gender.png"

CATS = ["han", "greedo", "dont_understand"]
CAT_LABELS = {"han": "Han", "greedo": "Greedo", "dont_understand": "Don't understand the question"}
GENDERS = ["male", "female"]

# Colour-blind-safe categorical slots (validated: blue vs orange) + muted neutral.
COLORS = {"han": "#2a78d6", "greedo": "#eb6834", "dont_understand": "#c3c2b7"}
TEXT_ON = {"han": "#ffffff", "greedo": "#ffffff", "dont_understand": "#0b0b0b"}
INK, INK_2, MUTED, SURFACE = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"


def r3(x: float) -> float:
    return round(float(x), 3)


def pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else float("nan")


def chi2_sf(chi2: float, dof: int) -> float:
    if dof == 1:
        return math.erfc(math.sqrt(chi2 / 2.0))
    if dof == 2:
        return math.exp(-chi2 / 2.0)
    raise ValueError(f"closed-form p-value only implemented for dof 1 or 2, got {dof}")


def chi_square(table: pd.DataFrame) -> dict:
    obs = table.to_numpy(dtype=float)
    n = obs.sum()
    expected = np.outer(obs.sum(axis=1), obs.sum(axis=0)) / n
    chi2 = float(((obs - expected) ** 2 / expected).sum())
    dof = (obs.shape[0] - 1) * (obs.shape[1] - 1)
    k = min(obs.shape) - 1
    return {
        "n": int(n),
        "chi2": r3(chi2),
        "dof": int(dof),
        "p_value": float(f"{chi2_sf(chi2, dof):.3g}"),
        "cramers_v": r3(math.sqrt(chi2 / (n * k))),
        "min_expected_count": r3(expected.min()),
    }


def main() -> None:
    df = pd.read_csv(DATA)
    sf = df["shot_first"]
    n_total = len(df)
    answered = sf.dropna()
    n_answered = len(answered)
    n_blank = int(sf.isna().sum())

    counts_all = {c: int((answered == c).sum()) for c in CATS}
    hg_all = counts_all["han"] + counts_all["greedo"]
    overall = {
        "n_respondents": n_total,
        "n_answered": n_answered,
        "n_blank": n_blank,
        "counts": counts_all,
        "pct_of_answered": {c: pct(counts_all[c], n_answered) for c in CATS},
        "n_han_or_greedo": hg_all,
        "pct_of_han_or_greedo": {
            "han": pct(counts_all["han"], hg_all),
            "greedo": pct(counts_all["greedo"], hg_all),
        },
    }

    # By gender (answered shot_first only)
    ans = df.loc[sf.notna(), ["gender", "shot_first"]]
    n_blank_gender_answered = int(ans["gender"].isna().sum())
    g = ans[ans["gender"].isin(GENDERS)]
    ct = pd.crosstab(g["gender"], g["shot_first"]).reindex(index=GENDERS, columns=CATS, fill_value=0)

    by_gender = {}
    for gen in GENDERS:
        row = {c: int(ct.loc[gen, c]) for c in CATS}
        n_g = sum(row.values())
        hg = row["han"] + row["greedo"]
        by_gender[gen] = {
            "n_answered": n_g,
            "counts": row,
            "row_pct": {c: pct(row[c], n_g) for c in CATS},
            "n_han_or_greedo": hg,
            "han_share_of_han_or_greedo_pct": pct(row["han"], hg),
        }

    chi_3cat = chi_square(ct)
    chi_hg = chi_square(ct[["han", "greedo"]])

    # Two-proportion difference: male minus female Han share among Han+Greedo answerers
    nm, nf = by_gender["male"]["n_han_or_greedo"], by_gender["female"]["n_han_or_greedo"]
    pm = by_gender["male"]["counts"]["han"] / nm
    pf = by_gender["female"]["counts"]["han"] / nf
    diff = pm - pf
    se = math.sqrt(pm * (1 - pm) / nm + pf * (1 - pf) / nf)
    z = 1.959964
    diff_res = {
        "description": "male minus female Han share among Han+Greedo answerers (unpooled SE, normal approx)",
        "male_han_share": r3(pm),
        "female_han_share": r3(pf),
        "diff_pct_points": round(100 * diff, 1),
        "ci95_low_pct_points": round(100 * (diff - z * se), 1),
        "ci95_high_pct_points": round(100 * (diff + z * se), 1),
        "se": r3(se),
    }

    results = {
        "question": "Q3: Who shot first (Han or Greedo), and does it differ by gender?",
        "units_note": "keys ending in _pct / pct_* are percentages (0-100, 1 decimal); shares are proportions (0-1)",
        "overall": overall,
        "by_gender": by_gender,
        "n_blank_gender_among_answered_excluded": n_blank_gender_answered,
        "n_blank_gender_counts_by_answer": {
            c: int((ans.loc[ans["gender"].isna(), "shot_first"] == c).sum()) for c in CATS
        },
        "chi_square_gender_x_shot_first_3cat": chi_3cat,
        "chi_square_gender_x_han_vs_greedo": chi_hg,
        "han_share_difference_male_minus_female": diff_res,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")

    make_chart(overall, by_gender, diff_res, chi_hg['p_value'])
    print_summary(results)


def make_chart(overall: dict, by_gender: dict, diff_res: dict, p_hg: float) -> None:
    plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans", "sans-serif"]
    rows = [
        (f"All respondents\n(n={overall['n_answered']})", overall["pct_of_answered"]),
        (f"Male\n(n={by_gender['male']['n_answered']})", by_gender["male"]["row_pct"]),
        (f"Female\n(n={by_gender['female']['n_answered']})", by_gender["female"]["row_pct"]),
    ]
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    ys = np.arange(len(rows))[::-1]
    for y, (_, pcts) in zip(ys, rows):
        left = 0.0
        for c in CATS:
            w = pcts[c]
            ax.barh(y, w, left=left, height=0.62, color=COLORS[c],
                    edgecolor=SURFACE, linewidth=2)
            if w >= 6:
                ax.text(left + w / 2, y, f"{w:.0f}%", ha="center", va="center",
                        color=TEXT_ON[c], fontsize=10, fontweight="bold")
            left += w

    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], color=INK, fontsize=10)
    ax.set_xlim(0, 100)
    ax.set_xticks(range(0, 101, 25))
    ax.set_xticklabels([f"{t}%" for t in range(0, 101, 25)], color=MUTED, fontsize=9)
    ax.set_xlabel("% of respondents who answered", color=INK_2, fontsize=10)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", color="#c3c2b7")

    hm = by_gender["male"]["han_share_of_han_or_greedo_pct"]
    hf = by_gender["female"]["han_share_of_han_or_greedo_pct"]
    fig.suptitle("Han leads 'who shot first'; women are far likelier than men to not understand the question",
                 x=0.01, ha="left", fontsize=12.5, fontweight="bold", color=INK)
    ax.set_title(f"Among those picking Han or Greedo, Han's share: men {hm:.0f}%, women {hf:.0f}% "
                 f"(difference {diff_res['diff_pct_points']:.1f} pts, "
                 f"95% CI {diff_res['ci95_low_pct_points']:.1f} to {diff_res['ci95_high_pct_points']:.1f}; p = {p_hg:.3f})",
                 loc="left", fontsize=9.5, color=INK_2, pad=28)

    handles = [plt.Rectangle((0, 0), 1, 1, color=COLORS[c]) for c in CATS]
    ax.legend(handles, [CAT_LABELS[c] for c in CATS], loc="lower left", bbox_to_anchor=(0, 1.0),
              ncol=3, frameon=False, fontsize=9.5, handlelength=1.2, borderaxespad=0.2,
              labelcolor=INK)

    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def print_summary(res: dict) -> None:
    o = res["overall"]
    print("Q3 - Who shot first?")
    print(f"  Answered: {o['n_answered']} of {o['n_respondents']} (blank: {o['n_blank']})")
    for c in CATS:
        print(f"    {CAT_LABELS[c]:<30} {o['counts'][c]:>4}  {o['pct_of_answered'][c]:5.1f}%")
    hg = o["pct_of_han_or_greedo"]
    print(f"  Among Han/Greedo pickers (n={o['n_han_or_greedo']}): Han {hg['han']}%, Greedo {hg['greedo']}%")
    print("  By gender (row % of answered):")
    for gen in GENDERS:
        b = res["by_gender"][gen]
        rp = b["row_pct"]
        print(f"    {gen:<6} n={b['n_answered']:>3}: Han {rp['han']}%, Greedo {rp['greedo']}%, "
              f"Don't understand {rp['dont_understand']}% | Han share of Han+Greedo "
              f"{b['han_share_of_han_or_greedo_pct']}% (n={b['n_han_or_greedo']})")
    print(f"  Blank gender (excluded): {res['n_blank_gender_among_answered_excluded']}")
    for key, lab in [("chi_square_gender_x_shot_first_3cat", "gender x 3 categories"),
                     ("chi_square_gender_x_han_vs_greedo", "gender x Han/Greedo")]:
        t = res[key]
        print(f"  Chi-square {lab}: chi2={t['chi2']}, dof={t['dof']}, p={t['p_value']:.3g}, "
              f"Cramer's V={t['cramers_v']} (n={t['n']})")
    d = res["han_share_difference_male_minus_female"]
    print(f"  Han share diff (male - female): {d['diff_pct_points']} pts, "
          f"95% CI [{d['ci95_low_pct_points']}, {d['ci95_high_pct_points']}]")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)} and {OUT_PNG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
