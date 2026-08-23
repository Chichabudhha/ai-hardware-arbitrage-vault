# Requirements — AI Hardware Arbitrage Serbia

## R1 — Sourcing
Sistem mora podržati source market `RS` i `EU` i razlikovati ih od resale marketa.

## R2 — Listing ingestion
Za svaki listing čuvati source, source_listing_id, URL/locator, raw title/description, seller reference, location, original price/currency, observed_at i status.

## R3 — Product normalization
Listing mora biti mapiran na canonical product ili označen `UNMATCHED` / `CONFLICT`.

## R4 — Serbian resale value
Sistem mora proceniti realnu prodajnu cenu u Srbiji na osnovu relevantnih domaćih market observations.

## R5 — Landed cost
Sistem mora izračunati nabavnu cenu + transport + payment + import/customs/tax + druge definisane troškove. Nepoznat obavezni trošak blokira finalni BUY rezultat.

## R6 — Deal calculation
Izračunati expected sale, conservative sale, landed cost, expected profit, ROI i capital required.

## R7 — Risk
Procena mora obuhvatiti product confidence, seller risk, condition risk, import uncertainty, liquidity i data freshness.

## R8 — Opportunity
Svaka prilika ima Deal Score, Confidence Score, Risk Score i verdict: BUY / NEGOTIATE / WATCH / SKIP.

## R9 — Provenance
Svaki broj koji utiče na odluku mora biti povezan sa source observation-om i vremenom.

## R10 — History
Raw observations i price history su append-only/logički immutable. Status oglasa se prati kroz observations.

## R11 — Manual approval
Nema automatske kupovine, kontakta sa prodavcem ili slanja ponude bez eksplicitne korisničke akcije.

## R12 — Compliance
Automatizacija samo preko dozvoljenih API/feed/manual mehanizama. Connector ima status: research / manual / API / disabled.

## R13 — Learning
Stvarni rezultat kupovine/prodaje može se vratiti u sistem radi kalibracije pricing i opportunity modela.

## Non-goals MVP

- automatska kupovina
- zaobilaženje marketplace zaštita
- kompletna Evropa prvog dana
- svi PC delovi
- autonomno pregovaranje
