"""Step 3: every figure used in the README and the LaTeX report.

Writes PNG (README) and PDF (vector, LaTeX) to outputs/figures/.
Run from the repository root:  python src/03_figures.py
"""
import json
import logging
from pathlib import Path

import duckdb
import matplotlib
import numpy as np
import pandas as pd
matplotlib.use("Agg")
logging.getLogger("fontTools").setLevel(logging.ERROR)   # silence font-metadata notices
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "outputs" / "figures"
F.mkdir(parents=True, exist_ok=True)
R = json.load(open(ROOT / "outputs" / "results.json"))
T = ROOT / "outputs" / "tables"
con = duckdb.connect(str(ROOT / "recsys.duckdb"), read_only=True)

# ---------------------------------------------------------------- style
INK, TXT, SUB = "#1E1B4B", "#334155", "#64748B"
VIOLET, VIOLET_M, VIOLET_L = "#6D28D9", "#8B5CF6", "#DDD6FE"
ORANGE, GREEN, AMBER, SLATE, MIST = "#F97316", "#10B981", "#F59E0B", "#94A3B8", "#F1F5F9"
FONT = "Poppins" if "Poppins" in {f.name for f in matplotlib.font_manager.fontManager.ttflist} else "DejaVu Sans"
plt.rcParams.update({
    "font.family": FONT, "font.size": 8.2, "text.color": TXT, "axes.labelcolor": SUB, "axes.edgecolor": "#CBD5E1",
    "xtick.color": SUB, "ytick.color": SUB, "xtick.labelsize": 7.6, "ytick.labelsize": 7.6, "axes.labelsize": 8,
    "axes.titlesize": 9.2, "axes.titleweight": "medium", "axes.titlelocation": "left", "axes.titlecolor": INK,
    "axes.titlepad": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": "#E2E8F0", "grid.linestyle": (0, (2, 2)), "grid.linewidth": .7,
    "axes.axisbelow": True, "legend.frameon": False, "legend.fontsize": 7.6, "xtick.major.size": 0, "ytick.major.size": 0,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.04, "pdf.fonttype": 42})
FULL, HALF = 6.3, 3.05
NAME = {"visit": "Page visit", "search": "Search", "cart_add": "Cart add", "cart_remove": "Cart remove", "purchase": "Purchase"}


def save(fig, name):
    fig.savefig(F / f"{name}.pdf")
    fig.savefig(F / f"{name}.png", dpi=300)
    plt.close(fig)


def pct_fmt(ax, axis="y"):
    f = matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%")
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(f)


def headline(ax, title, sub=None):
    ax.set_title(title, loc="left", fontsize=9.2, fontweight="medium", color=INK, pad=16 if sub else 9)
    if sub:
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=7.4, color=SUB, va="bottom")


c = R["cart"]
ov = pd.read_csv(T / "events_overview.csv").set_index("event")
order = ["visit", "search", "cart_add", "purchase", "cart_remove"]

# ---------------------------------------------------------------- fig00a pipeline (chevrons)
steps = [("Sample", "46,673 buyers\n9.0M events", "SQL"), ("Cart fate", "bought, removed,\nunresolved", "SQL"),
         ("Journey", "transitions,\nsessions, cohorts", "SQL"), ("Segment", "segments +\nWelch's t-test", "Python"),
         ("Stress-test", "like-for-like,\nper session", "Python"), ("Prioritise", "JTBD +\nRICE", "Python")]
fig, ax = plt.subplots(figsize=(FULL, 1.75)); ax.set_xlim(0, 12.2); ax.set_ylim(0, 3.5); ax.axis("off")
w, h, d = 2.05, 1.15, 0.38
shades = ["#4C1D95", "#5B21B6", "#6D28D9", "#7C3AED", "#8B5CF6", ORANGE]
for i, (t, s, tool) in enumerate(steps):
    x, y = 0.05 + i * (w - 0.02), 1.75
    pts = [(x, y), (x + w - d, y), (x + w, y + h / 2), (x + w - d, y + h), (x, y + h)] + ([] if i == 0 else [(x + d, y + h / 2)])
    ax.add_patch(Polygon(pts, closed=True, fc=shades[i], ec="white", lw=2))
    ax.text(x + w / 2 + (0.12 if i else -0.08), y + h / 2, t, ha="center", va="center", color="white", fontsize=7.4, fontweight="medium")
    ax.text(x + w / 2, y + h + 0.3, f"0{i + 1}", ha="center", fontsize=7.5, color=SLATE, fontweight="medium")
    ax.text(x + w / 2, y - 0.25, s, ha="center", va="top", fontsize=6.5, color=TXT, linespacing=1.35)
    ax.add_patch(FancyBboxPatch((x + w / 2 - 0.42, 0.08), 0.84, 0.36, boxstyle="round,pad=0,rounding_size=0.17",
                                fc=VIOLET_L if tool == "SQL" else "#FFEDD5", ec="none"))
    ax.text(x + w / 2, 0.26, tool, ha="center", va="center", fontsize=6.8, color=VIOLET if tool == "SQL" else "#C2410C")
save(fig, "fig00a_pipeline")

# ---------------------------------------------------------------- fig00b HEART scorecard
hr = R["heart"]
rows = [("H", "Happiness", "Do shoppers find\nwhat they want?", "Search sessions ending\nwith no cart or purchase",
         f"{hr['happiness']['unsuccessful_search_pct']}% of search\nsessions fail", True),
        ("E", "Engagement", "How actively do\nshoppers browse?", "Sessions, searches\nand visits per user",
         f"Median {hr['engagement']['sessions_median']:.0f} sessions\nper user", False),
        ("A", "Adoption", "Do shoppers use the\ncart and search?", "Buyers who ever used\neach feature",
         f"Cart {hr['adoption']['cart_pct']}%,\nsearch {hr['adoption']['search_pct']}%", True),
        ("R", "Retention", "Do buyers\ncome back?", "Repeat purchase\nby monthly cohort", f"{hr['retention']['value_pct']}% buy again\nin month 1", False),
        ("T", "Task success", "Do carted items\nget bought?", "Outcome of every\ncart item",
         f"{hr['task_success']['value_pct']}% bought,\n{c['abandonment_pct']}% abandoned", False)]
fig, ax = plt.subplots(figsize=(FULL, 3.1)); ax.set_xlim(0, 12.6); ax.set_ylim(0, 7.4); ax.axis("off")
for x, lab in [(0.15, "DIMENSION"), (3.55, "GOAL"), (6.55, "SIGNAL"), (9.6, "METRIC IN THIS DATA")]:
    ax.text(x, 7.1, lab, fontsize=6.3, color=SLATE, fontweight="medium")
ax.plot([0.1, 12.5], [6.9, 6.9], color="#E2E8F0", lw=1)
for i, (L, name, goal, sig, met, proxy) in enumerate(rows):
    y = 6.2 - i * 1.34
    ax.add_patch(Circle((0.45, y), 0.32, fc=VIOLET, ec="none"))
    ax.text(0.45, y - 0.02, L, ha="center", va="center", color="white", fontsize=8.6, fontweight="bold")
    ax.text(0.98, y + (0.17 if proxy else 0), name, va="center", fontsize=7.5, color=INK, fontweight="medium")
    if proxy:
        ax.add_patch(FancyBboxPatch((0.98, y - 0.43), 1.05, 0.34, boxstyle="round,pad=0,rounding_size=0.17", fc="#FFEDD5", ec="none"))
        ax.text(1.505, y - 0.26, "proxy", ha="center", va="center", fontsize=6, color="#C2410C")
    ax.text(3.55, y, goal, va="center", fontsize=6.6, color=TXT, linespacing=1.3)
    ax.text(6.55, y, sig, va="center", fontsize=6.6, color=TXT, linespacing=1.3)
    ax.add_patch(FancyBboxPatch((9.5, y - 0.48), 3.0, 0.96, boxstyle="round,pad=0,rounding_size=0.25", fc="#EDE9FE", ec="none"))
    ax.text(9.68, y, met, va="center", fontsize=6.6, color=VIOLET, fontweight="medium", linespacing=1.3)
    if i < 4:
        ax.plot([0.1, 12.5], [y - 0.67, y - 0.67], color="#F1F5F9", lw=1)
save(fig, "fig00b_heart")

# ---------------------------------------------------------------- fig01 overview: lollipop + reach bars
fig, axs = plt.subplots(1, 2, figsize=(FULL, 2.35), gridspec_kw={"wspace": 0.55})
ax = axs[0]; y = np.arange(5)[::-1]; v = ov.loc[order, "events"].values
ax.hlines(y, 1e5, v, color=VIOLET_L, lw=2.2); ax.scatter(v, y, s=46, color=VIOLET, zorder=3)
for yi, vi in zip(y, v):
    ax.text(vi * 1.35, yi, f"{vi/1e6:.2f}M", va="center", fontsize=7.6, color=INK)
ax.set_xscale("log"); ax.set_xlim(1e5, 3e7); ax.set_yticks(y, [NAME[e] for e in order])
ax.grid(axis="x"); ax.grid(axis="y", visible=False)
ax.set_xlabel("Events (log scale)"); headline(ax, "Event volume", "9.04M events in total")
ax = axs[1]; sp = R["journey_stage_pct"]
for yi, e in zip(y, order):
    ax.add_patch(FancyBboxPatch((0, yi - .2), 100, .4, boxstyle="round,pad=0,rounding_size=0.2", fc=MIST, ec="none"))
    ax.add_patch(FancyBboxPatch((0, yi - .2), sp[e], .4, boxstyle="round,pad=0,rounding_size=0.2",
                                fc=SLATE if e == "purchase" else GREEN, ec="none"))
    ax.text(103, yi, f"{sp[e]:.1f}%" + ("  (by design)" if e == "purchase" else ""), va="center", fontsize=7.6, color=INK)
ax.set_xlim(0, 150); ax.set_ylim(-.7, 4.7); ax.set_yticks(y, [NAME[e] for e in order]); ax.set_xticks([])
ax.grid(False); ax.spines["bottom"].set_visible(False)
headline(ax, "Users reaching each stage", "Share of 46,673 purchasers")
save(fig, "fig01_data_overview")

# ---------------------------------------------------------------- fig02 journey: next-event 100% bars
tr = pd.read_csv(T / "event_transitions.csv")
M = tr.pivot(index="event", columns="next_event", values="pct_of_row").fillna(0)
rows_ = ["visit", "search", "cart_add", "cart_remove", "purchase"]
nxt = ["purchase", "cart_add", "cart_remove", "search", "visit"]
ncol = {"visit": "#E2E8F0", "search": "#C7D2FE", "cart_add": VIOLET, "cart_remove": "#FDBA74", "purchase": GREEN}
ntxt = {"visit": SUB, "search": INK, "cart_add": "white", "cart_remove": INK, "purchase": "white"}
fig, ax = plt.subplots(figsize=(FULL, 2.7)); y = np.arange(len(rows_))[::-1]
for yi, r_ in zip(y, rows_):
    left = 0
    for n in nxt:
        v = M.loc[r_, n]
        ax.barh(yi, v, left=left, color=ncol[n], height=.6, edgecolor="white", lw=1.2,
                label=NAME[n] if r_ == rows_[0] else None)
        if v >= 4.5:
            ax.text(left + v / 2, yi, f"{v:.0f}%", ha="center", va="center", fontsize=7, color=ntxt[n])
        left += v
ax.set_yticks(y, ["After a " + NAME[r_].lower() for r_ in rows_])
for t in ax.get_yticklabels():
    if "cart add" in t.get_text():
        t.set_color(INK); t.set_fontweight("medium")
cy = y[rows_.index("cart_add")]
ax.set_xlim(0, 100); ax.set_xticks([]); ax.grid(False); ax.spines["bottom"].set_visible(False)
ax.legend(title="Next event", title_fontsize=7, loc="lower center", bbox_to_anchor=(0.45, -0.24), ncol=5, fontsize=7,
          handlelength=1.2, columnspacing=1.0)
headline(ax, "What shoppers do next", f"Share of transitions to the next event. After a cart add, only {M.loc['cart_add', 'purchase']:.1f}% go straight to purchase")
save(fig, "fig02_journey_transitions")

# ---------------------------------------------------------------- fig03 cart fate waffle + time buckets
raw = np.array([c["purchased_pct"], c["removed_pct"], c["unresolved_pct"]])
cells = np.floor(raw).astype(int); cells[np.argmax(raw - np.floor(raw))] += 100 - cells.sum()
colors = [GREEN] * cells[0] + [ORANGE] * cells[1] + [AMBER] * cells[2]
fig, axs = plt.subplots(1, 2, figsize=(FULL, 2.6), gridspec_kw={"width_ratios": [1.15, 1], "wspace": 0.2})
ax = axs[0]; ax.axis("off"); ax.set_aspect("equal"); ax.set_xlim(-0.2, 15.6); ax.set_ylim(-1.4, 11.2)
for k, col in enumerate(colors):
    r_, q_ = divmod(k, 10)
    ax.add_patch(FancyBboxPatch((q_ + .08, 9 - r_ + .08), .84, .84, boxstyle="round,pad=0,rounding_size=0.15", fc=col, ec="none"))
for j, (lab, v, col) in enumerate([("Purchased", raw[0], GREEN), ("Removed", raw[1], ORANGE), ("Unresolved", raw[2], AMBER)]):
    ax.add_patch(FancyBboxPatch((10.8, 8.6 - j * 2.3), .6, .6, boxstyle="round,pad=0,rounding_size=0.12", fc=col, ec="none"))
    ax.text(11.7, 8.9 - j * 2.3, f"{lab}\n{v:.1f}%", va="center", fontsize=6.8, color=INK, linespacing=1.25)
ax.text(0, 10.55, f"Fate of {c['cart_items']:,} cart items", fontsize=9.2, color=INK, fontweight="medium")
ax.text(0, -1.0, "each square = 1% of cart items", fontsize=6.5, color=SUB)
ax = axs[1]
ch = con.execute("SELECT EPOCH(first_buy_ts - first_cart_ts)/3600 AS h FROM cart_items "
                 "WHERE was_purchased AND first_buy_ts >= first_cart_ts").df().h
labs = ["<1h", "1-6h", "6-24h", "1-3d", "3-7d", ">7d"]
tb = pd.cut(ch, [-1, 1, 6, 24, 72, 168, 1e9], labels=labs).value_counts(normalize=True).reindex(labs) * 100
ax.bar(labs, tb.values, color=[VIOLET] + [VIOLET_L] * 5, width=.62)
for i, v in enumerate(tb.values):
    ax.text(i, v + 1.5, f"{v:.1f}%", ha="center", fontsize=7.4, color=INK)
ax.set_ylim(0, 78); pct_fmt(ax); ax.set_xlabel("Time from first cart-add to purchase")
headline(ax, "When carted items sell", "Items that were eventually bought")
save(fig, "fig03_cart_outcomes")

# ---------------------------------------------------------------- fig04 cohorts: retention curves + dot plot
coh = pd.read_csv(T / "cohort_retention.csv", parse_dates=["cohort_month"])
cab = pd.read_csv(T / "abandonment_by_cohort.csv", parse_dates=["cm"])
fig, axs = plt.subplots(1, 2, figsize=(FULL, 2.6), gridspec_kw={"width_ratios": [1.4, 1], "wspace": 0.3})
ax = axs[0]
pal = {"2022-06": SLATE, "2022-07": "#4C1D95", "2022-08": VIOLET, "2022-09": VIOLET_M, "2022-10": "#C4B5FD"}
for cm, g in coh.groupby("cohort_month"):
    key = cm.strftime("%Y-%m")
    if key not in pal:
        continue
    g = g[g.months_since_first >= 1].sort_values("months_since_first")
    full, partial = g.iloc[:-1], g.iloc[-2:]
    ax.plot(full.months_since_first, full.pct_retained, "--" if key == "2022-06" else "-", color=pal[key], lw=1.8,
            marker="o", ms=3.5, label=cm.strftime("%b") + ("*" if key == "2022-06" else ""))
    ax.plot(partial.months_since_first, partial.pct_retained, ":", color=pal[key], lw=1.4)
    ax.scatter(partial.months_since_first.iloc[-1:], partial.pct_retained.iloc[-1:], s=18, facecolor="white",
               edgecolor=pal[key], zorder=3)
ax.set_xticks(range(1, 7), [f"M{k}" for k in range(1, 7)]); ax.set_ylim(0, 45); pct_fmt(ax)
ax.set_xlabel("Months since first purchase")
ax.legend(ncol=5, loc="lower center", fontsize=6.8, bbox_to_anchor=(0.5, -0.4), handlelength=1.4, columnspacing=0.9)
ax.text(0.5, -0.5, "* June includes earlier customers.  Hollow point = December (8 days of data).", transform=ax.transAxes, ha="center", fontsize=6.2, color=SUB)
headline(ax, "Repeat purchase by cohort", "Share of each cohort buying again")
ax = axs[1]
ax.axhline(c["abandonment_pct"], color=SLATE, ls=(0, (3, 2)), lw=1)
ax.text(6.45, c["abandonment_pct"], f"overall\n{c['abandonment_pct']}%", fontsize=6.4, color=SUB, ha="left", va="center")
ax.vlines(range(len(cab)), 45, cab.abandonment, color=VIOLET_L, lw=2)
ax.scatter(range(len(cab)), cab.abandonment, s=40, color=VIOLET, zorder=3)
for i, v in enumerate(cab.abandonment):
    ax.text(i, v + 1.6, f"{v:.0f}", ha="center", fontsize=7, color=INK)
ax.set_xticks(range(len(cab)), cab.cm.dt.strftime("%b")); ax.set_xlim(-0.5, 7.4); ax.set_ylim(45, 65); ax.set_yticks([45, 50, 55, 60, 65]); pct_fmt(ax)
headline(ax, "Abandonment by cohort", "Stable between 52% and 59%")
save(fig, "fig04_cohorts")

# ---------------------------------------------------------------- fig05 segments: distributions (boxplots, log)
us = con.execute("SELECT abandon_segment, searches, visits FROM user_segments").df()
segs = ["low_abandon", "moderate_abandon", "high_abandon"]
fig, axs = plt.subplots(1, 2, figsize=(FULL, 2.5), gridspec_kw={"wspace": 0.35})
for ax, col, title in [(axs[0], "searches", "Searches per user"), (axs[1], "visits", "Page visits per user")]:
    data = [us.loc[us.abandon_segment == s, col] + 1 for s in segs]
    bp = ax.boxplot(data, vert=False, widths=.52, patch_artist=True, showfliers=False, whis=(5, 95),
                    medianprops=dict(color="white", lw=1.6), whiskerprops=dict(color=SLATE), capprops=dict(color=SLATE))
    for b, clr in zip(bp["boxes"], [SLATE, VIOLET_M, VIOLET]):
        b.set(facecolor=clr, edgecolor="none")
    means = [us.loc[us.abandon_segment == s, col].mean() for s in segs]
    ax.scatter(np.array(means) + 1, range(1, 4), marker="D", s=26, color=ORANGE, zorder=4)
    for i, m in enumerate(means):
        ax.text((m + 1) * 1.2, i + 1.33, f"mean {m:.1f}", fontsize=6.8, color="#C2410C")
    ax.set_xscale("log"); ax.set_yticks(range(1, 4), ["Low", "Moderate", "High"])
    ax.grid(axis="x"); ax.grid(axis="y", visible=False)
    ax.set_xlabel(f"{col.capitalize()} + 1 (log scale)")
    headline(ax, title, "Box = IQR, whiskers = 5th-95th pct., diamond = mean")
axs[0].set_ylabel("Abandon segment")
save(fig, "fig05_segments")

# ---------------------------------------------------------------- fig06 stress test: slope chart
st = R["stress_test"]
means = [R["headline"]["searches"]["ratio_of_means"], st["searches"]["ratio_of_means"], st["searches_per_session"]["ratio_of_means"]]
meds = [st["searches"]["median_a"] / st["searches"]["median_b"], st["searches_per_session"]["median_a"] / st["searches_per_session"]["median_b"]]
fig, ax = plt.subplots(figsize=(FULL, 2.6))
ax.axhline(1, color=SLATE, lw=1, ls=(0, (3, 2)))
ax.text(0.55, 0.93, "no difference (1×)", fontsize=6.8, color=SUB, va="top", ha="center")
ax.plot(range(3), means, color=VIOLET, lw=2.2, marker="o", ms=8, mfc="white", mew=2.2, label="Ratio of means", zorder=3)
ax.plot([1, 2], meds, color=ORANGE, lw=2.2, marker="s", ms=7, mfc="white", mew=2.2, label="Ratio of medians", zorder=3)
for i, v in enumerate(means):
    ax.text(i + 0.08, v * (1.12 if i < 2 else 1 / 1.22), f"{v:.2f}×", fontsize=8.6, color=VIOLET, fontweight="medium")
for i, v in zip([1, 2], meds):
    ax.text(i + 0.1, v * (1 / 1.42 if i == 1 else 1.12), f"{v:.2f}×", fontsize=8.6, color=ORANGE, fontweight="medium")
ax.text(0.08, 1.35, "median not defined\n(low-abandon median is 0)", fontsize=6.6, color=SUB)
ax.set_yscale("log"); ax.set_ylim(0.75, 32); ax.set_yticks([1, 2, 5, 10, 20], ["1×", "2×", "5×", "10×", "20×"])
ax.set_xticks(range(3), ["All users\n(headline)", "Cart users only\n(3+ cart-adds)", "Cart users,\nper session"])
ax.set_xlim(-0.25, 2.4); ax.legend(loc="upper right")
headline(ax, "How much more do high-abandon users search?", "The gap shrinks as the comparison becomes like-for-like")
save(fig, "fig06_stress_test")

# ---------------------------------------------------------------- fig07 substitution: 100% stacked bars
sb = R["substitution"]
keys = ["all", "high_abandon", "moderate_abandon", "low_abandon"]
labs = ["All abandoned items", "High abandon", "Moderate abandon", "Low abandon"]
same = np.array([sb[k]["same_category_7d_pct"] for k in keys]); anyp = np.array([sb[k]["any_purchase_7d_pct"] for k in keys])
other, none = anyp - same, 100 - anyp
fig, ax = plt.subplots(figsize=(FULL, 2.2)); y = np.arange(4)[::-1]
ax.barh(y, same, color=VIOLET, height=.56, label="Bought a same-category alternative")
ax.barh(y, other, left=same, color=VIOLET_L, height=.56, label="Bought something else")
ax.barh(y, none, left=anyp, color="#E2E8F0", height=.56, label="No purchase within 7 days")
for yi, s_, o_, n_ in zip(y, same, other, none):
    ax.text(s_ / 2, yi, f"{s_:.0f}%", ha="center", va="center", color="white", fontsize=7.6, fontweight="medium")
    ax.text(s_ + o_ / 2, yi, f"{o_:.0f}%", ha="center", va="center", color=INK, fontsize=7.4)
    ax.text(s_ + o_ + n_ / 2, yi, f"{n_:.0f}%", ha="center", va="center", color=SUB, fontsize=7.4)
ax.set_yticks(y, labs); ax.set_xlim(0, 100); ax.set_xticks([]); ax.grid(False); ax.spines["bottom"].set_visible(False)
ax.legend(loc="lower center", bbox_to_anchor=(0.42, -0.3), ncol=3, fontsize=7.1)
headline(ax, "What happened after an item was abandoned", "Purchases by the same user within 7 days of the cart-add")
save(fig, "fig07_substitution")

# ---------------------------------------------------------------- fig08 price: dot + CI
pq = pd.DataFrame(R["price_quartiles"])
fig, ax = plt.subplots(figsize=(HALF, 2.5))
ax.axhline(c["purchased_pct"], color=SLATE, ls=(0, (3, 2)), lw=1)
ax.text(3.45, c["purchased_pct"] - 6.5, f"overall {c['purchased_pct']}%", fontsize=6.6, color=SUB, ha="right")
ax.errorbar(range(4), pq.rate, yerr=pq.ci95, fmt="o", ms=8, color=VIOLET, capsize=4, lw=1.4)
for i, r in pq.iterrows():
    ax.text(i, r.rate + 3.2, f"{r.rate:.1f}%", ha="center", fontsize=7.6, color=INK)
ax.set_xticks(range(4), [f"Q{int(r.price_quartile)}\n{int(r.lo)}-{int(r.hi)}" for _, r in pq.iterrows()])
ax.set_ylim(0, 60); ax.set_xlim(-0.5, 3.5); pct_fmt(ax); ax.set_xlabel("Price quartile (bucket range)")
headline(ax, "Purchase rate by price", f"Correlation with abandonment: r = {R['corr_price_abandonment']:.2f}")
save(fig, "fig08_price")

# ---------------------------------------------------------------- fig09 categories: ranked dot curve
cat = pd.read_csv(T / "category_abandonment.csv").sort_values("abandonment_rate").reset_index(drop=True)
cs = R["categories"]
fig, ax = plt.subplots(figsize=(FULL * 0.6, 2.5))
ax.axhspan(cs["p25"], cs["p75"], color=VIOLET_L, alpha=.5, lw=0)
ax.scatter(cat.index, cat.abandonment_rate, s=5, color=VIOLET, lw=0, zorder=3)
ax.axhline(cs["median"], color=VIOLET, lw=1, ls=(0, (3, 2)))
ax.text(5, cs["p75"] + 1.5, f"middle half: {cs['p25']}-{cs['p75']}%", fontsize=6.9, color=VIOLET)
ax.annotate(f"lowest {cs['min']}%", xy=(0, cs["min"]), xytext=(45, cs["min"] - 4), fontsize=6.9, color=ORANGE,
            arrowprops=dict(arrowstyle="-", color=ORANGE, lw=.8))
ax.annotate(f"highest {cs['max']}%", xy=(len(cat) - 1, cs["max"]), xytext=(len(cat) - 190, cs["max"] + 1), fontsize=6.9,
            color=ORANGE, arrowprops=dict(arrowstyle="-", color=ORANGE, lw=.8))
ax.set_ylim(20, 92); pct_fmt(ax); ax.set_xlabel(f"{cs['n']} categories (200+ cart items), ranked")
headline(ax, "Abandonment across categories", f"Median {cs['median']}%")
save(fig, "fig09_categories")

# ---------------------------------------------------------------- fig10 RICE: value vs effort bubbles
rc = pd.DataFrame(R["rice"])
rc["value"] = rc.reach * rc.impact * rc.confidence
fig, ax = plt.subplots(figsize=(FULL, 2.9))
ax.axvline(5.5, color="#E2E8F0", lw=1); ax.axhline(340, color="#E2E8F0", lw=1)
for tx, ty, t, ha in [(1.2, 515, "High value, lower effort", "left"), (8.8, 515, "High value, higher effort", "right")]:
    ax.text(tx, ty, t, fontsize=6.6, color=SLATE, ha=ha, style="italic")
off = {"Comparison tool for heavy searchers": (0, 48, "center"), "Reminders for items left in the cart": (0, 42, "center"),
       "Better product info in high-abandon categories": (0, -38, "center"),
       "Personalised recommendations before cart-add": (0.1, 36, "center")}
top = rc.rice_score.idxmax()
for i, r in rc.iterrows():
    ax.scatter(r.effort, r.value, s=r.rice_score * 9, color=ORANGE if i == top else VIOLET_M, alpha=.9, ec="white", lw=1.5, zorder=3)
    ax.text(r.effort, r.value, f"{r.rice_score:.0f}", ha="center", va="center", color="white", fontsize=7.6,
            fontweight="medium", zorder=4)
    dx, dy, ha = off.get(r.intervention, (0, 40, "center"))
    ax.text(r.effort + dx, r.value + dy, r.intervention, fontsize=6.9, color=INK, ha=ha, va="center")
ax.set_xlim(1, 9); ax.set_ylim(185, 535); ax.set_xlabel("Effort (1-10)"); ax.set_ylabel("Reach × Impact × Confidence")
ax.grid(False)
headline(ax, "Value vs. effort", "Bubble size and label = RICE score")
save(fig, "fig10_rice")
print("Figures written to outputs/figures/")
