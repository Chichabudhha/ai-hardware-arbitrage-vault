# Serbian Pricing Engine

## Objective

Estimate the realistic resale price in Serbia for a specific canonical product/variant.

## Inputs

- Serbian asking observations
- sold/completed observations when available
- exact product/variant
- condition
- warranty
- listing freshness
- source quality
- liquidity indicators

## Outputs

- `resale_conservative`
- `resale_expected`
- `resale_optimistic`
- `confidence`
- `sample_size`
- `calculation_version`

## Baseline

Use robust statistics, not a single listing. Initial baseline: filtered P25 / median / P75. Outliers must be explicitly excluded by rule and logged.

Implemented in `src/pricing/serbian_market.py` (`pricing-v1`).

### Which percentile becomes `resale_expected`

| Basis | `resale_expected` | Why |
|---|---|---|
| SOLD | median | Realized prices; the middle of the distribution is the honest centre. |
| MIXED | P25 | One asking price contaminates the sample; stay conservative. |
| ASKING | P25 | Asking sits above realized by a margin nobody here has measured. |

Applying a fixed asking-to-sold discount would be an invented number
(principle 1). P25 is an **observed** value at the low end of the actual
distribution, so the conservatism comes from data, not from a guess. When sold
observations become available, the median of those takes over.

### Exclusion rules, in order

1. `different_product` — not the requested canonical product.
2. `unsupported_currency:<CUR>` — anything outside RSD/EUR would need converting,
   and a converted price is derived, not observed (D-013).
3. `currency_not_sample:<CUR>` — valid currency, wrong one for this sample. The
   sample currency is the one the product has most observations in, EUR on a
   tie; a percentile spanning two currencies is arithmetic on unlike units.
4. `bundle_price_is_not_a_gpu_price`.
5. `for_parts`.
6. `condition_mismatch:<condition>` — used and new are never mixed.
7. `non_positive_price`.
8. `stale_over_90_days`.
9. `outlier_below_iqr_fence` / `outlier_above_iqr_fence` — Tukey 1.5x IQR.

Every exclusion is returned in `excluded` with the listing id, the price and the
rule that dropped it. Nothing disappears silently.

### Confidence

Deterministic, in [0, 1]:

```text
base       SOLD 0.80 | MIXED 0.65 | ASKING 0.50
+ size     up to +0.15, linear to a sample of 20
- spread   up to -0.20, linear in (P75-P25)/median
- age      up to -0.10, linear in median observation age over the 90-day window
```

### Sample floor

Fewer than 5 surviving observations produces `INSUFFICIENT_DATA` with
`missing_inputs`, and **no** percentile fields at all — not zeros, not a number
with a caveat.

### Parameters

`PricingRules` in `src/pricing/serbian_market.py`. These are statistical
choices, not owner money policy: 1.5x IQR is the standard Tukey fence, the
90-day window matches how fast the used GPU market moves, and the sample floor
of 5 is the point below which quartiles stop meaning anything. They are not
decisions in `odluke/` — unlike the thresholds in `src/core/policy.py`.

## Observation store

`src/pricing/observations.py` reads and appends JSONL. Append-only: a new price
for a listing is a new line (principle 6). A malformed line raises rather than
being skipped, because a silently dropped observation shifts every percentile
that depended on it.

## Rules

- Exact model/variant preferred over family-level matches.
- Used vs new separated.
- Bundle prices are not GPU prices unless component value is explicitly estimated.
- Asking-only datasets receive lower confidence than sold/completed datasets.
- Stale observations receive lower weight.
- If sample is insufficient: `INSUFFICIENT_DATA`.

## Serbian market is authoritative for resale

EU prices are not used as the final resale price. They are sourcing/benchmark data only.

### Valuta procene (D-013)

Srpski GPU oglasi se kotiraju i u evrima i u dinarima. Obe valute su validne
srpske opservacije; meša se nikad. Procena nosi `currency`, a
`Opportunity.expected_sale_rsd` ostaje prazno kad je procena u evrima — jer
konvertovan iznos nije posmatran. EUR/RSD kurs se traži samo kad je nešto u
poslu stvarno u dinarima.
