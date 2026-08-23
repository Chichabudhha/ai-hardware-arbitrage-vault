# src/ — GPU Arbitrage Engine (HA-002, faza 1)

## Slojevi

| Modul | Odgovornost | Šta NE radi |
|---|---|---|
| `core/` | Kanonski modeli, Decimal novac, provenance | Ne pristupa mreži |
| `scrapers/` | Transport i normalizacija (KupujemProdajem, Kleinanzeigen) | Ne tumači i ne računa |
| `products/` | Kanonski katalog + **deterministički** product match | Ne koristi embeddings ni LLM |
| `deal_engine/` | LLM tumačenje oglasa + deterministički risk score | Ne računa novac (D-005) |
| `pricing/` | Landed cost, profit, ROI, verdikt | Ne procenjuje prodajnu cenu (to je pricing engine, W-faza) |
| `obsidian_sync/` | Renderovanje note po `blokovi/DEAL-template.md` | Ne menja template |

## Compliance

Oba konektora su `automation_status = RESEARCH`. `fetch()` namerno podiže
`ComplianceError` dok se pristup ne verifikuje i ne upiše u `odluke/`
(D-006, D-007). Nema proxy rotacije, nema anti-bot mera, nema UA spoofing-a —
`CLAUDE.md` pravilo 7. Do verifikacije radi se preko `scrapers/manual_import.py`.

Kad pristup bude verifikovan:
1. Popuni `AccessVerification(terms_url=..., verified_on=..., permitted_use=...)`.
2. Promeni `automation_status` na `API_FEED` ili `AUTOMATED`.
3. Potvrdi selektore u `html_parse.SelectorMap` na sačuvanom fixture-u i upiši `verified_on`.

## Product match

Identitet kartice je **lookup, ne procena.** Skup ciljnih čipova je zatvoren
(7 modela iz `product-intelligence/PRODUCT-INTELLIGENCE.md`), pa regex preko
kanonskog kataloga daje tačan rezultat besplatno.

Embeddings su testirani i **odbačeni**: `nomic-embed-text` daje sličnost 0.930
za "RTX 3090 24GB Gigabyte Gaming OC" vs "RTX 3080 10GB Gigabyte Gaming OC", a
samo 0.708 za isti proizvod drukčije formulisan. Detalji u
`reference/naucene-lekcije.md`.

Stanja (`MatchStatus`): `MATCHED` · `LOW_CONFIDENCE` · `CONFLICT` · `UNMATCHED`
· `REVIEW_REQUIRED`. Match se nikad ne forsira nasilno.

Samo `MATCHED` prolazi dalje — `build_opportunity` inače vraća
`INSUFFICIENT_DATA` sa `product_match:<STATUS>` u `missing_inputs`
(`CLAUDE.md` §5 navodi product match kao obavezan atribut).

Kad LLM i katalog nisu saglasni, katalog pobeđuje, a neslaganje se upisuje u
`risk_notes` (`reconcile_with_llm`).

## UNKNOWN ≠ 0

Svaki nedostajući finansijski ulaz daje `Verdict.INSUFFICIENT_DATA` i listu
`missing_inputs`; nota prikazuje `UNKNOWN`, nikad `0`.

## Komande

```bash
python -m src.cli health
python -m src.cli match "RTX 3090 24GB Gigabyte"
python -m src.cli import <fajl.html> --marketplace kupujemprodajem --listing-id 111 --url <url>
python -m src.cli note  <fajl.html> --marketplace kleinanzeigen --listing-id 222 --url <url> \
    --evaluate --shipping-eur 35 --import-buffer-eur 60 --expected-sale-rsd 117200
python -m pytest -q
```

`--evaluate` zahteva `ANTHROPIC_API_KEY` u `.env` (model: `claude-opus-5`).
`--expected-sale-rsd` zahteva observovan EUR/RSD kurs u `data/fx-observations.json`.
