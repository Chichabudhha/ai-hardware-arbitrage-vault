# Architecture

```text
Sources (RS + EU)
      ↓
Connectors / Manual Import
      ↓
Raw Observation Store
      ↓
Normalization
      ↓
Canonical Product + Seller
      ↓
Market Observations
      ↓
┌──────────────────┐
│ Serbian Pricing  │
└────────┬─────────┘
         ↓
┌──────────────────┐
│ Landed Cost      │
└────────┬─────────┘
         ↓
┌──────────────────┐
│ Deal Engine      │
└────────┬─────────┘
         ↓
Opportunity DB → Dashboard → Alerts
         ↓
┌──────────────────┐
│ Paper Trading    │  predikcija → posmatran ishod → kalibracija
└──────────────────┘
```

## Separation of concerns

- Connectors: transport/access only.
- Normalizer: structure extraction.
- LLM: interpretation/classification only.
- Pricing engine: deterministic/statistical calculation.
- Cost engine: deterministic money calculation.
- Deal engine: deterministic scoring + policy.
- Dashboard: presentation only.
- Paper trading (`src/paper/`): merenje, ne odlučivanje. Snima verdikt kakav je
  bio u trenutku ocene, upoređuje ga sa posmatranim ishodom i vraća grešku;
  nikad ne menja procenu unazad i nikad ne kupuje.

## Suggested stack

- Python 3.12+
- FastAPI
- PostgreSQL
- SQLAlchemy + Alembic
- Pydantic
- pytest
- background worker: Celery/RQ/async worker, choose only after W1 decision
- dashboard: Next.js/React or lightweight server UI, decide in W7
- Docker Compose for local development

Do not add infrastructure before required by a workstream.
