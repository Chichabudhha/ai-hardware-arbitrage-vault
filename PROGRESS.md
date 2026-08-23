---
updated: 2026-08-23
status: matrica proširena na 9 tržišta; Mađarska se pojavila kao nova vodeća prodajna destinacija; willhaben bug ispravljen
---

# PROGRESS — AI Hardware Arbitrage Serbia

## Gde smo stali
Lanac radi od kraja do kraja na stvarnim podacima: nemački oglas → product match
→ landed cost → srpska procena iz stvarnih oglasa → verdikt → zapisana
predikcija. Matrica cena sada pokriva **9 tržišta** (dodati Mađarska i Češka
ovom sesijom, Hrvatska proširena sa 1 na 4 uzorka).

Prva provera liste praćenja (2026-08-23) je isprva pogrešno prijavila 6/6
austrijskih oglasa kao nestale — **bio je bug**: sačuvan URL bez SEO sluga je
rušio willhaben-ov SPA routing (404 na formu bez sluga), ne stvarno uklanjanje.
Ispravljeno: 5 od 6 je zapravo živo i nepromenjeno; samo 1 (400 €) je stvarno
nestao (willhaben eksplicitno vraća "Anzeige nicht mehr verfügbar"). I dalje
0 ishoda sa posmatranom cenom.

## Brojevi na dan 2026-08-23
- **81 opservacija** u `data/observations/serbia.jsonl`, **9 tržišta**
  (kupujemprodajem 15, olx-pl 16, subito 13, olx-ro 10, willhaben 9,
  kleinanzeigen 8, hardverapro 5 — novo, njuskalo 4 — novo, bazos 1 — novo,
  CZK bez kursa).
- **3 predikcije** u `data/paper/predictions.jsonl` (NEGOTIATE / WATCH / SKIP).
- **24 ishoda upisano** 2026-08-23 (uklj. 5 korekcija): 3 DELISTED (1
  willhaben, 2 olx-pl), 21 UNSOLD. **0 SOLD, 0 ishoda sa cenom.**
- **15 subjekata i dalje otvoreno** na listi praćenja (2 kleinanzeigen + 5
  willhaben + 8 olx-pl).
- **Matrica (RTX 3080 Ti):** DE 338/425/463 (n=8) < RS 380/390/410 (n=9) <
  IT 430/450/600 (n=13) < HU **438/492/501 (n=5, novo)** < RO 448/453/458
  (n=8) < AT 450/480/499 (n=9) < PL 462/485/508 (n=13). HR (n=4) i CZ (n=1)
  ispod praga uzorka (5).
- **Najveća neto razlika je sada DE→HU: +128,74 € (45,5%)**, ispred DE→PL
  (+122,13 €) i DE→AT (+117 €) — promenilo se u odnosu na prošlu sesiju gde je
  AT bio prvi; Mađarska je ranije odbačena na jednom uzorku (195.000 Ft), sada
  sa 5 uzoraka (158.900–199.999 Ft) izgleda sasvim drugačije.
- Matrica, RTX 3080 Ti, sve u evrima (`arbitrage matrix --product-id rtx-3080-ti`):

  | tržište | n | P25 | medijana | P75 |
  |---|---|---|---|---|
  | kleinanzeigen (DE) | 8 | **338** | 425 | 463 |
  | kupujemprodajem (RS) | 9 | 380 | 390 | 410 |
  | subito (IT) | 13 | 430 | 450 | 600 |
  | hardverapro (HU) | 5 | 438,32 | 491,74 | 501,33 |
  | olx-ro (RO) | 8 | 448,03 | 452,79 | 457,56 |
  | willhaben (AT) | 9 | 450 | 480 | 499 |
  | olx-pl (PL) | 13 | 462,01 | 485,13 | 508,47 |

  Ispod praga uzorka (5): njuskalo (HR) n=4, bazos (CZ) n=1.

  Najveća neto razlika (posle 25 € prevoza): **DE→HU +128,74 € (45,5%)**,
  DE→PL +122,13 €, DE→AT +117 €, DE→RO +89,79 €, DE→IT +87 €. DE→RS (kupovina
  u Nemačkoj, prodaja u Srbiji) ostaje nepromenjeno +27 € — ni DE ni RS nisu
  dobili nove opservacije ove sesije.

## Gotovo
- ✅ Source/resale, data/provenance i pricing/deal engine model definisani.
- ✅ Deterministički `product_match` (9 modela, katalog + regex).
- ✅ W0 poslovne odluke D-008 … D-011; pragovi u `src/core/policy.py`.
- ✅ W4 srpski pricing engine: P25/median/P75, pravila isključenja, deterministička
  confidence, INSUFFICIENT_DATA ispod 5 uzoraka.
- ✅ W5 (delom): landed cost, profit, ROI, risk, verdikt.
- ✅ **W6 alat: predikcije, ishodi, kalibracioni izveštaj, lista praćenja.**
- ✅ **Povratna sprega: prodat praćeni oglas postaje SOLD opservacija** — jedini
  put da procena pređe sa ASKING na SOLD osnovu.
- ✅ **Matrica cena po tržištima + bruto/neto razlike, sve u evrima.**
- ✅ **Generički MANUAL konektor: novi sajt je red u `marketplace/sites.json`.**
- ✅ Kursevi sa centralnih banaka (NBS preko vlasnika, BNR, MNB, BNB, NBP).
- ✅ Prva provera liste praćenja (2026-08-23): 19 ishoda upisano, 9 DELISTED,
  10 UNSOLD.
- ✅ Bug fix: `watch` i `report` su pucali čim je watch-oglas dobio ishod —
  `pair_records` je dobijao i outcome-e koji ne pripadaju nijednoj predikciji
  (žive u `watchlist.jsonl`, ne u `predictions.jsonl`). Filtrirano u
  `cmd_watch`/`cmd_report` pre poziva; test u `tests/test_cli.py`.
- ✅ 215 testova prolazi.
- ✅ **Bug fix #2 (nalaz istog dana):** 5 od 6 willhaben "DELISTED" ishoda je
  bilo pogrešno — sačuvan URL bio je bez SEO sluga (`/d/{id}` umesto
  `/d/x-{id}/`), pa je willhaben-ov SPA vraćao 404 na ispravan, još uvek živ
  oglas. Otkriveno slučajno dok se tražio nov oglas (isti ID se pojavio u
  pretrazi). Ispravljeno upisom novih outcome linija (append-only, principe 6);
  stari pogrešni upisi ostaju na disku kao istorijski trag, ne brišu se.
  **Lekcija:** willhaben URL mora imati bilo koji slug-prefiks pre ID-ja da bi
  routing radio — zapisano u `reference/naucene-lekcije.md`.
- ✅ Domeni koji su ranije bili blokirani u Chrome ekstenziji (njuskalo.hr,
  subito.it, olx.ro, hardverapro.hu, bolha.com, bazos.cz) rade u ovoj sesiji —
  dozvole se povremeno resetuju po grupi tabova, treba ih tražiti ponovo, ne
  pretpostaviti da su trajno blokirani.
- ✅ Merni prolaz proširen: **Mađarska (hardverapro.hu) sada ima 5 uzoraka**
  (158.900–199.999 Ft, ranije samo 1 na 195.000 Ft) i **ispada iznad Austrije**
  kao druga najbolja prodajna destinacija posle Poljske. Hrvatska (njuskalo)
  ima 4 uzorka (300–500 €), i dalje ispod praga od 5. Slovenija (bolha.com):
  0 samostalnih kartica u ponudi trenutno. Češka (bazos.cz): 1 uzorak
  (8.500 Kč), i dalje bez CZK kursa za konverziju.

## U toku
- ⏳ **Čeka se da ishodi sazru.** Gate traži 100 kandidata i 20 ishoda sa cenom;
  imamo 3+21 subjekata, 24 ishoda upisano ali 0 sa cenom (svi DELISTED/UNSOLD).
- ⏳ Uzorci ispod minimuma: RTX 3090 n=3, RTX 4080 Super n=2, njuskalo (HR) n=4,
  bazos (CZ) n=1.
- ⏳ **Otvoreno pitanje (posle ispravke):** samo 1 od 6 willhaben oglasa je
  stvarno nestao (400 €, potvrđeno "nije više dostupan"); ostalih 5 stoji
  nepromenjeno 4-11 dana. To ne podržava "brzu apsorpciju po 499-550 €" —
  ako nešto govori, to je da AT oglasi dugo stoje po toj ceni, ne da se brzo
  prodaju. Nema potvrde prodaje ni u jednom pravcu.
- ⏳ CZK kurs i dalje nedostaje (cnb.cz, ecb.europa.eu blokirani); 1 češki
  uzorak čeka konverziju.

## Otvoreno za odluku
- 🟡 **Trgovina van koridora EU→RS (D-018).** #čeka-vlasnika: troškovi po
  koridoru (provizija platforme, naknada posrednika u drugom smeru).
  #čeka-provere: pravni i poreski položaj izvoza iz Srbije. #čeka-vlasnika:
  rizik prodaje na daljinu — risk model pokriva kupovinu, ne prodaju.
- 🟡 Minimalna confidence za BUY (#čeka-vlasnika). Odgovor treba da dođe iz
  kalibracionog izveštaja, ne iz pretpostavke.

## Blokirano
- 🔴 Verifikacija dozvoljenog automatizovanog pristupa (#čeka-provere) — blokira
  W2 i HA-002 fazu 2. Ne blokira W6: ručno čitanje javnih oglasa je odobreno
  posebno (D-012, D-014, D-017).
- 🔴 Izbor prvog EU connectora za automatiku (D-007, #čeka-provere).
- 🟡 Dozvole domena u Chrome ekstenziji ne preživljavaju novu grupu tabova —
  treba ih tražiti iznova svaki put, ali nisu trajno blokirane: njuskalo,
  subito, olx.ro, hardverapro, bolha i bazos su sve prošli 2026-08-23 u istoj
  sesiji. Neizmereno realno ostaje samo ono što tržište stvarno nema (SI: 0
  golih kartica) ili nema kurs (CZ: 1 uzorak čeka CZK kurs — cnb.cz i
  ecb.europa.eu i dalje blokirani).
- 🟡 **#čeka-provere: `bazos.cz` nema odluku poput D-017.** Pročitana 1 stranica
  i upisana opservacija 2026-08-23 pre nego što je postojala eksplicitna
  odluka za taj sajt (D-012/D-014/D-017 nabrajaju tačan spisak i `bazos.cz`
  nije na njemu). Treba ili proširiti D-017 na Češku ili povući taj upis.

## Sledeći zadatak
Za nekoliko dana: `arbitrage watch`, pa proći kroz preostalih 15 subjekata
(koristeći URL sa slugom za willhaben, ne goli ID) i zabeležiti šta se desilo.
Vredi dodati par mađarskih i hrvatskih kartica na listu praćenja (`watch --add
hardverapro`, `watch --add njuskalo`) da se i tamo meri stvarna prodaja, ne
samo asking — Mađarska je sada matematički najbolja prodajna destinacija, ali
to je i dalje samo asking cena bez sold potvrde.

Kod koji nedostaje, a ne zavisi od podataka: W5 liquidity, friction i
deal/confidence score.

## Poslednje sesije
- 2026-08-23 (drugi deo) — Traženje novih oglasa na 8 tržišta (DE, AT, PL, RS,
  IT, RO, HR, HU, SI, CZ — poslednja dva ispitana, SI prazno, CZ 1 uzorak).
  +22 nove opservacije. Otkriven i ispravljen willhaben URL bug (5/6 lažnih
  DELISTED). Mađarska (hardverapro) prvi put sa n=5 — ispada najveća neto
  razlika od nemačkog izvora (DE→HU +128,74 €, 45,5%), ispred Poljske i
  Austrije.
- 2026-08-23 (prvi deo) — Prva provera liste praćenja: 19 ishoda upisano.
  Otkriven i popravljen bug u `watch`/`report` (outcome za watch-oglas je
  rušio `pair_records`). 213 → 215 testova.
- 2026-08-19 — W6 alat, prvi srpski uzorak, prve predikcije, matrica na 6
  tržišta, generički konektor, lista praćenja. Odluke D-012 … D-019.
- 2026-08-19 — W4 srpski pricing engine; W0 zatvoren, pragovi u kodu.
- 2026-08-18 — Matcher, deterministički product_match, AI orkestracija,
  HA-002 faza 1.
