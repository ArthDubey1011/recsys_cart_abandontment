/* =====================================================================
   E-Commerce Behavioral Analytics: Cart Abandonment & User Journey
   SQL pipeline (DuckDB)

   Data    : client-level sample of the Synerise RecSys Challenge 2025
             dataset, stored as data/*_sample.parquet
   Run     : from the repository root,
             duckdb recsys.duckdb < sql/ecommerce_behavioral_analysis.sql
             (or: python src/01_build_tables.py)

   Sections
     1. Load the event tables
     2. Data overview
     3. User journey: stage coverage and event transitions
     4. Cart outcomes (the cart-level funnel)
     5. Purchase cohorts
     6. User features and segments
     7. Sessions (30-minute inactivity rule)
     8. Price: purchase rate by price quartile
     9. Category abandonment
    10. Substitution: was an abandoned item replaced by a same-category purchase?
    11. HEART proxies for Happiness and Adoption

   Expected outputs are noted under each query.
   ===================================================================== */


/* ---------------------------------------------------------------------
   1. Load the event tables (timestamps arrive as text)
   --------------------------------------------------------------------- */
CREATE OR REPLACE TABLE product_buy AS
SELECT client_id, CAST(timestamp AS TIMESTAMP) AS ts, sku FROM read_parquet('data/product_buy_sample.parquet');

CREATE OR REPLACE TABLE add_to_cart AS
SELECT client_id, CAST(timestamp AS TIMESTAMP) AS ts, sku FROM read_parquet('data/add_to_cart_sample.parquet');

CREATE OR REPLACE TABLE remove_from_cart AS
SELECT client_id, CAST(timestamp AS TIMESTAMP) AS ts, sku FROM read_parquet('data/remove_from_cart_sample.parquet');

CREATE OR REPLACE TABLE page_visit AS
SELECT client_id, CAST(timestamp AS TIMESTAMP) AS ts, url FROM read_parquet('data/page_visit_sample.parquet');

CREATE OR REPLACE TABLE search_query AS
SELECT client_id, CAST(timestamp AS TIMESTAMP) AS ts FROM read_parquet('data/search_query_sample.parquet');

-- price is an anonymised bucket (0-99), category is an anonymised ID
CREATE OR REPLACE TABLE product_properties AS
SELECT sku, category, price AS price_bucket FROM read_parquet('data/product_properties_sample.parquet');

-- one long table of every event, used for journeys and sessions
CREATE OR REPLACE TABLE all_events AS
SELECT client_id, ts, 'visit'       AS event FROM page_visit
UNION ALL SELECT client_id, ts, 'search'      FROM search_query
UNION ALL SELECT client_id, ts, 'cart_add'    FROM add_to_cart
UNION ALL SELECT client_id, ts, 'cart_remove' FROM remove_from_cart
UNION ALL SELECT client_id, ts, 'purchase'    FROM product_buy;


/* ---------------------------------------------------------------------
   2. Data overview
   --------------------------------------------------------------------- */
SELECT event,
       COUNT(*)                  AS events,
       COUNT(DISTINCT client_id) AS users,
       MIN(ts)::DATE             AS first_day,
       MAX(ts)::DATE             AS last_day
FROM all_events
GROUP BY event
ORDER BY events DESC;
-- Expected: visit 6,853,213 | search 922,717 | cart_add 635,890 | purchase 335,771 |
--           cart_remove 296,719  (9,044,310 events, 46,673 users, 23 Jun - 8 Dec 2022)
-- The sample was drawn from purchasers, so every user bought at least once.


/* ---------------------------------------------------------------------
   3. User journey
   --------------------------------------------------------------------- */
-- 3a. Share of users who ever reach each stage
SELECT ROUND(100 * AVG(CASE WHEN v.client_id IS NOT NULL THEN 1 ELSE 0 END), 1) AS pct_visited,
       ROUND(100 * AVG(CASE WHEN s.client_id IS NOT NULL THEN 1 ELSE 0 END), 1) AS pct_searched,
       ROUND(100 * AVG(CASE WHEN c.client_id IS NOT NULL THEN 1 ELSE 0 END), 1) AS pct_carted,
       ROUND(100 * AVG(CASE WHEN r.client_id IS NOT NULL THEN 1 ELSE 0 END), 1) AS pct_removed,
       100.0                                                                     AS pct_purchased
FROM (SELECT DISTINCT client_id FROM product_buy) u
LEFT JOIN (SELECT DISTINCT client_id FROM page_visit)       v USING (client_id)
LEFT JOIN (SELECT DISTINCT client_id FROM search_query)     s USING (client_id)
LEFT JOIN (SELECT DISTINCT client_id FROM add_to_cart)      c USING (client_id)
LEFT JOIN (SELECT DISTINCT client_id FROM remove_from_cart) r USING (client_id);
-- Expected: visited 77.7 | searched 52.1 | carted 73.5 | removed 48.5 | purchased 100
-- A visit -> search -> cart -> purchase conversion funnel is not meaningful here:
-- purchase is 100% by construction and many users skip stages.

-- 3b. Journey map: what each event is followed by (row-normalised transition matrix)
CREATE OR REPLACE TABLE transitions AS
WITH ordered AS (
    SELECT client_id, event,
           LEAD(event) OVER (PARTITION BY client_id ORDER BY ts, event) AS next_event
    FROM all_events
)
SELECT event, next_event, COUNT(*) AS n,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY event), 1) AS pct_of_row
FROM ordered
WHERE next_event IS NOT NULL
GROUP BY event, next_event;

SELECT * FROM transitions ORDER BY event, pct_of_row DESC;
-- Expected highlights: after a cart_add the next event is a visit 59.0% of the time,
-- another cart_add 21.6%, a search 8.5%, a removal 7.7% and a purchase only 3.2%.

-- 3c. How many purchases went through the cart first?
SELECT ROUND(100 * AVG(CASE WHEN EXISTS (
           SELECT 1 FROM add_to_cart c
           WHERE c.client_id = b.client_id AND c.sku = b.sku AND c.ts <= b.ts) THEN 1 ELSE 0 END), 1)
       AS pct_purchases_after_cart_add
FROM product_buy b;
-- Expected: 77.3


/* ---------------------------------------------------------------------
   4. Cart outcomes: one row per (user, SKU) that was ever carted
   --------------------------------------------------------------------- */
-- De-duplicating to (client_id, sku) BEFORE joining avoids the join fan-out
-- that originally inflated rows about 7x and produced a false 100% purchase rate.
CREATE OR REPLACE TABLE cart_items AS
WITH carted AS (
    SELECT client_id, sku, MIN(ts) AS first_cart_ts, COUNT(*) AS times_carted
    FROM add_to_cart GROUP BY client_id, sku
),
bought AS (
    SELECT client_id, sku, MIN(ts) AS first_buy_ts
    FROM product_buy GROUP BY client_id, sku
),
removed AS (
    SELECT DISTINCT client_id, sku FROM remove_from_cart
)
SELECT c.client_id, c.sku, c.first_cart_ts, c.times_carted, b.first_buy_ts,
       b.sku IS NOT NULL                        AS was_purchased,
       b.sku IS NULL AND r.sku IS NOT NULL      AS was_removed,
       b.sku IS NULL AND r.sku IS NULL          AS unresolved,
       p.price_bucket, p.category
FROM carted c
LEFT JOIN bought  b USING (client_id, sku)
LEFT JOIN removed r USING (client_id, sku)
LEFT JOIN product_properties p USING (sku);
-- Expected: 450,463 rows

SELECT COUNT(*)                                          AS cart_items,
       ROUND(100 * AVG(was_purchased::INT), 1)           AS pct_purchased,
       ROUND(100 * AVG(was_removed::INT), 1)             AS pct_removed,
       ROUND(100 * AVG(unresolved::INT), 1)              AS pct_unresolved,
       ROUND(100 * (1 - AVG(was_purchased::INT)), 1)     AS abandonment_rate
FROM cart_items;
-- Expected: 450,463 | purchased 43.3 | removed 40.5 | unresolved 16.2 | abandonment 56.7

-- Right-censoring check: items carted near the end of the window have had little
-- time to resolve. Excluding the last 14 days barely moves the headline.
SELECT ROUND(100 * (1 - AVG(was_purchased::INT)), 1) AS abandonment_excl_last_14d,
       ROUND(100 * AVG(unresolved::INT), 1)          AS unresolved_excl_last_14d
FROM cart_items
WHERE first_cart_ts < TIMESTAMP '2022-11-24';
-- Expected: 56.2 | 14.5

-- Time from first cart-add to purchase, for items that were bought
SELECT ROUND(QUANTILE_CONT(EPOCH(first_buy_ts - first_cart_ts) / 3600, 0.50), 1) AS median_hours,
       ROUND(QUANTILE_CONT(EPOCH(first_buy_ts - first_cart_ts) / 3600, 0.75), 1) AS p75_hours,
       ROUND(QUANTILE_CONT(EPOCH(first_buy_ts - first_cart_ts) / 3600, 0.90), 1) AS p90_hours
FROM cart_items
WHERE was_purchased AND first_buy_ts >= first_cart_ts;
-- Expected: 0.3 | 4.7 | 72.1  (two-thirds of carted items that sell, sell within an hour)


/* ---------------------------------------------------------------------
   5. Purchase cohorts (by month of first purchase in the window)
   --------------------------------------------------------------------- */
CREATE OR REPLACE TABLE cohort_retention AS
WITH first_purchase AS (
    SELECT client_id, DATE_TRUNC('month', MIN(ts)) AS cohort_month
    FROM product_buy GROUP BY client_id
),
active AS (
    SELECT DISTINCT client_id, DATE_TRUNC('month', ts) AS active_month FROM product_buy
)
SELECT f.cohort_month,
       DATE_DIFF('month', f.cohort_month, a.active_month)                       AS months_since_first,
       COUNT(DISTINCT a.client_id)                                              AS active_users,
       ROUND(100.0 * COUNT(DISTINCT a.client_id)
             / MAX(COUNT(DISTINCT a.client_id)) OVER (PARTITION BY f.cohort_month), 1) AS pct_retained
FROM active a
JOIN first_purchase f USING (client_id)
GROUP BY f.cohort_month, months_since_first;

SELECT * FROM cohort_retention ORDER BY cohort_month, months_since_first;
-- Expected: month-1 repeat purchase of 25-29% for the Jul-Oct cohorts, then flat.
-- The last observed month of each cohort is December, which only has 8 days of data.

-- Cart abandonment by cohort: stable, so tenure does not explain abandonment
WITH first_purchase AS (
    SELECT client_id, DATE_TRUNC('month', MIN(ts)) AS cohort_month FROM product_buy GROUP BY client_id
)
SELECT cohort_month, COUNT(*) AS cart_items,
       ROUND(100 * (1 - AVG(was_purchased::INT)), 1) AS abandonment_rate
FROM cart_items JOIN first_purchase USING (client_id)
GROUP BY cohort_month ORDER BY cohort_month;
-- Expected: 51.8% to 58.9%


/* ---------------------------------------------------------------------
   6. User features and segments
   --------------------------------------------------------------------- */
CREATE OR REPLACE TABLE user_features AS
WITH purchase_stats AS (
    SELECT client_id, COUNT(*) AS purchase_freq, MIN(ts) AS first_purchase, MAX(ts) AS last_purchase
    FROM product_buy GROUP BY client_id
),
cart_stats    AS (SELECT client_id, COUNT(*) AS cart_adds, COUNT(DISTINCT sku) AS distinct_skus_carted
                  FROM add_to_cart GROUP BY client_id),
removal_stats AS (SELECT client_id, COUNT(*) AS removals FROM remove_from_cart GROUP BY client_id),
visit_stats   AS (SELECT client_id, COUNT(*) AS visits   FROM page_visit       GROUP BY client_id),
search_stats  AS (SELECT client_id, COUNT(*) AS searches FROM search_query     GROUP BY client_id)
SELECT p.client_id, p.purchase_freq, p.first_purchase, p.last_purchase,
       DATE_DIFF('day', p.first_purchase, p.last_purchase)               AS purchase_span_days,
       COALESCE(c.cart_adds, 0)                                          AS cart_adds,
       COALESCE(c.distinct_skus_carted, 0)                               AS distinct_skus_carted,
       COALESCE(r.removals, 0)                                           AS removals,
       COALESCE(v.visits, 0)                                             AS visits,
       COALESCE(s.searches, 0)                                           AS searches,
       CASE WHEN c.cart_adds > 0 THEN COALESCE(r.removals, 0) * 1.0 / c.cart_adds ELSE 0 END AS removal_rate
FROM purchase_stats p
LEFT JOIN cart_stats    c USING (client_id)
LEFT JOIN removal_stats r USING (client_id)
LEFT JOIN visit_stats   v USING (client_id)
LEFT JOIN search_stats  s USING (client_id);
-- Expected: 46,673 users

CREATE OR REPLACE TABLE user_segments AS
SELECT *,
       CASE WHEN removal_rate >= 0.5 THEN 'high_abandon'
            WHEN removal_rate > 0    THEN 'moderate_abandon'
            ELSE 'low_abandon' END                                  AS abandon_segment,
       CASE WHEN purchase_freq >= 5 THEN 'high_frequency'
            WHEN purchase_freq >= 2 THEN 'repeat'
            ELSE 'one_time' END                                     AS frequency_segment,
       NTILE(4) OVER (ORDER BY purchase_freq)                       AS frequency_quartile
FROM user_features;

SELECT abandon_segment,
       COUNT(*)                                                     AS users,
       ROUND(AVG(searches), 1)                                      AS avg_searches,
       ROUND(AVG(visits), 1)                                        AS avg_visits,
       ROUND(AVG(cart_adds), 1)                                     AS avg_cart_adds,
       ROUND(100 * AVG(CASE WHEN cart_adds = 0 THEN 1 ELSE 0 END), 1) AS pct_never_carted
FROM user_segments
GROUP BY abandon_segment
ORDER BY users DESC;
-- Expected:
-- low_abandon      24,355 users | 2.1 searches  | 26.7 visits  | 50.7% never used the cart
-- moderate_abandon 12,038 users
-- high_abandon     10,280 users | 39.7 searches | 276.8 visits
-- Note: removal_rate defaults to 0 for users with no cart-adds, so half of the
-- "low_abandon" group never carted anything. See the stress test in src/02_analysis.py.


/* ---------------------------------------------------------------------
   7. Sessions: a new session starts after 30 minutes of inactivity
   --------------------------------------------------------------------- */
CREATE OR REPLACE TABLE user_sessions AS
WITH ordered AS (
    SELECT client_id, ts, LAG(ts) OVER (PARTITION BY client_id ORDER BY ts) AS prev_ts
    FROM all_events
)
SELECT client_id,
       SUM(CASE WHEN prev_ts IS NULL OR ts - prev_ts > INTERVAL 30 MINUTE THEN 1 ELSE 0 END) AS sessions
FROM ordered
GROUP BY client_id;
-- Expected: 46,673 rows


/* ---------------------------------------------------------------------
   8. Price: purchase rate by price quartile
   --------------------------------------------------------------------- */
WITH tiered AS (
    SELECT *, NTILE(4) OVER (ORDER BY price_bucket) AS price_quartile FROM cart_items
)
SELECT price_quartile,
       COUNT(*)                                   AS cart_items,
       MIN(price_bucket) || '-' || MAX(price_bucket) AS bucket_range,
       ROUND(100 * AVG(was_purchased::INT), 1)    AS pct_purchased
FROM tiered
GROUP BY price_quartile
ORDER BY price_quartile;
-- Expected: 45.3 | 42.7 | 43.0 | 42.3  (flat)

SELECT ROUND(CORR(price_bucket, 1 - was_purchased::INT), 3) AS corr_price_abandonment
FROM cart_items;
-- Expected: 0.030


/* ---------------------------------------------------------------------
   9. Category abandonment (categories with at least 200 cart items)
   --------------------------------------------------------------------- */
CREATE OR REPLACE TABLE category_abandonment AS
SELECT category, COUNT(*) AS cart_items,
       ROUND(100 * (1 - AVG(was_purchased::INT)), 1) AS abandonment_rate
FROM cart_items
GROUP BY category
HAVING COUNT(*) >= 200;

SELECT COUNT(*)                                         AS categories,
       MIN(abandonment_rate)                            AS min_rate,
       QUANTILE_CONT(abandonment_rate, 0.25)            AS p25,
       QUANTILE_CONT(abandonment_rate, 0.50)            AS median_rate,
       QUANTILE_CONT(abandonment_rate, 0.75)            AS p75,
       MAX(abandonment_rate)                            AS max_rate
FROM category_abandonment;
-- Expected: 465 categories | 28.5 | 51.6 | 57.2 | 61.9 | 85.2
-- The ~3x spread is between the extremes, half of all categories sit within 10 points.


/* ---------------------------------------------------------------------
  10. Substitution: after abandoning an item, did the user buy a different
      SKU from the same category within 7 days?
   --------------------------------------------------------------------- */
WITH abandoned AS (
    SELECT ci.*, u.abandon_segment
    FROM cart_items ci JOIN user_segments u USING (client_id)
    WHERE NOT ci.was_purchased
),
buys AS (
    SELECT b.client_id, b.sku, b.ts, p.category
    FROM product_buy b JOIN product_properties p USING (sku)
)
SELECT COALESCE(abandon_segment, 'All abandoned items')          AS scope,
       COUNT(*)                                                   AS abandoned_items,
       ROUND(100 * AVG(CASE WHEN EXISTS (
                SELECT 1 FROM buys x
                WHERE x.client_id = a.client_id AND x.category = a.category AND x.sku <> a.sku
                  AND x.ts BETWEEN a.first_cart_ts AND a.first_cart_ts + INTERVAL 7 DAY)
           THEN 1 ELSE 0 END), 1)                                 AS pct_replaced_same_category_7d
FROM abandoned a
GROUP BY ROLLUP (abandon_segment)
ORDER BY scope;
-- Expected: all 21.0 | high_abandon 20.2 | moderate_abandon 22.6 | low_abandon 12.5


/* ---------------------------------------------------------------------
  11. HEART proxies (the data has no surveys and no feature launch)
   --------------------------------------------------------------------- */
-- Happiness proxy (frustration signal): of sessions that include a search,
-- how many end without anything carted or bought?
CREATE OR REPLACE TABLE session_summary AS
WITH ordered AS (
    SELECT client_id, ts, event,
           LAG(ts) OVER (PARTITION BY client_id ORDER BY ts, event) AS prev_ts
    FROM all_events
),
numbered AS (
    SELECT *,
           SUM(CASE WHEN prev_ts IS NULL OR ts - prev_ts > INTERVAL 30 MINUTE THEN 1 ELSE 0 END)
               OVER (PARTITION BY client_id ORDER BY ts, event ROWS UNBOUNDED PRECEDING) AS session_id
    FROM ordered
)
SELECT client_id, session_id,
       MAX((event = 'search')::INT)   AS has_search,
       MAX((event = 'cart_add')::INT) AS has_cart_add,
       MAX((event = 'purchase')::INT) AS has_purchase
FROM numbered
GROUP BY client_id, session_id;

SELECT COUNT(*)                                                             AS sessions,
       SUM(has_search)                                                      AS search_sessions,
       ROUND(100 * AVG(CASE WHEN has_cart_add = 1 OR has_purchase = 1 THEN 1 ELSE 0 END)
             FILTER (WHERE has_search = 1), 1)                              AS search_success_pct,
       ROUND(100 - 100 * AVG(CASE WHEN has_cart_add = 1 OR has_purchase = 1 THEN 1 ELSE 0 END)
             FILTER (WHERE has_search = 1), 1)                              AS unsuccessful_search_pct
FROM session_summary;
-- Expected: 837,339 sessions | 200,587 with a search | 46.5% succeed | 53.5% end with nothing carted or bought

-- Second happiness proxy ("cart regret"): items removed within 10 minutes of being carted
WITH first_removal AS (SELECT client_id, sku, MIN(ts) AS removed_ts FROM remove_from_cart GROUP BY client_id, sku)
SELECT ROUND(100 * AVG(CASE WHEN r.removed_ts >= c.first_cart_ts
                              AND r.removed_ts - c.first_cart_ts <= INTERVAL 10 MINUTE THEN 1 ELSE 0 END), 1) AS pct_removed_within_10min
FROM cart_items c LEFT JOIN first_removal r USING (client_id, sku);
-- Expected: 13.0

-- Adoption proxy: share of purchasers who have ever used the cart and search features
SELECT ROUND(100 * AVG(CASE WHEN c.client_id IS NOT NULL THEN 1 ELSE 0 END), 1) AS cart_adoption_pct,
       ROUND(100 * AVG(CASE WHEN s.client_id IS NOT NULL THEN 1 ELSE 0 END), 1) AS search_adoption_pct
FROM (SELECT DISTINCT client_id FROM product_buy) u
LEFT JOIN (SELECT DISTINCT client_id FROM add_to_cart)  c USING (client_id)
LEFT JOIN (SELECT DISTINCT client_id FROM search_query) s USING (client_id);
-- Expected: 73.5 | 52.1
