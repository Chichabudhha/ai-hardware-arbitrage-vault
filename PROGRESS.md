---
updated: 2026-08-24
status: matrica proširena na BG/BE/NL; Holandija (marktplaats) sada najveća DE-izlaz razlika; D-020 diler cene isključene iz statistike
---

# PROGRESS — AI Hardware Arbitrage Serbia

## Gde smo stali
Lanac radi od kraja do kraja na stvarnim podacima: nemački oglas → product match
→ landed cost → srpska procena iz stvarnih oglasa → verdikt → zapisana
predikcija. Matrica cena pokriva **9 tržišta** (Mađarska i Češka dodate
2026-08-23, Hrvatska proširena sa 1 na 4 uzorka).

Druga provera liste praćenja (2026-08-24): svih 15 otvorenih subjekata
provereno sa ispravnim (slug) URL-ovima. **14/15 i dalje UNSOLD, nepromenjena
cena** (5 willhaben, 8 olx-pl, 1 kleinanzeigen). **1 kleinanzeigen oglas
(EVGA 3080Ti, 300 €) stvarno DELISTED** — stranica nosi eksplicitnu oznaku
"Gelöscht", ne generički 404, pa je nalaz pouzdan (vidi lekciju o anti-bot
404 vs. stvarno uklanjanje). Uzgred otkriven parsing-kvirk: `get_page_text`
je za drugi kleinanzeigen oglas prvi put vratio tekst nepovezanog
reklamnog/preporučenog vidžeta umesto članka — potvrđeno screenshot-om da je
pravi oglas i dalje živ, nepromenjen. I dalje **0 ishoda sa posmatranom
cenom** — 5 dana bez nijedne potvrđene prodaje na 15 pod nadzorom.

Mađarska (hardverapro) i Hrvatska (njuskalo) su ovom sesijom prvi put dodate
na listu praćenja (`watch --add`, D-017 već pokriva oba sajta) — 5 + 4 = 9
novih subjekata, sada 23 ukupno otvorenih. Ranije je Mađarska bila samo u
matrici asking cena, bez merenja stvarnog ishoda.

**Drugi deo sesije — proširenje pretrage na nova tržišta (Bugarska, Belgija,
Holandija; sva tri već pokrivena spiskom u D-017, samo nisu ranije korišćena).**
Usput otkriven i ispravljen **arhitekturni nalaz**: `src/pricing/serbian_market.py`
nije razdvajao `dealer_reference` (diler) od `asking` (privatni prodavac) opservacija
pri računanju P25/medijane/P75 — ista greška koju D-013 zabranjuje za mešanje
valuta, samo neprimenjena na tip prodavca. Otkriveno na `olx.bg`, gde je 7 od 9
nađenih oglasa bilo od preprodavaca hardvera (dileri), a diler cena sistematski
gura medijanu naviše. **Odluka D-020** (odobrio vlasnik 2026-08-24): `dealer_reference`
i `manual_reference` se isključuju iz statistike na svim tržištima, retroaktivno;
opservacije ostaju upisane (princip 6), samo ne ulaze u percentile. Implementirano
u `_filter()`, 2 nova testa, 217 testova prolazi.

Nakon fixa:
- **olx.bg (BG):** 9 opservacija (2 privatne, 7 diler — 3 od istog diler-a
  PCFlip.BG). n=2 posle isključivanja dilera, ispod praga uzorka.
- **2dehands.be (BE):** 3 opservacije, sve privatne (450–500 €), ispod praga uzorka.
- **marktplaats.nl (NL):** 14 opservacija (13 privatnih + 1 diler "Hardriven
  Technologies", sopstveni sajt hardriven.nl, isključen). n=12 posle IQR filtera.
  **Nova najveća DE→izlaz razlika: DE→NL +137 € neto (47,9%)**, ispred
  DE→HU (+128,74 €) koja je bila prva ranije ove sesije.

## Brojevi na dan 2026-08-24
- **39 ishoda upisano ukupno** (append-only, uklj. istorijske ispravke):
  10 DELISTED, 29 UNSOLD, **0 SOLD, 0 sa cenom**. +15 novih outcome linija
  ove sesije (14 UNSOLD, 1 DELISTED).
- **23 subjekta otvoreno** na listi praćenja (14 preostalih iz prošlog
  prolaza + 9 novih: 5 hardverapro/HU, 4 njuskalo/HR).
- **+26 novih opservacija** (9 olx-bg, 3 2dehands, 14 marktplaats) —
  **107 opservacija ukupno**, **12 tržišta** (3 nova: BG, BE, NL).
- **Matrica (RTX 3080 Ti) posle proširenja:** DE 338/425/463 (n=8) < RS
  380/390/410 (n=9) < IT 430/450/600 (n=13) < HU 438,32/491,74/501,33 (n=5) <
  RO 448,03/452,79/457,56 (n=8) < AT 450/480/499 (n=9) < PL 462,01/485,13/508,47
  (n=13) < **NL 500/500/535 (n=12, novo)**. BG (n=2), BE (n=2), HR (n=3/4),
  CZ (n=1) ispod praga uzorka (5).
- **Najveća neto razlika je sada DE→NL: +137 € (47,9%)**, ispred DE→HU
  (+128,74 €) i DE→PL (+122,13 €).
- **D-020 doneta i primenjena**: dealer_reference/manual_reference isključeni
  iz P25/medijana/P75 svuda, retroaktivno. Nijedna postojeća opservacija van BG/NL
  nije bila diler-tip, pa se nijedna stara ćelija matrice nije promenila.

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
  imamo 3 predikcije + 23 otvorena watch-subjekta, 39 ishoda upisano ukupno
  ali i dalje 0 sa cenom (svi DELISTED/UNSOLD).
- ⏳ Uzorci ispod minimuma: RTX 3090 n=3, RTX 4080 Super n=2, njuskalo (HR) n=4,
  bazos (CZ) n=1.
- ⏳ **Otvoreno pitanje, sada jače podržano:** od 15 subjekata praćenih 5 dana
  (19.08 → 24.08), samo 1 je nestao (kleinanzeigen, potvrđeno "Gelöscht");
  ostalih 14 stoji nepromenjeno na istoj ceni. To i dalje ide protiv teze o
  brzoj apsorpciji po posmatranim asking cenama — bez ijedne potvrđene
  prodaje ni u jednom pravcu, ni posle dve provere.
- ⏳ CZK kurs i dalje nedostaje (cnb.cz, ecb.europa.eu blokirani); 1 češki
  uzorak čeka konverziju.

## Otvoreno za odluku
- 🟡 **Trgovina van koridora EU→RS (D-018).** #čeka-vlasnika: troškovi po
  koridoru (provizija platforme, naknada posrednika u drugom smeru).
  #čeka-provere: pravni i poreski položaj izvoza iz Srbije. #čeka-vlasnika:
  rizik prodaje na daljinu — risk model pokriva kupovinu, ne prodaju.
- 🟡 Minimalna confidence za BUY (#čeka-vlasnika). Odgovor treba da dođe iz
  kalibracionog izveštaja, ne iz pretpostavke.
- 🟡 **#čeka-vlasnika (novo 2026-08-24): ponovljeni privatni nalog kao
  neformalni diler.** "Dan" na marktplaats.nl (2 god. na sajtu, 205 ocena)
  je izvor 3 od 12 holandskih opservacija u uzorku, gotovo identičan tekst
  oglasa/grad. Nema formalnu "Zakelijk" (poslovni) oznaku sajta, pa je upisan
  kao privatni po istom kriterijumu kao ostali (D-020: oznaka platforme), ali
  obrazac (visok broj ocena, ponovljen šablon) liči na neformalnog
  preprodavca. Nije isključeno — samo zabeleženo. Treba odluka: da li nalog
  sa X+ ponovljenih oglasa za isti model treba tretirati kao diler bez obzira
  na platformsku oznaku, i ako da, koji prag (broj oglasa/ocena).

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
Za nekoliko dana: `arbitrage watch`, pa proći kroz svih 23 otvorena subjekta
(14 stari + 9 novi HU/HR) i zabeležiti šta se desilo. Ako i posle trećeg
prolaza ostane 0 SOLD na celoj listi, vredi razmotriti da li 5-dnevni interval
uopšte hvata realan ciklus prodaje na ovim tržištima, ili treba duži razmak
između provera.

Vredi i vratiti se na Belgiju (2dehands, n=2) i Bugarsku (olx.bg, n=2 posle
D-020) sa još jednim mernim prolazom da pređu prag uzorka od 5 — trenutno
oba ispod praga i ne ulaze u matricu.

Kod koji nedostaje, a ne zavisi od podataka: W5 liquidity, friction i
deal/confidence score.

## Poslednje sesije
- 2026-08-24 (drugi deo) — Merni prolaz na 3 nova tržišta iz D-017 spiska
  koja do sada nisu korišćena: Bugarska (olx.bg), Belgija (2dehands.be),
  Holandija (marktplaats.nl). Usput otkriven arhitekturni nalaz: pricing
  engine nije razdvajao diler (`dealer_reference`) od privatnih (`asking`)
  cena — ista greška klase kao D-013 (mešanje uzorka), samo za tip prodavca
  umesto valute. **D-020** (odobrio vlasnik): diler cene isključene iz
  P25/medijana/P75 svuda, retroaktivno; opservacije ostaju upisane. +26
  opservacija (BG 9, BE 3, NL 14). **Holandija je nova najveća DE→izlaz
  razlika: +137 € neto (47,9%)**, ispred Mađarske. 217 testova prolazi (2
  nova za D-020).
- 2026-08-24 (prvi deo) — Druga provera liste praćenja: svih 15 subjekata (slug
  URL-ovi za willhaben), 14 UNSOLD + 1 stvarno DELISTED (potvrđeno "Gelöscht",
  ne ambiguozan 404). Dodati hardverapro (HU, 5) i njuskalo (HR, 4) na listu
  praćenja — 23 otvorena subjekta ukupno. I dalje 0 SOLD posle 5 dana. 215
  testova prolazi (bez izmene koda, samo podaci).
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
