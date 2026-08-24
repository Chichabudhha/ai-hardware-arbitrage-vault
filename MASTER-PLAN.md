---
status: aktivan
go-live: null
---

# MASTER PLAN — AI Hardware Arbitrage Serbia

## Cilj

Pronaći potcenjen polovan hardver u Srbiji i Evropi, izračunati landed cost u Srbiji i realnu prodajnu cenu na srpskom tržištu, a zatim rangirati prilike za kupovinu i preprodaju.

## Prioritet

Data foundation → marketplace connectors → product intelligence → Serbian pricing → deal engine → validation → dashboard/alerts → scale.

## MVP scope

- Source: Srbija + najmanje 1 EU marketplace sa dozvoljenim automatizovanim pristupom.
- Resale benchmark: KupujemProdajem + dodatni srpski izvori kada budu definisani.
- Product: NVIDIA GPU.
- Početni modeli: RTX 3090, RTX 3090 Ti, RTX 3080 Ti, RTX 4090, RTX A4000, RTX A5000, RTX A6000, RTX 4080 Super, RTX 4070 Ti Super (D-011).
- Currency: EUR internally; original currency retained.
- No automatic purchasing.

## Workstreams

### W0 — Bootstrap i poslovne odluke — **PROŠAO 2026-08-19**
- [x] Potvrditi početni kapital i maksimalnu kupovinu. (D-008)
- [x] Potvrditi minimalni profit i ROI. (D-009)
- [x] Definisati transport/uvoz cost rules. (D-010 — posrednik, fiksnih 15 €)
- [x] Definisati srpske resale izvore. (D-006 — KupujemProdajem)
- [ ] Potvrditi prvi EU connector. (D-007, #čeka-provere — ne blokira W4)
**Gate:** prošao za finansijski rezultat — svaki prag je odluka u `odluke/` i
konfiguracija u `src/core/policy.py`, ne pretpostavka u kodu.

### W1 — Data foundation
- [ ] Repository/app skeleton.
- [ ] PostgreSQL schema.
- [ ] Raw observation model.
- [ ] Provenance model.
- [ ] Currency/FX abstraction.
- [ ] Tests.
**Gate:** validan listing može da se sačuva, ponovo učita i auditira bez gubitka izvornog podatka.

### W2 — Marketplace connectors
- [ ] Connector contract.
- [ ] KupujemProdajem acquisition strategy: API/allowed/manual research only.
- [ ] Prvi EU connector.
- [ ] Pagination, retry, deduplication, rate limits.
**Gate:** connector daje reproducible raw observations bez bypass-a pristupa.

### W3 — Product intelligence
- [x] Canonical GPU catalog. (9 modela, D-011)
- [x] Listing → product matching. (deterministički, regex preko kataloga)
- [x] Variant/VRAM extraction.
- [x] Confidence + conflict handling. (5 stanja, REVIEW_REQUIRED umesto tihog izbora)
**Gate:** test corpus ima poznat expected output i nema silent mismatches.

### W4 — Serbian market pricing
- [x] Asking price observations. (`PriceObservation`, JSONL store)
- [x] Sold-price source model, ako je dostupan. (`PriceBasis`; SOLD koristi
      medijanu, ASKING/MIXED P25 — izvor sold podataka još ne postoji)
- [x] P25/median/P75. (linearna interpolacija, Tukey 1.5x IQR filter)
- [x] Condition/model adjustments. (used/new razdvojeni, FOR_PARTS i bundle van)
- [x] Resale estimate + confidence. (`ResaleEstimate`, confidence 0-1)
**Gate:** prošao — `ResaleEstimate.explanation` navodi bazu, veličinu uzorka,
starost i razlog za svako isključenje.

Otvoreno: izvor **sold/completed** podataka u Srbiji. Dok ga nema, svaka procena
je ASKING baza sa P25 anchor-om i confidence ≤ ~0.65.

### W5 — Deal engine
- [x] Landed cost. (uklj. posredničku naknadu, D-010)
- [x] Profit.
- [x] ROI.
- [x] Risk.
- [ ] Liquidity.
- [ ] Friction.
- [ ] Deal/Confidence/Risk scores. (risk gotov; deal/confidence score još ne)
- [x] BUY / NEGOTIATE / WATCH / SKIP. (pragovi D-008/D-009 u `src/core/policy.py`)
**Gate:** finansijski rezultat je deterministički i testiran.

### W6 — Paper trading
- [ ] 100+ candidate opportunities. (alat radi; podaci se prikupljaju)
- [x] Predikcije bez kupovine. (`predict` → `data/paper/predictions.jsonl`)
- [x] Outcome tracking. (`outcome`; SOLD/DELISTED/UNSOLD/PRICE_CUT, cena samo uz
      posmatranu prodaju)
- [x] Calibration report. (`report`; greška procene, false positive/negative po
      pragovima iz `policy.py`, greška po confidence opsezima, failure modes)
**Gate:** model ima merljivu preciznost i poznate failure modes.
Izveštaj ostaje `INSUFFICIENT_DATA` dok nema 100 kandidata i 20 ishoda sa cenom.
Postupak: `operations/PAPER-TRADING.md`.

### W7 — Dashboard i alerti
- [ ] Opportunity dashboard.
- [ ] Filters.
- [ ] Telegram/email alerts.
- [ ] Listing detail + provenance.
**Gate:** vlasnik može za <60 sekundi da proceni priliku.

### W8 — Scale
- [x] Više EU marketplace-a. (9 tržišta u matrici na dan 2026-08-23 — dodate
      Mađarska i Rumunija/Hrvatska proširene; generički MANUAL konektor —
      novi sajt je red u `marketplace/sites.json`, ne nova klasa. Slovenija
      merena i prazna za ovaj model; Češka jedan uzorak, bez FX kursa —
      #čeka-provere: `bazos.cz` nema odluku poput D-017, pristupljen van
      odobrenog spiska sajtova.)
- [ ] Više GPU modela.
- [ ] Complete PCs / bundles.
- [ ] Seller intelligence.
- [ ] Learning loop.
**Gate:** novi connector/product može da se doda bez menjanja core deal engine-a.

## Zavisnosti

- ~~#čeka-vlasnika: početni kapital, max purchase, minimalni profit/ROI.~~
  Rešeno 2026-08-19 (D-008, D-009).
- ~~#čeka-vlasnika: visina posredničke naknade; pragovi NEGOTIATE/WATCH.~~
  Rešeno 2026-08-19: fiksnih 15 €, pragovi potvrđeni.
- #čeka-provere: legal/ToS/API status svakog marketplace-a — blokira W2 i
  HA-002 fazu 2. Ručno čitanje javnih oglasa je odobreno posebno (D-012, D-014,
  D-017) i ne menja `automation_status` nijednog konektora.
- ~~#čeka-definicije: metod procene sold price u Srbiji.~~ Mehanizam rešen
  2026-08-19: praćeni oglas koji se proda upisuje se kao SOLD opservacija
  (`outcome --record-observation`). Ostaje da se skupe stvarni ishodi.
- **#čeka-vlasnika: troškovi po koridoru van EU→RS** (D-018). Prevoz je 25 € u
  svim smerovima kao radna pretpostavka (D-019), ali provizija platforme i
  eventualna naknada posrednika za druge smerove nisu odlučene.
- **#čeka-provere: pravni i poreski položaj izvoza iz Srbije** (D-018) — izvozna
  procedura, PDV, eventualna obaveza registracije delatnosti. Pitanje za
  knjigovođu, ne za engine.
- **#čeka-vlasnika: rizik prodaje na daljinu** (D-018) — risk model pokriva
  kupovinu, ne prodaju u zemlji bez naloga i istorije ocena.
- **#čeka-provere: `bazos.cz` (Češka) pristupljen 2026-08-23 bez prethodne
  odluke.** D-012/D-014/D-017 nabrajaju tačan spisak odobrenih sajtova i
  `bazos.cz` nije na njemu. Pročitana je 1 javna stranica (isti obrazac kao
  D-017: vlasnikov Chrome, bez prijave, bez zaobilaženja) i upisana kao
  opservacija, ali bez formalne odluke koja to pokriva. Treba ili proširiti
  D-017 na `bazos.cz` ili povući taj jedan upis.

## Aktivni workstream

**W6 — Paper trading.** Alat je gotov i prošao ceo lanac na stvarnim podacima:
3 predikcije nad nemačkim oglasima (NEGOTIATE / WATCH / SKIP) i 21 praćen
oglas (AT, PL). Svi preduslovi (kurs, API ključ, srpski uzorak) su rešeni.

Prva provera liste praćenja izvršena 2026-08-23: 24 ishoda upisano, **0 SOLD**
— i dalje nijedna posmatrana prodaja. Usput otkriven i popravljen bug koji je
5 od 6 willhaben oglasa lažno prijavio kao nestale (URL bez SEO sluga je rušio
willhaben-ov routing, ne stvaran nestanak oglasa — vidi
`reference/naucene-lekcije.md`).

Druga provera 2026-08-24: svih 15 subjekata provereno (ispravnim slug
URL-ovima), 14 UNSOLD nepromenjeno, 1 stvarno DELISTED (kleinanzeigen,
potvrđeno oznakom "Gelöscht", ne ambiguozan 404). HU (hardverapro) i HR
(njuskalo) dodati na listu praćenja — 23 otvorena subjekta ukupno. I dalje
0 SOLD posle 5 dana na 15 pod nadzorom.

Ostalo je i dalje **vreme i ishodi**: gate traži 100 kandidata i 20 ishoda sa
posmatranom cenom. Od 6 pratećih austrijskih oglasa samo je 1 stvarno nestao
(bez potvrde prodaje), ostalih 5 stoji nepromenjeno 4-11 dana — to pre ide
protiv teze o brzoj prodaji po 499-550 € nego u njenu korist.

Uz W6 je otvoren i **W8-ranije nego planirano**: matrica cena po tržištima
(D-018) sada pokriva 9 tržišta (dodata Mađarska, proširena Hrvatska). Najveća
neto razlika više nije DE→AT nego **DE→HU: +128,74 € (45,5%)** — Mađarska je
u prvom mernom prolazu (D-017, 19.08.) odbačena na jednom skupom uzorku
(195.000 Ft); sa 5 sopstvenih uzoraka (158.900-199.999 Ft) izgleda potpuno
drugačije. I ovo je i dalje samo asking cena bez ijedne potvrđene prodaje.

## Rizici

- Pogrešan product match.
- Netačna resale procena zbog asking-only podataka.
- Nepotpuni import/transport troškovi.
- Nelegalan/neodobren automated access.
- GPU defect/mining history.
- Slaba likvidnost.
- Promena kursa.
