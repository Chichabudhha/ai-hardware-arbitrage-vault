# Data Model

## Core entities

### marketplace
`id, name, country, region, access_method, automation_status, terms_url, notes`

### listing
`id, marketplace_id, source_listing_id, url, title, description, seller_id, location, first_seen_at, last_seen_at, current_status`

### listing_observation
`id, listing_id, observed_at, price_amount, currency, price_type, raw_payload_hash, raw_payload_ref`

### seller
`id, marketplace_id, source_seller_id, name, seller_type, rating, rating_count, first_seen_at, last_seen_at`

### product
`id, category, manufacturer, family, model, variant, vram_gb, architecture, canonical_name, ai_relevance_score`

### product_match
`listing_id, product_id, confidence, method, matched_at, conflict_status`

### market_observation
`id, product_id, market_country, source, observation_type, price_amount, currency, condition, observed_at, provenance_ref`

`observation_type`: asking | sold | completed | dealer_reference | manual_reference

### fx_observation
`base_currency, quote_currency, rate, observed_at, source`

### cost_rule
`route, cost_type, rule_version, formula/config, effective_from, effective_to, source, confidence`

### opportunity
`id, listing_id, product_id, source_market, resale_market, created_at, expected_sale, landed_cost, expected_profit, roi, deal_score, confidence_score, risk_score, verdict`

### transaction
`id, opportunity_id, purchase_date, purchase_cost, landed_cost_actual, sale_date, sale_price_actual, fees_actual, profit_actual, roi_actual, outcome`

## Rules

- Original currency and original amount are always retained.
- EUR normalized values are derived fields.
- Never overwrite raw observations.
- Every derived price has calculation version and input references.
- Financial fields use Decimal, never binary floating point.
