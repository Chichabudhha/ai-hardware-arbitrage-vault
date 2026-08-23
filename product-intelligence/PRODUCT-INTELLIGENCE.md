# Product Intelligence

## MVP

Canonical NVIDIA GPU catalog:
- RTX 3090 24GB
- RTX 3090 Ti 24GB
- RTX 3080 Ti 12GB
- RTX 4090 24GB
- RTX A4000 16GB
- RTX A5000 24GB
- RTX A6000 48GB
- RTX 4080 Super 16GB (D-011)
- RTX 4070 Ti Super 16GB (D-011)

Plain RTX 4080 and plain RTX 4070 Ti are deliberately absent — the matcher
leaves them UNMATCHED rather than folding them into the Super variant.

Tesla V100 and A100 were considered and rejected in D-011: the Serbian resale
market for datacenter cards is too thin to price.

Expand only via a new entry in `odluke/`.

## Extraction

Extract:
- manufacturer
- family
- model
- exact variant
- VRAM
- condition
- warranty
- defects
- mining/use clues
- bundle status

LLM may propose values with confidence. Canonical catalog/rules validate them.

## Conflict states

`MATCHED`, `LOW_CONFIDENCE`, `CONFLICT`, `UNMATCHED`, `REVIEW_REQUIRED`.

Never silently force a match.
