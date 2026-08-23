# Marketplace Strategy

## Market roles

| Market | Role |
|---|---|
| Serbia | sourcing + resale |
| EU | sourcing |

## Connector status

`RESEARCH` → `MANUAL` → `API/FEED` → `AUTOMATED` only after access/compliance verification.

## MVP

1. KupujemProdajem: primary Serbian market. Determine permitted acquisition method before automation.
2. First EU source: choose a marketplace with documented API/feed and useful used-GPU inventory. Marktplaats is the initial candidate, subject to current access verification.

## Connector contract

Every connector exposes:
- `search(query, filters)`
- `get_listing(id)`
- `normalize_raw(response)`
- `health_check()`

Connector must support:
- pagination
- retries with backoff
- rate limits
- timeout
- deduplication
- source IDs
- observed timestamps
- raw payload retention

## Compliance gate

Before automation:
- verify current Terms/API terms
- verify authentication requirements
- verify permitted use
- verify rate limits
- record source URL and verification date

If unclear: `RESEARCH` or `MANUAL`, not automated.

## Dodavanje novog izvora (od 2026-08-19)

Novi oglasnik se dodaje kao **red u `marketplace/sites.json`**, ne kao nova
klasa. Profil opisuje: `marketplace`, `country`, `base_url`,
`listing_id_pattern` i CSS selektore za naslov, cenu, opis, prodavca i lokaciju.
Selektori sajta se probaju prvi, pa zajednički fallback (`h1`, `[class*=price]`,
`[class*=description]`...). Polje koje se ne nađe ostaje `None` i prijavljuje se
kao nedostajuće — ne popunjava se pretpostavkom.

Šta profil **ne može**:

- Ne može da dobije automatizovan pristup. `GenericManualConnector` je uvek
  `MANUAL` i `UNVERIFIED`, bez obzira šta u JSON-u piše; `fetch()` ostaje
  blokiran compliance gate-om. Prelaz na `AUTOMATED` je odluka u `odluke/`,
  ne polje u konfiguraciji.
- Ne može da pregazi ručno pisan konektor. `kupujemprodajem` i `kleinanzeigen`
  imaju svoje parsere i registry ih uvek bira ispred profila iz konfiguracije.

Loš profil (nevalidan JSON, nedostajuće polje, neispravan regex) odbija **ceo**
fajl umesto da tiho ispusti jedan sajt.
