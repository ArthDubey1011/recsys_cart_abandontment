# Analysis notes: definitions, pitfalls and decisions

## Definitions
- **Cart item**: a distinct (user, SKU) pair that was added to a cart at least once. 450,463 in total.
- **Outcome** of a cart item: *purchased* if the user bought that SKU; *removed* if not bought but removed; *unresolved* otherwise.
- **Abandonment rate** = (removed + unresolved) / cart items = 1 − purchase rate. **56.7%**.
- **Removal rate** (per user) = removals / cart additions; defaults to 0 for users with no cart additions.
- **Segments**: high abandon (removal rate ≥ 0.5), moderate (0 < rate < 0.5), low (rate = 0). Frequency: one-time, repeat (2–4 purchases), high-frequency (5+).
- **Session**: a new session starts after 30 minutes without any event.
- **Cohort**: month of a user's first purchase in the window.
- **Substitution**: an abandoned item is "replaced" if the same user bought a different SKU from the same category within 7 days of first carting it.
- **HEART proxies**: Happiness = search success, the share of sessions containing a search that end with a cart-add or purchase (46.5%, so 53.5% fail), plus "cart regret", items removed within 10 minutes of being carted (13.0%). Adoption = share of purchasers who ever used the cart (73.5%) and search (52.1%). These are behavioural proxies, not direct measures of satisfaction or uptake of a new feature.

## Pitfall 1: sampling bias broke the funnel
The sample was built by drawing users from `product_buy` and keeping all their events. Every user therefore purchased. The first funnel attempt (visit → search → cart → purchase) showed 100% purchase and stage-to-stage "conversion" above 100%, because many users skip stages (e.g. buy without a logged search). A conversion funnel isn't meaningful on this sample, so the analysis measures what it can: the fate of each cart item, and how purchasers move between event types.

## Pitfall 2: join fan-out
Joining raw `add_to_cart`, `product_buy` and `remove_from_cart` on (user, SKU) multiplies rows whenever a user carts or buys the same SKU more than once. In one version this produced ~7× the real number of rows (747,640 vs 450,463 cart items) and an impossible 100% purchase rate in one price quartile. Fix: de-duplicate each table to one row per (user, SKU) *before* joining (see `cart_items` in the SQL).

## Pitfall 3: the low-abandon group hid non-cart users
Because removal rate defaults to 0 without cart-adds, 50.7% of the "low abandon" segment never used the cart. The headline comparison (high-abandon users search 18.9× more) therefore largely compares cart users with non-cart users. Evidence: the moderate and high segments search almost identically (38.5 vs 39.7).

Stress test (users with ≥ 3 cart-adds; high removal ≥ 0.5 vs low < 0.2):

| Measure | High | Low | Ratio |
|---|---|---|---|
| Searches (total) | 47.9 | 20.7 | 2.32× |
| Sessions | 36.3 | 21.3 | 1.71× |
| Cart additions | 34.6 | 13.7 | 2.53× |
| Searches per session | 1.36 | 1.28 | 1.07× (median 0.75 vs 0.50) |

Reading: heavy abandoners are mostly heavy users, with a modest lean towards searching. The more direct evidence of comparison shopping is the substitution test: 21% of abandoned items are followed by a same-category purchase within 7 days.

## Other checks
- **Right-censoring**: items carted in the last 14 days are over-represented among unresolved items; excluding them gives 56.2% abandonment (vs 56.7%).
- **Price**: purchase rate by price quartile is 45.3 / 42.7 / 43.0 / 42.3%; correlation 0.03; chi-square is significant only because n = 450,463 (Cramér's V = 0.024).
- **Categories**: 465 categories with ≥ 200 cart items range from 28.5% to 85.2%, but the middle half sit in 51.6–61.9%.
- **June cohort** includes customers whose real first purchase predates the window (it starts 23 June), which inflates its retention. December has only 8 days of data.

## RICE scores
Reach, Impact, Confidence and Effort are judgement-based 1–10 estimates informed by the analysis, not measured values. The top two (comparison tool 89.6, cart reminders 84.0) are close; reminders are cheaper, which is why the recommendation is to ship them first and A/B test the comparison tool.
