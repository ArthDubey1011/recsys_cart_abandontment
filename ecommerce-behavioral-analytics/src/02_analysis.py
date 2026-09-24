"""Step 2: statistics on the tables built by 01_build_tables.py.

Outputs
  outputs/results.json      every number quoted in the README and the report
  outputs/tables/*.csv      summaries (journey, cart outcomes, cohorts, segments, tests, RICE)

Run from the repository root:  python src/02_analysis.py
"""
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT, TAB = ROOT / "outputs", ROOT / "outputs" / "tables"
TAB.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(str(ROOT / "recsys.duckdb"), read_only=True)
q = lambda sql: con.execute(sql).df()
R = {}

# ------------------------------------------------------------- 1. overview
ov = q("SELECT event, COUNT(*) AS events, COUNT(DISTINCT client_id) AS users FROM all_events GROUP BY event ORDER BY events DESC")
ov.to_csv(TAB / "events_overview.csv", index=False)
R["overview"] = {"users": int(q("SELECT COUNT(DISTINCT client_id) n FROM product_buy").n[0]),
                 "events_total": int(ov.events.sum()),
                 "events": dict(zip(ov.event, ov.events.astype(int))),
                 "users_by_event": dict(zip(ov.event, ov.users.astype(int))),
                 "date_range": [str(x) for x in q("SELECT MIN(ts)::DATE a, MAX(ts)::DATE b FROM all_events").iloc[0]]}

# ------------------------------------------------------------- 2. journey
users = R["overview"]["users"]
R["journey_stage_pct"] = {k: round(100 * v / users, 1) for k, v in R["overview"]["users_by_event"].items()}
tr = q("SELECT event, next_event, n, pct_of_row FROM transitions")
tr.to_csv(TAB / "event_transitions.csv", index=False)
R["transitions_pct"] = {f"{r.event}->{r.next_event}": float(r.pct_of_row) for r in tr.itertuples()}
R["pct_purchases_after_cart_add"] = float(q("""SELECT ROUND(100*AVG(CASE WHEN EXISTS (SELECT 1 FROM add_to_cart c
    WHERE c.client_id=b.client_id AND c.sku=b.sku AND c.ts<=b.ts) THEN 1 ELSE 0 END),1) v FROM product_buy b""").v[0])

# ------------------------------------------------------------- 3. cart outcomes
ci = q("SELECT * FROM cart_items")
fate = {"cart_items": len(ci), "purchased_pct": round(100 * ci.was_purchased.mean(), 1),
        "removed_pct": round(100 * ci.was_removed.mean(), 1), "unresolved_pct": round(100 * ci.unresolved.mean(), 1)}
fate["abandonment_pct"] = round(100 - 100 * ci.was_purchased.mean(), 1)
early = ci[ci.first_cart_ts < pd.Timestamp("2022-11-24")]
fate["abandonment_excl_last_14d_pct"] = round(100 - 100 * early.was_purchased.mean(), 1)
bought = ci[ci.was_purchased & (ci.first_buy_ts >= ci.first_cart_ts)]
hrs = (bought.first_buy_ts - bought.first_cart_ts).dt.total_seconds() / 3600
fate["hours_to_purchase"] = {"p50": round(float(hrs.quantile(.5)), 1), "p75": round(float(hrs.quantile(.75)), 1),
                             "p90": round(float(hrs.quantile(.9)), 1), "share_within_1h_pct": round(100 * float((hrs < 1).mean()), 1)}
R["cart"] = fate

# ------------------------------------------------------------- 4. cohorts
coh = q("SELECT * FROM cohort_retention ORDER BY cohort_month, months_since_first")
coh.to_csv(TAB / "cohort_retention.csv", index=False)
m1 = coh[(coh.months_since_first == 1) & coh.cohort_month.isin(pd.to_datetime(["2022-07-01", "2022-08-01", "2022-09-01", "2022-10-01"]))]
R["cohort_month1_repeat_pct"] = {str(r.cohort_month.date()): float(r.pct_retained) for r in m1.itertuples()}
R["cohort_month1_repeat_avg_pct"] = round(float(m1.pct_retained.mean()), 1)
cab = q("""WITH f AS (SELECT client_id, DATE_TRUNC('month', MIN(ts)) cm FROM product_buy GROUP BY 1)
           SELECT cm, COUNT(*) n, ROUND(100*(1-AVG(was_purchased::INT)),1) abandonment FROM cart_items JOIN f USING (client_id) GROUP BY cm ORDER BY cm""")
cab.to_csv(TAB / "abandonment_by_cohort.csv", index=False)
R["abandonment_by_cohort_range"] = [float(cab.abandonment.min()), float(cab.abandonment.max())]

# ------------------------------------------------------------- 5. segments + headline RCA
us = q("SELECT u.*, COALESCE(s.sessions, 0) AS sessions FROM user_segments u LEFT JOIN user_sessions s USING (client_id)")
seg = (us.groupby("abandon_segment")
       .agg(users=("client_id", "size"), avg_searches=("searches", "mean"), avg_visits=("visits", "mean"),
            avg_cart_adds=("cart_adds", "mean"), median_searches=("searches", "median"),
            pct_never_carted=("cart_adds", lambda x: 100 * (x == 0).mean()), avg_sessions=("sessions", "mean"))
       .round(2).reindex(["low_abandon", "moderate_abandon", "high_abandon"]))
seg.to_csv(TAB / "segments.csv")
R["segments"] = seg.reset_index().to_dict("records")
R["frequency_segments"] = us.frequency_segment.value_counts().to_dict()

def welch(a, b):
    t, p = stats.ttest_ind(a, b, equal_var=False)
    u, pu = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {"mean_a": round(float(a.mean()), 2), "mean_b": round(float(b.mean()), 2),
            "ratio_of_means": round(float(a.mean() / b.mean()), 2),
            "median_a": float(a.median()), "median_b": float(b.median()),
            "welch_t": round(float(t), 2), "welch_p": float(p), "mann_whitney_p": float(pu), "n_a": len(a), "n_b": len(b)}

hi, lo = us[us.abandon_segment == "high_abandon"], us[us.abandon_segment == "low_abandon"]
R["headline"] = {"searches": welch(hi.searches, lo.searches), "visits": welch(hi.visits, lo.visits)}

# ------------------------------------------------------------- 6. stress test of the headline
us["searches_per_session"] = us.searches / us.sessions.clip(lower=1)
us["visits_per_session"] = us.visits / us.sessions.clip(lower=1)
c = us[us.cart_adds >= 3].copy()
c["group"] = np.select([c.removal_rate >= 0.5, c.removal_rate < 0.2], ["high", "low"], "middle")
H, L = c[c.group == "high"], c[c.group == "low"]
R["stress_test"] = {
    "definition": "users with >= 3 cart-adds; high = removal rate >= 0.5, low = removal rate < 0.2",
    "n_high": len(H), "n_low": len(L),
    "searches": welch(H.searches, L.searches), "visits": welch(H.visits, L.visits),
    "sessions": welch(H.sessions, L.sessions), "cart_adds": welch(H.cart_adds, L.cart_adds),
    "searches_per_session": welch(H.searches_per_session, L.searches_per_session),
    "visits_per_session": welch(H.visits_per_session, L.visits_per_session),
    "spearman_removal_vs_searches": round(float(stats.spearmanr(c.removal_rate, c.searches)[0]), 3),
    "spearman_removal_vs_searches_per_session": round(float(stats.spearmanr(c.removal_rate, c.searches_per_session)[0]), 3),
    "spearman_removal_vs_cart_adds": round(float(stats.spearmanr(c.removal_rate, c.cart_adds)[0]), 3)}
ladder = pd.DataFrame([
    ("All users: high vs low abandon (headline)", R["headline"]["searches"]["ratio_of_means"], None),  # low-abandon median is 0
    ("Cart users only (>= 3 cart-adds)", R["stress_test"]["searches"]["ratio_of_means"], R["stress_test"]["searches"]["median_a"] / R["stress_test"]["searches"]["median_b"]),
    ("Cart users, searches per session", R["stress_test"]["searches_per_session"]["ratio_of_means"],
     R["stress_test"]["searches_per_session"]["median_a"] / R["stress_test"]["searches_per_session"]["median_b"])],
    columns=["comparison", "ratio_of_means", "ratio_of_medians"]).round(2)
ladder.to_csv(TAB / "stress_test_ladder.csv", index=False)
R["stress_ladder"] = ladder.to_dict("records")

# substitution (computed in SQL section 10)
sub = q("""WITH ab AS (SELECT ci.*, u.abandon_segment FROM cart_items ci JOIN user_segments u USING (client_id) WHERE NOT ci.was_purchased),
     buys AS (SELECT b.client_id, b.sku, b.ts, p.category FROM product_buy b JOIN product_properties p USING (sku))
SELECT COALESCE(abandon_segment, 'all') AS scope, COUNT(*) AS n,
       ROUND(100*AVG(CASE WHEN EXISTS (SELECT 1 FROM buys x WHERE x.client_id=ab.client_id AND x.category=ab.category AND x.sku<>ab.sku
             AND x.ts BETWEEN ab.first_cart_ts AND ab.first_cart_ts + INTERVAL 7 DAY) THEN 1 ELSE 0 END),1) AS same_cat_7d,
       ROUND(100*AVG(CASE WHEN EXISTS (SELECT 1 FROM buys x WHERE x.client_id=ab.client_id
             AND x.ts BETWEEN ab.first_cart_ts AND ab.first_cart_ts + INTERVAL 7 DAY) THEN 1 ELSE 0 END),1) AS any_7d
FROM ab GROUP BY ROLLUP (abandon_segment)""")
sub.to_csv(TAB / "substitution.csv", index=False)
R["substitution"] = {r.scope: {"n": int(r.n), "same_category_7d_pct": float(r.same_cat_7d), "any_purchase_7d_pct": float(r.any_7d)} for r in sub.itertuples()}

# ------------------------------------------------------------- 7. price and category
ci["price_quartile"] = pd.qcut(ci.price_bucket.rank(method="first"), 4, labels=[1, 2, 3, 4])
pq = ci.groupby("price_quartile", observed=True).agg(n=("was_purchased", "size"), rate=("was_purchased", "mean"),
                                                     lo=("price_bucket", "min"), hi=("price_bucket", "max")).reset_index()
pq["ci95"] = 1.96 * np.sqrt(pq.rate * (1 - pq.rate) / pq.n)
pq[["rate", "ci95"]] *= 100
pq.round(2).to_csv(TAB / "price_quartiles.csv", index=False)
R["price_quartiles"] = pq.round(2).to_dict("records")
R["corr_price_abandonment"] = round(float(np.corrcoef(ci.price_bucket, 1 - ci.was_purchased.astype(int))[0, 1]), 3)
chi2, pchi, _, _ = stats.chi2_contingency(pd.crosstab(ci.price_quartile, ci.was_purchased))
R["price_chi2"] = {"chi2": round(float(chi2), 1), "p": float(pchi),
                   "cramers_v": round(float(np.sqrt(chi2 / len(ci))), 3)}
cat = q("SELECT * FROM category_abandonment")
cat.to_csv(TAB / "category_abandonment.csv", index=False)
R["categories"] = {"n": len(cat), "min": float(cat.abandonment_rate.min()), "p25": float(cat.abandonment_rate.quantile(.25)),
                   "median": float(cat.abandonment_rate.median()), "p75": float(cat.abandonment_rate.quantile(.75)),
                   "max": float(cat.abandonment_rate.max())}

# ------------------------------------------------------------- 8. HEART metrics (Happiness and Adoption via proxies)
hp = q("""SELECT ROUND(100 * AVG(CASE WHEN has_cart_add = 1 OR has_purchase = 1 THEN 1 ELSE 0 END) FILTER (WHERE has_search = 1), 1) AS ok,
                 SUM(has_search) AS n FROM session_summary""")
regret = q("""WITH r AS (SELECT client_id, sku, MIN(ts) rts FROM remove_from_cart GROUP BY 1, 2)
              SELECT ROUND(100 * AVG(CASE WHEN r.rts >= c.first_cart_ts AND r.rts - c.first_cart_ts <= INTERVAL 10 MINUTE
                                          THEN 1 ELSE 0 END), 1) AS v FROM cart_items c LEFT JOIN r USING (client_id, sku)""").v[0]
R["heart"] = {
    "happiness": {"metric": "proxy: unsuccessful search sessions (search, but nothing carted or bought)",
                  "search_sessions": int(hp.n[0]), "search_success_pct": float(hp.ok[0]),
                  "unsuccessful_search_pct": round(100 - float(hp.ok[0]), 1), "cart_regret_10min_pct": float(regret)},
    "engagement": {"metric": "median sessions per user / median searches per session",
                   "sessions_median": float(us.sessions.median()), "searches_per_session_median": round(float(us.searches_per_session.median()), 2)},
    "adoption": {"metric": "proxy: share of purchasers who used the cart and search features",
                 "cart_pct": R["journey_stage_pct"]["cart_add"], "search_pct": R["journey_stage_pct"]["search"]},
    "retention": {"metric": "month-1 repeat purchase (Jul-Oct cohorts)", "value_pct": R["cohort_month1_repeat_avg_pct"],
                  "repeat_buyer_share_pct": round(100 * float((us.purchase_freq >= 2).mean()), 1)},
    "task_success": {"metric": "cart-to-purchase rate", "value_pct": fate["purchased_pct"]}}

# ------------------------------------------------------------- 9. RICE (judgement-based scores)
rice = pd.DataFrame([
    ("Comparison tool for heavy searchers", "Help me compare options quickly so I can decide with confidence", 8, 8, 7, 5),
    ("Reminders for items left in the cart", "Remind me about items I was seriously considering", 6, 7, 6, 3),
    ("Better product info in high-abandon categories", "Give me what I need to decide without leaving the cart", 5, 8, 6, 6),
    ("Personalised recommendations before cart-add", "Show me relevant options without extensive searching", 9, 6, 5, 7)],
    columns=["intervention", "job_to_be_done", "reach", "impact", "confidence", "effort"])
rice["rice_score"] = (rice.reach * rice.impact * rice.confidence / rice.effort).round(1)
rice = rice.sort_values("rice_score", ascending=False)
rice.to_csv(TAB / "rice.csv", index=False)
R["rice"] = rice.to_dict("records")

(OUT / "results.json").write_text(json.dumps(R, indent=2, default=str))
h, s = R["headline"]["searches"], R["stress_test"]
print(f"""Results written to outputs/results.json and outputs/tables/
  cart abandonment          {fate['abandonment_pct']}%  (removed {fate['removed_pct']}, unresolved {fate['unresolved_pct']})
  headline search ratio     {h['ratio_of_means']}x  (Welch t = {h['welch_t']}, p = {h['welch_p']:.1e})
  like-for-like ratio       {s['searches']['ratio_of_means']}x total searches, {s['searches_per_session']['ratio_of_means']}x per session
  replaced within category  {R['substitution']['all']['same_category_7d_pct']}% of abandoned items within 7 days
  price correlation         {R['corr_price_abandonment']}
  categories                {R['categories']['min']}% to {R['categories']['max']}% (IQR {R['categories']['p25']}-{R['categories']['p75']})
  HEART proxies             {R['heart']['happiness']['unsuccessful_search_pct']}% of search sessions unsuccessful, cart used by {R['heart']['adoption']['cart_pct']}%""")
