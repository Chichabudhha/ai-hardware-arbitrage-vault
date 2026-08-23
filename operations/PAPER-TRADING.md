# Paper Trading (W6)

> Cilj: izmeriti koliko procena valja **pre** nego što se potroši novac.
> Nijedna komanda ne kupuje. Sistem daje preporuku, vlasnik odlučuje (D-003).

## Šta se meri

Za svaki kandidat beleži se predikcija u trenutku ocene, a kasnije ono što je
tržište stvarno uradilo. Izveštaj poredi to dvoje.

| Zapis | Fajl | Sadržaj |
|---|---|---|
| Opservacija cene | `data/observations/serbia.jsonl` | srpski oglas: proizvod, cena, stanje, datum |
| Predikcija | `data/paper/predictions.jsonl` | landed cost, procena resale-a, profit, ROI, verdikt, confidence |
| Ishod | `data/paper/outcomes.jsonl` | prodato / skinuto / neprodato / snižena cena, i posmatrana prodajna cena |

Sva tri fajla su append-only. Ispravka je nova linija, ne izmena stare
(princip 6). Pokvarena linija diže grešku, ne preskače se.

## Radni tok

### 1. Prikupi srpske opservacije

Pojedinačno:

```bash
python -m src.cli observe --product-id rtx-3090 --price 99000 --currency RSD \
  --marketplace kupujemprodajem --listing-id kp-12345 \
  --url https://www.kupujemprodajem.com/... --condition used
```

Grupno, iz CSV-a (praktičnije za 100 oglasa). Šablon je samo zaglavlje
(`data/observations/template.csv`) — namerno bez primer-reda, da izmišljena
cena ne bi slučajno završila u store-u.

```bash
python -m src.cli observe --csv data/observations/kp-avgust.csv
```

Kolone: `product_id, price_amount, currency, price_type, condition,
observed_at, marketplace, source_listing_id, url, is_bundle`.
Obavezne: `product_id, price_amount, currency, observed_at, marketplace,
source_listing_id`. Red sa neispravnom cenom obara ceo import — bolje nego
polovično popunjen store.

Prikupljanje je MANUAL put: vlasnik čita stvaran oglas i upisuje šta u njemu
piše. Ništa se ne dohvata automatski dok pristup nije proveren (princip 7).

### 2. Proveri procenu za model

```bash
python -m src.cli price --product-id rtx-3090
```

Ispod 5 upotrebljivih uzoraka izlaz je `INSUFFICIENT_DATA`, ne broj sa ogradom.

### 3. Zabeleži predikciju za kandidata

```bash
python -m src.cli predict oglas.html --marketplace kupujemprodajem \
  --listing-id kp-12345 --url https://... \
  --shipping-eur 0 --import-buffer-eur 0 --evaluate
```

Za EU oglas: `--marketplace kleinanzeigen`, stvarni `--shipping-eur`,
`--import-buffer-eur` i po potrebi `--intermediary-fee-eur` (D-010).

Resale strana se **ne kuca ručno** — uzima se iz observation store-a, jer se
meri ona procena koju bi engine stvarno dao.

Predikcija se uvek upisuje, i kad je verdikt `INSUFFICIENT_DATA`. Kandidat koji
nije mogao da se oceni je nalaz, ne otpad.

### 4. Zabeleži ishod kad se oglas zatvori

```bash
python -m src.cli outcome --prediction-id "kupujemprodajem:kp-12345:20260819T120000Z" \
  --outcome SOLD --sale-rsd 105000 --days-listed 12
```

Vrste ishoda:

- `SOLD` — prodaja viđena, sa cenom. Jedino stanje koje sme da nosi cenu.
- `DELISTED` — oglas nestao, cena **UNKNOWN**. Ne upisuje se pretpostavljena cena.
- `UNSOLD` — još stoji na kraju prozora posmatranja.
- `PRICE_CUT` — još stoji, prodavac snizio cenu.

Ako je cena u RSD, potreban je posmatran EUR/RSD kurs u
`data/fx-observations.json`; bez njega komanda vraća `INSUFFICIENT_DATA` umesto
da izmisli konverziju.

### 4b. Lista praćenja

```bash
python -m src.cli watch
python -m src.cli watch --marketplace kupujemprodajem
```

Prati se **svaki** ocenjeni kandidat, ne samo oni vredni kupovine. Oglas koji je
bio preskup pa se ipak proda govori šta tržište stvarno plaća; snižena cena
govori da prodavac nije mogao da dobije traženo. To je jedini izvor signala o
ceni koji sistem inače nema.

Sa liste ispadaju samo `SOLD` i `DELISTED` — to su zaključci. `UNSOLD` i
`PRICE_CUT` su međuizveštaji i oglas ostaje na listi.

Sniženje se beleži sa novom traženom cenom, odvojenom od prodajne:

```bash
python -m src.cli outcome --prediction-id "<id>" --outcome PRICE_CUT   --new-asking 320 --new-asking-currency EUR
```

### 4b-2. Praćenje oglasa koji nisu kandidati za kupovinu

Oglas ne mora da bude kandidat za kupovinu da bi vredeo praćenja. Austrijska
kartica od 499 € ne govori ništa o kupovini, ali sve o tome da li je 499 €
cena koju to tržište stvarno plaća.

```bash
python -m src.cli watch --add willhaben --product-id rtx-3080-ti
python -m src.cli watch --add olx-pl
```

Prati se svaki oglas iz observation store-a za to tržište. Zapis je namerno
tanak: šta, gde, po kojoj traženoj ceni i kad je prvi put viđeno — bez verdikta,
troškova i score-a, jer bi to podrazumevalo odluku o trgovini koja nije doneta.
Isti oglas dodat dvaput je jedan subjekat, ne dva.

Ishodi se beleže istom komandom, sa `watch:` ID-jem umesto ID-ja predikcije:

```bash
python -m src.cli outcome --prediction-id "watch:willhaben:1900028284"   --outcome SOLD --sale-eur 395 --days-listed 9 --record-observation
```

### 4c. Povratna sprega: prodata cena ulazi u procenu

```bash
python -m src.cli outcome --prediction-id "<id>" --outcome SOLD   --sale-eur 395 --days-listed 11 --record-observation
```

`--record-observation` upisuje posmatranu cenu u observation store kao
`price_type=sold`. **Ovo je jedini put da procena pređe sa ASKING na SOLD
osnovu** — bazna confidence raste sa 0,50 na 0,80, a očekivana vrednost
prestaje da bude P25 i postaje medijana stvarno postignutih cena.

Opservacija se upisuje sa **svojim** tržištem. Da nemačka prodaja ne uđe u
srpski uzorak brine estimator (`PricingRules.resale_marketplaces`), ne ova
komanda — tako prodaja u Austriji završi u austrijskoj ćeliji matrice umesto da
bude bačena.

### 5. Izveštaj

```bash
python -m src.cli report
```

Sadrži: broj kandidata i verdikata, ishode, grešku procene (medijana apsolutne i
predznačene greške — pozitivno = precenjeno), grešku profita, hipotetički ROI,
false positive/negative po pragovima iz `src/core/policy.py`, grešku po
confidence opsezima, medijanu dana do prodaje i failure modes.

Izlaz je `INSUFFICIENT_DATA` dok nema **100 kandidata i 20 ishoda sa cenom**.
To nije ograda uz broj — dok se ne skupi, izveštaj nije merenje.

## Gate za W6

- 100+ kandidata sa zabeleženom predikcijom.
- 20+ ishoda sa posmatranom prodajnom cenom.
- Izveštaj sa poznatom greškom procene i izlistanim failure modes.

Tek tada ima smisla pitanje minimalne confidence za BUY (#čeka-vlasnika):
odgovor je merenje iz ovog izveštaja, ne pretpostavka.

## Preduslovi koji trenutno nedostaju

1. ~~Kurs EUR/RSD~~ — rešeno 2026-08-19: radni kurs 120, pa NBS srednji 118 kao
   nova linija. Koristi se najnoviji zapis (118); starija linija se ne briše, jer
   je po njoj računata ranija predikcija. RSD cena oglasa se preračunava u EUR
   inverzijom tog istog kursa, pa se koristi jedan posmatran broj, ne dva.
2. **Evaluacija oglasa** — `--evaluate` traži `ANTHROPIC_API_KEY`. Bez nje u
   `missing_inputs` stoji `evaluation` i nema verdikta.
3. **Sold podaci** — dok postoje samo asking cene, baza je ASKING sa P25
   sidrom i confidence ≤ ~0.65. Izveštaj će to pokazati kao sistematsku
   grešku predznaka, što je i svrha W6.
