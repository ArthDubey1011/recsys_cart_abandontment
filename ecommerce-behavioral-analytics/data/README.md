# Data

**Source:** [Synerise RecSys Challenge 2025](https://github.com/Synerise/recsys2025), anonymised real-world e-commerce interaction logs. Download the dataset via the link in the challenge repository (about 1.9 GB compressed).

The data isn't committed here; the dataset remains under Synerise's terms.

## The sample used in this project

The full dataset is too large to work with comfortably on a laptop, so the analysis uses a **client-level sample**: users drawn from the purchase log, with *every* event for those users kept so that complete journeys stay intact. `scripts/sample_recsys.py` builds it.

Place these six files in this folder:

| File | Rows | Users |
|---|---|---|
| `page_visit_sample.parquet` | 6,853,213 | 36,272 |
| `search_query_sample.parquet` | 922,717 | 24,305 |
| `add_to_cart_sample.parquet` | 635,890 | 34,325 |
| `product_buy_sample.parquet` | 335,771 | 46,673 |
| `remove_from_cart_sample.parquet` | 296,719 | 22,628 |
| `product_properties_sample.parquet` | 282,022 SKUs | — |

**Important:** because users were sampled from purchasers, every user bought at least once. The original sample was drawn without a fixed random seed, so rebuilding it gives very close but not identical numbers; `sample_recsys.py` now uses a fixed seed for future runs.

**Fields:** `client_id`, `timestamp`, `sku` / `url` / `query` (query text is a numerical embedding). `product_properties` gives each SKU an anonymised `category` ID and a `price` bucket (0–99).
