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

### Deal Score
Measures economic attractiveness.

### Confidence Score
Measures quality/completeness of product, market and cost data.

### Risk Score
Measures seller, condition, import, liquidity and data risks.

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
