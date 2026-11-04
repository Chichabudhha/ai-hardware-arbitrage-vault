# Deal Engine

## Landed cost

```text
landed_cost = purchase_price
            + source_local_shipping
            + international_shipping
            + intermediary_fee
            + payment_fees
            + customs
            + import_taxes
            + broker/handling
            + insurance
            + testing/repair allowance
            + other_defined_costs
```

Unknown mandatory cost => `INSUFFICIENT_DATA` for BUY.

D-010: EU sourcing runs through an intermediary charging a flat 15 EUR per card.
Imports carry that fee from policy unless the deal was quoted a different one.
Domestic buys have no intermediary and carry 0 as a stated fact, not as a
substitute for UNKNOWN.

## Profit

```text
expected_profit = expected_sale_price - landed_cost - resale_fees - expected_repair_reserve
roi = expected_profit / landed_cost
```

Use Decimal.

## Three scores

Formulas approved in D-023 (`src/deal_engine/scores.py`). Scores are advisory:
none of them changes the verdict.

### Deal Score
Measures economic attractiveness, 0–100 relative to D-009:
`clamp(50 × min(ROI / 18%, profit / 50 EUR), 0, 100)`, rounded to an integer.
50 = exactly at the BUY thresholds, 100 = twice both. UNKNOWN when profit/ROI
are unknown.

### Confidence Score
`min(pricing_confidence, product_match.confidence)` — weakest link, no
weights. Mandatory costs are complete by construction (else INSUFFICIENT_DATA).

### Risk Score
Existing `risk_level` (Low/Medium/High) from `src/deal_engine/risk.py`.

### Liquidity (D-023)
Proxy `liquidity_sample_listings` = Serbian sample size after exclusions.
`liquidity_sell_through` is UNKNOWN until Serbian SOLD/DELISTED outcomes exist.

### Resale friction (D-023)
`Policy.resale_friction_eur` is UNKNOWN (None): profit excludes it and the
opportunity lists `unpriced_costs: ["resale_friction"]`. Once approved, it is
subtracted from profit (not added to landed cost).

## Initial policy

Thresholds are owner decisions and live in `src/core/policy.py` (`OWNER_POLICY`),
never inline in the calculator. Approved values (D-008, D-009):

| Parameter | Value |
|---|---|
| capital | 1000 EUR |
| max purchase per card | 500 EUR |
| min profit for BUY | 50 EUR |
| min ROI for BUY | 18% |
| min ROI for NEGOTIATE | 9% |
| min ROI for WATCH | 4% |
| EU intermediary fee | 15 EUR flat per card |

A BUY candidate requires:
- expected_profit >= min profit **and** ROI >= min ROI (both, not either)
- purchase price within the per-purchase cap; above it the ceiling is NEGOTIATE
- no unresolved mandatory landed-cost item
- risk below configured maximum

Changing any value requires a new entry in `odluke/`.

## Verdicts

- BUY: meets policy.
- NEGOTIATE: potentially good if purchase price is reduced to target price.
- WATCH: promising but data/price/liquidity insufficient.
- SKIP: fails economics or risk policy.

## Target price

Calculate maximum purchase price that preserves configured minimum profit and ROI.

```text
max_purchase_price = function(expected_sale, all_non_purchase_costs, min_profit, min_roi)
```

Exact formula and tests belong in implementation.
