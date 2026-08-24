# Odluke — AI Hardware Arbitrage Serbia

| ID | Odluka | Status | Datum |
|---|---|---|---|
| D-001 | Source markets su Srbija + Evropa; resale market je Srbija | odobreno | 2026-08-18 |
| D-002 | MVP fokus: NVIDIA high-VRAM GPU | odobreno | 2026-08-18 |
| D-003 | Nema automatske kupovine | odobreno | 2026-08-18 |
| D-004 | Raw observations se ne prepisuju | odobreno | 2026-08-18 |
| D-005 | AI ne računa finansijske rezultate | odobreno | 2026-08-18 |
| D-006 | KupujemProdajem je primarni srpski resale benchmark; način automatizacije ostaje predmet provere | aktivno | 2026-08-18 |
| D-007 | Prvi EU connector bira se posle compliance/API provere | #čeka-provere | 2026-08-18 |
| D-008 | Početni kapital 1.000 €; maksimalno 500 € po jednoj kupovini | odobreno | 2026-08-19 |
| D-009 | BUY zahteva ROI ≥ 18% I profit ≥ 50 €; NEGOTIATE ≥ 9%, WATCH ≥ 4% | odobreno | 2026-08-19 |
| D-010 | Nabavka iz EU ide preko posrednika; fiksna naknada 15 € po kartici | odobreno | 2026-08-19 |
| D-011 | Katalog proširen na RTX 4080 Super i 4070 Ti Super; V100 i A100 odbijeni | odobreno | 2026-08-19 |

## D-008 — Kapital i limit po kupovini

Početni kapital je **1.000 €**, maksimum po jednoj kartici **500 €**.

Posledica u kodu: `src/core/policy.py` (`OWNER_POLICY`). Oglas iznad limita ne
može da dobije BUY bez obzira na ekonomiju — najviše NEGOTIATE, jer ciljna cena
može da ga vrati u budžet. Praktično isključuje RTX 4090, A5000 i A6000 iz
prvog kruga po trenutnim tržišnim cenama.

## D-009 — Pragovi profita i ROI

BUY zahteva **oba** uslova: ROI ≥ 18% **i** apsolutni profit ≥ 50 €. Visok ROI
na jeftinoj kartici nije posao — 40% na kartici od 100 € je 40 € i ne pokriva
vreme i rizik.

NEGOTIATE ≥ 9% i WATCH ≥ 4% su **izvedeni**, ne izabrani: zadržan je isti odnos
prema BUY pragu koji je imao raniji savetodavni set (12/25 i 5/25 od BUY praga),
zaokruženo na ceo procenat. **Vlasnik ih je potvrdio 2026-08-19** — nisu više
otvoreno pitanje.

Zamenjuje tvrdo kodirane vrednosti 25/12/5% koje su stajale u
`src/pricing/calculator.py` kao neodobrena pretpostavka.

## D-010 — Model nabavke iz EU: posrednik

EU nabavka ide preko posrednika/preprodavca koji naplaćuje naknadu. Zato:

Naknada je **fiksna: 15 € po kartici** (`Policy.intermediary_fee_eur`), ne
procenat. Podložna promeni novom odlukom.

- Uvoz bez navedene naknade koristi tih 15 € iz politike — nije UNKNOWN, jer je
  vrednost odobrena.
- `CostInputs.intermediary_fee_eur` prebrisuje politiku kad posrednik za
  konkretan deal traži drugu cenu.
- Domaća kupovina nema posrednika, pa je tamo 0 činjenica, a ne UNKNOWN.
- Carina/PDV se i dalje vode kroz `import_buffer_eur` — ako ih posrednik već
  uračunava u svoju naknadu, buffer se postavlja na 0 **eksplicitno**, uz izvor.

## D-011 — Proširenje kataloga

Dodati: **RTX 4080 Super** (16 GB, Ada) i **RTX 4070 Ti Super** (16 GB, Ada).

Odbijeni: **Tesla V100** i **A100** — visok VRAM i AI vrednost, ali srpsko
resale tržište za datacenter kartice je preplitko da bi pricing engine dao
uzorak, a D-008 limit ih ionako ne dohvata.

Obična RTX 4080 i obična 4070 Ti **nisu** dodate — matcher ih ostavlja
`UNMATCHED` umesto da ih tiho spoji sa Super varijantom.


## D-012 — Ručno čitanje javnih KupujemProdajem oglasa kroz vlasnikov browser

**Odobreno od vlasnika 2026-08-19.**

Za prikupljanje srpskih asking opservacija (W6) dozvoljeno je otvarati **javno
vidljive** stranice oglasa u vlasnikovom Chrome-u i prepisivati ono što u njima
piše.

Šta ovo **nije**: nije `AUTOMATED` status konektora. `fetch()` u
`src/scrapers/` ostaje blokiran, a KupujemProdajem ostaje `RESEARCH` dok
ToS/pristup ne budu provereni (#čeka-provere). Ovo je proširenje `MANUAL` puta,
ne prelaz na sledeći nivo.

Granice koje važe uz odobrenje:
- Bez prijave na nalog, bez zaobilaženja logina, captcha, rate limita ili
  anti-bot mera (princip 7).
- Samo javno vidljiv sadržaj oglasa: cena, naslov, stanje, lokacija, ID, URL.
- Tempo ručnog pregleda, ne masovni crawl. Reda veličine desetina oglasa.
- Bez ličnih podataka prodavca preko onoga što ionako stoji u oglasu.
- Svaka opservacija nosi `access_method=MANUAL`, URL i `observed_at`.

Razlog: bez srpskih opservacija engine radi ali nema šta da meri, a W6 gate
traži merenje pre trošenja novca. Alternativa (vlasnik ručno puni CSV) daje
identične podatke uz veći trošak vremena.

## D-013 — EUR je validna valuta srpske opservacije

**Odobreno od vlasnika 2026-08-19.**

`PRICING-ENGINE.md` je pretpostavljao da srpsko tržište kotira u dinarima, pa je
sve što nije RSD izbacivano iz uzorka. Provera na KupujemProdajem 2026-08-19
pokazala je suprotno: sve tri upotrebljive polovne RTX 3090 kartice oglašene su
u evrima. Po starom pravilu procena bi odbacila ceo uzorak.

Novo pravilo:

- **RSD i EUR su obe validne** valute srpske opservacije. Oglas u evrima na
  srpskom sajtu je srpski tržišni podatak, ne uvozni.
- **Uzorak se nikad ne meša.** Percentil nad dve valute je računanje sa
  neistorodnim jedinicama. Bira se jedna valuta po proceni; ostale opservacije
  se isključuju sa razlogom `currency_not_sample:<VAL>` i vide se u izveštaju.
- **Izbor valute prati tržište:** ona u kojoj proizvod ima više opservacija.
  Nerešeno se lomi na EUR, jer je to ono što GPU segment kotira i jer se
  nerešeno mora lomiti isto u svakom pokretanju. Poziv sme i eksplicitno da
  traži valutu.
- **Treća valuta se i dalje isključuje** (`unsupported_currency:<VAL>`) — ušla bi
  samo kroz konverziju, a konvertovana cena je izvedena, ne posmatrana.
- **Kurs se traži samo kad nešto u poslu jeste u dinarima.** Procena već u
  evrima ne zahteva EUR/RSD. `Opportunity.expected_sale_rsd` ostaje prazno kad
  je procena u evrima — konvertovan broj bi izgledao kao posmatran.

Ne menja se: asking ostaje asking (P25 sidro), minimum od 5 uzoraka, IQR filter.

## D-014 — Ručno čitanje javnih Kleinanzeigen oglasa prošireno na EU izvor

**Odobreno od vlasnika 2026-08-19.** Proširuje D-012 na `kleinanzeigen.de`.

Važe iste granice: bez prijave, bez zaobilaženja captcha/rate limita/anti-bot
mera, samo javno vidljiv sadržaj oglasa, tempo ručnog pregleda, `access_method`
ostaje `MANUAL`, svaki zapis nosi URL i vreme.

Ovo **ne** menja `automation_status` konektora — `KleinanzeigenConnector` ostaje
`RESEARCH` i `fetch()` ostaje blokiran compliance gate-om. D-007 (izbor prvog EU
connectora za automatizovan pristup) i dalje čeka proveru ToS-a.

Sačuvan „payload" oglasa je izvod stvarnih čvorova stranice (`#viewad-title`,
`#viewad-price`, `#viewad-description-text`), ne rekonstrukcija: markup je
sajtov, samo sužen na polja koja parser čita.

## D-015 — Standardni troškovi EU uvoza po kartici

**Odobreno od vlasnika 2026-08-19.**

- **Prevoz DE→RS: 25 € po kartici.**
- **Carinski buffer: 0 €** — ne zato što je nepoznat, nego zato što posrednička
  naknada iz D-010 (15 €) već uključuje carinu i PDV. To je odobrena činjenica,
  ne UNKNOWN prećutno pretvoren u nulu (princip 2).

Kako se primenjuje:

- Vrednosti su podrazumevane **samo za uvoz** (`is_import=True`). Domaća
  kupovina nema prevoz dok ga neko ne navede — tamo UNKNOWN i dalje znači
  `INSUFFICIENT_DATA`.
- Konkretan posao sme da ih pregazi: `--shipping-eur` i `--import-buffer-eur`
  imaju prednost nad politikom, isto kao naknada posrednika u D-010.
- **Podložno korekciji** novom odlukom, na izričit zahtev vlasnika. Vrednosti
  stoje u `src/core/policy.py` (`import_shipping_eur`, `import_buffer_eur`), pa
  se menjaju na jednom mestu i putuju kroz `policy_version` uz svaku predikciju.

Zašto je bitno da su odluka a ne podrazumevana vrednost u kodu: svaka
zabeležena predikcija nosi `calculation_version` i `policy_version`, pa se
kasnija promena troška vidi u kalibraciji umesto da tiho pomeri stare rezultate.

## D-016 — Izvori samo iz EU; prevoz 25 € bez obzira na zemlju

**Odobreno od vlasnika 2026-08-19.** Dopunjuje D-015.

- Posrednik pokriva **EU**. Cena prevoza je **ista, 25 € po kartici, za svaku
  EU zemlju** — ne skalira se sa udaljenošću.
- **Vanevropski izvori se ne koriste** dok vlasnik ne proveri da li ih posrednik
  uopšte radi. Konkretno ispadaju Norveška (`finn.no`) i Švajcarska
  (`tutti.ch`): nisu u EU, pa pretpostavka iz D-015 da posrednik pokriva carinu
  i PDV za njih ne važi.

Posledica za pretragu: pošto prevoz ne zavisi od zemlje, izvor se bira **samo po
ceni i riziku**, a ne po blizini. Mađarska i Portugalija su ravnopravne ako je
kartica ista.

## D-017 — Merni prolaz po EU oglasnicima

**Odobreno od vlasnika 2026-08-19.** Ista pravila kao D-012 i D-014, prošireno
na EU oglasnike: `willhaben.at` (AT), `njuskalo.hr` (HR), `bolha.com` (SI),
`hardverapro.hu` i `jofogas.hu` (HU), `olx.ro` (RO), `olx.bg` (BG),
`subito.it` (IT), `2dehands.be` / `marktplaats.nl` (BE/NL).

Svrha ovog prolaza je **merenje ponude i nivoa cena**, ne prikupljanje uzorka:
odgovor na pitanje ima li uopšte jeftinije robe nego u Nemačkoj, pre nego što se
uloži rad u konektore.

Granice ostaju: bez prijave, bez zaobilaženja captcha/rate limita/anti-bot mera,
samo javno vidljiv sadržaj, tempo ručnog pregleda, `access_method=MANUAL`.
Konektori ostaju `RESEARCH`; ovo ne menja `automation_status` nijednog sajta.

## D-018 — Više tržišta: matrica cena i valuta po tržištu

**Odobreno od vlasnika 2026-08-19** (deo koji se tiče poređenja cena).

Sistem više ne gleda samo „nabavka u EU → prodaja u Srbiji". Svako posmatrano
tržište može biti i izvor i izlaz, pa procena cene mora da postoji **po tržištu**,
a ne samo za Srbiju.

Šta je odlučeno i primenjeno:

- **Matrica cena** (`src/pricing/market_matrix.py`, komanda `matrix`): za svaki
  par (proizvod, tržište) računa se ista procena kao za Srbiju — nema drugog,
  labavijeg puta za novac. Ćelija sa premalim uzorkom je `INSUFFICIENT_DATA`.
- **Valuta je svojstvo tržišta.** Prihvata se svaki ispravan troslovni kod, ne
  fiksna lista. Rumunsko tržište koje kotira u RON je samo po sebi konzistentno
  i ne treba mu konverzija da bi se procenilo. Neispravan kod (`XX`) i dalje
  ispada kao `unsupported_currency`.
- **Uzorak se i dalje nikad ne meša** (D-013 ostaje). Valuta uzorka se bira
  unutar tržišta, ne globalno.
- **Razlika između dva tržišta u različitim valutama se ne računa** dok ne
  postoji posmatran kurs. Matrica ne izmišlja kurs (princip 1).
- **Spread nije profit.** Matrica prikazuje bruto razliku (P25 jeftinijeg →
  medijana skupljeg) i to izričito kaže. Nijedan trošak nije oduzet.

### Otvoreno — #čeka-vlasnika i #čeka-provere

Trgovina van koridora EU→RS **nije odobrena** i sistem je ne računa. Pre nego
što bilo koji drugi smer postane predlog za kupovinu, treba odlučiti:

1. **Koridori i troškovi.** D-015/D-016 pokrivaju tačno jedan smer: EU→RS,
   25 € prevoz + 15 € posrednik, carina kroz posrednika. Za RS→EU ili BG→IT ne
   postoji nijedna odobrena cifra. Bez toga se profit ne sme računati.
2. **Pravni i poreski položaj izvoza iz Srbije.** Prodaja fizičkim licima u EU
   iz Srbije nije isto što i uvoz u Srbiju: izvozna carina, PDV, eventualna
   obaveza registracije delatnosti. To je pitanje za knjigovođu, ne za engine.
3. **Naplata i rizik na daljinu.** Prodaja u tuđoj zemlji bez ličnog
   preuzimanja menja rizik prevare i povrata; risk model to trenutno ne pokriva.
4. **Da li se uopšte isplati.** Bruto razlika koju matrica pokaže mora da pređe
   troškove tog koridora, a oni su za sada nepoznati.

## D-019 — Prevoz 25 € u svim smerovima; prikaz uvek u evrima

**Odobreno od vlasnika 2026-08-19.** Radna pretpostavka dok se troškovi ne istraže.

- **Prevoz je 25 € po kartici u svakom koridoru**, ne samo EU→RS: i RS→EU, i
  između dva EU tržišta. Vlasnik je izričito rekao da su stvarni troškovi još
  neistraženi i da ovo stoji privremeno — menja se novom odlukom, a `policy-v3`
  ga nosi uz svaku predikciju, pa se promena vidi u kalibraciji.
- **Posrednička naknada od 15 € (D-010) i dalje važi samo za uvoz u Srbiju**,
  jer je vezana za konkretnog posrednika i njegov posao sa carinom. Za druge
  koridore nije odobrena nijedna naknada; ako je bude, to je nova odluka.
- **Svaki prikaz cene je u evrima.** Iznos u lokalnoj valuti se čuva kao
  posmatran podatak, ali tabela prikazuje EUR jer vlasnik nema osećaj za cenu u
  lejima ili forintama.
  - Konverzija koristi **posmatran kurs iz `data/fx-observations.json`**, sa
    izvorom i datumom. Kurs se ne izmišlja: tržište za koje kurs ne postoji
    prikazuje `-` i razlog, umesto približne cifre.
  - Konvertovan iznos je izveden, ne posmatran, i tako je i označen.

Ovo **ne** odobrava trgovinu van koridora EU→RS. Otvorena pitanja iz D-018
(pravni i poreski položaj izvoza, naplata i rizik na daljinu) i dalje stoje.

## D-020 — Diler cene (dealer_reference) isključene iz P25/medijana/P75 uzorka

**Odobreno od vlasnika 2026-08-24.**

Nalaz: merni prolaz kroz `olx.bg` (D-017) je otkrio da je od 9 upisanih RTX
3080 Ti oglasa 7 od preprodavaca hardvera (dileri: PCFlip.BG, MyPCcamp,
Komputri bg — stranica ih eksplicitno označava kao "Бизнес", za razliku od
"Частна" za privatne prodavce), a samo 2 od privatnih lica. `PriceObservation`
je već imao `dealer_reference` kao poseban `price_type`
(`observation_type` u `data/DATA-MODEL.md`), ali `src/pricing/serbian_market.py`
(koji i `matrix` i srpska procena koriste) ga nije razdvajao od `asking` —
oba su ulazila u isti P25/medijana/P75 račun. Rezultat: olx-bg ćelija u matrici
je bila mešavina privatne i diler cene, a diler cena po pravilu nosi maržu
koju privatni prodavac nema — ista vrsta greške koju D-013 zabranjuje za
valute ("uzorak se nikad ne meša"), samo neprimenjena na tip prodavca.

Odlučeno:

- **`DEALER_REFERENCE` i `MANUAL_REFERENCE` se isključuju iz P25/medijana/P75
  uzorka** za svako tržište (i srpsku procenu i `matrix`). U uzorak i dalje
  ulaze samo `ASKING`, `SOLD`, `COMPLETED`.
- **Opservacije se i dalje čuvaju** (princip 6) — `dealer_reference` ostaje u
  `data/observations/serbia.jsonl`, samo se ne broji u statistiku. Vidljiv je
  u `ResaleEstimate.explanation` kao isključen sa razlogom.
- Razlog za `MANUAL_REFERENCE` isti kao za `DEALER_REFERENCE`: oba su po
  imenu i nameni referentne, ne peer market cene — dosledno se tretiraju
  isto dok ne postoji suprotna odluka.
- Ovo je opšte pravilo, ne specifično za olx.bg — primenjuje se retroaktivno
  na sve postojeće i buduće opservacije na svim tržištima.
