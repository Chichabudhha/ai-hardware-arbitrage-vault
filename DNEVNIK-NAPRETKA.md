---
merge: union
---

# DNEVNIK-NAPRETKA — AI Hardware Arbitrage Serbia

> **Append-only.** Nikad ne brisati ili prepisivati stare unose — samo
> dodavati nove na dno (ili na vrh, izaberi konvenciju i drži se nje). Ako
> koristiš Obsidian Git ili sličan auto-sync alat, postavi
> `merge=union` u `.gitattributes` za ovaj fajl da se izbegnu merge
> konflikti kad više izvora (chat + Claude Code + cPanel) pišu isti dan.

Tagovi: `[claude-code]` = lokalni terminal · `[chat]` = chat sesija ·
`[{{live-tag}}]` = rad direktno na produkciji.

Format unosa:
```
## {{YYYY-MM-DD}} `[tag]` — kratak naslov

- Šta je urađeno (bullet lista, konkretno — ne "radio na SEO" nego
  "dodao 3 meta title-a, ispravio 7 404 redirekta")
- Odluke donete i zašto (link na [[odluke/_pregled-odluka]] ako je veća)
- Blokeri otkriveni
- Sledeći korak
```

---

## {{YYYY-MM-DD}} `[claude-code]` — Pokretanje projekta

- Kreirana vault struktura po template-u
- {{...}}

## 2026-08-18 `[claude-code]` — HA-002 faza 1: struktura modula

- Kreirana struktura u `src/`: `core/` (kanonski modeli, Decimal novac,
  provenance), `scrapers/` (KupujemProdajem + Kleinanzeigen + manual import),
  `deal_engine/` (LLM evaluator + deterministički risk), `pricing/`
  (landed cost, profit, ROI, verdikt), `obsidian_sync/` (render DEAL-template).
- Implementiran compliance gate (`scrapers/compliance.py`): oba konektora su
  `RESEARCH`, `fetch()` podiže `ComplianceError`, robots.txt se proverava i
  neuspela provera se tretira kao zabrana.
- **Odstupanje od HA-002 §1:** spec traži "anti-bot mere, proxy rotacija".
  Nije implementirano — kolidira sa `CLAUDE.md` pravilom 7 i compliance gate-om
  u `MARKETPLACE-STRATEGY.md`. Umesto toga: fiksni identifikujući User-Agent,
  rate limit po konektoru (KP 8s, Kleinanzeigen 10s), backoff na 429/5xx i
  MANUAL import kao radni put do verifikacije pristupa.
- LLM evaluator (`claude-opus-5`, structured outputs) vraća samo činjenice i
  risk flag-ove; ne računa novac (D-005). Risk score i sve finansijske
  vrednosti su deterministički Decimal kod.
- Nedostajući finansijski ulaz daje `INSUFFICIENT_DATA` + `missing_inputs`;
  nota renderuje `UNKNOWN`, nikad `0`.
- CLI: `health`, `import`, `note`. 31 test prolazi (`python -m pytest -q`).
- Blokeri (nepromenjeni, blokiraju fazu 2): verifikacija pristupa KP i
  Kleinanzeigen (D-006, D-007), pravila landed cost-a za uvoz, pragovi ROI za
  BUY/NEGOTIATE/WATCH, i procena srpske prodajne cene (pricing engine).
- Zapaženo: `blokovi/DEAL-template.md.md` je duplikat — nije diran.
- Sledeći korak: verifikovati CSS selektore na sačuvanim fixture-ima i doneti
  odluku o pristupu marketplace-ima pre bilo kakve automatizacije.

## 2026-08-18 `[claude-code]` — AI orkestracija (auto mode setup)

- Provereno šta je stvarno dostupno, ne pretpostavljeno: **Copilot CLI radi**
  (autentikovan, headless `-p`). **Grok CLI nije prijavljen** (`grok login
  --device-code`). **Gemini CLI nije instaliran.** **Ollama nema povučen model.**
  Nijedan API ključ nije u okruženju.
- Dodato `.claude/bin/ai-status.sh` (provera provajdera, bez naplativog poziva) i
  `.claude/bin/delegate.sh` (delegacija sa ulogama review/tests/research/docs).
- Delegat radi read-only (`view,glob,grep`, +`web_fetch` za research), dobija
  projektna pravila u promptu i ne može da menja fajlove.
- Zaštita tajni: odbija kredencijale u zadatku i `.env`/`secrets/`/`*.pem`.
  Prvi regex je propustio `sk-ant-...` jer ključevi sadrže crtice — ispravljeno i
  ponovo testirano na 4 obrasca, svi blokirani.
- Provenance: svaki poziv u `operations/ai-delegacija-log.jsonl` (vreme, provajder,
  uloga, fajlovi, hash prompta, exit kod, putanja izlaza).
- Politika u `operations/AI-ORKESTRACIJA.md` + `CLAUDE.md` sekcija 7. Ne delegira
  se obračun novca, compliance procena, `odluke/`, izmene fajlova ni commit.
- **Prvi delegirani review je našao 2 stvarna buga** (od 6 nalaza):
  - FX kurs `<= 0` je vodio u deljenje nulom → `FxRate` sada odbija nepozitivan
    kurs, `load_rates` diže `InsufficientData` na pokvaren zapis.
  - `expected_sale_rsd` se zaokruživao na 2 decimale (EUR logika) → uveden
    `round_units` jer se RSD plaća u celim dinarima.
  Ostala 4 nalaza su bila lažno pozitivna ili kozmetička.
- Delegirani predlozi testova dodali 3 granična slučaja za risk scoring
  (prag HIGH na 6 poena, `match_confidence == 0.6` isključiv, FOR_PARTS).
- Testovi: 31 → 38, svi prolaze.
- Cena: Copilot ~0.36 kredita za trivijalan poziv, ~2.14 za review tri modula.
- Sledeći korak: `grok login --device-code` ako se želi drugi provajder;
  i dalje blokira W0 — pragovi i verifikacija marketplace pristupa.

## 2026-08-18 `[claude-code]` — Deterministički product_match

- Povučeni lokalni modeli: `nomic-embed-text` i `qwen3:4b`. Qwen nije imao
  problem sa serverom — ollama je tražila 20.1 GiB jer podrazumevano alocira
  KV cache za pun kontekst (qwen3 ima 256K). Sa `num_ctx: 8192` radi,
  ~13.4 tok/s na CPU-u (MX450 ima 2 GB VRAM, nema realnog offload-a).
- **Embeddings testirani i odbačeni za product matching.** Izmereno:
  3090 vs 3080 = 0.930 sličnosti, isti proizvod drukčije formulisan = 0.708.
  Model hvata površinski tekst, ne značenje broja modela. Lekcija upisana u
  `reference/naucene-lekcije.md`.
- Implementiran `src/products/`:
  - `catalog.py` — 7 modela iz `PRODUCT-INTELLIGENCE.md`. HA-002 pominje i
    4080 Super, 4070 Ti Super, V100 i A100 — **namerno nisu dodati**, širenje
    kataloga je odluka za `odluke/` (princip 9).
  - `matcher.py` — regex preko kanonskog kataloga, sa: shadowing-om (3090 Ti
    pobeđuje nad 3090), zaštitom od cene ("cena 3090 din" nije model),
    zahtevom za brand token kod golih brojeva, VRAM cross-check-om i
    normalizacijom dijakritike/spojenih naziva (`RTX-3090Ti`).
  - `ai_relevance_score` se **izvodi** iz VRAM-a, nije ručno dodeljen broj.
- Pet stanja po specifikaciji: MATCHED, LOW_CONFIDENCE, CONFLICT, UNMATCHED,
  REVIEW_REQUIRED. Match se nikad ne forsira.
- `RTX 3090 12GB` daje **CONFLICT**, ne tihi match — to je ili greška prodavca
  ili prevara, i mora ručno u pregled.
- Gate: `build_opportunity` sada zahteva `MATCHED`, inače `INSUFFICIENT_DATA`
  sa `product_match:<STATUS>` (`CLAUDE.md` §5 traži product match kao obavezan
  atribut za finansijski zaključak).
- `reconcile_with_llm`: katalog pobeđuje nad LLM procenom čipa i VRAM-a,
  neslaganje se upisuje u `risk_notes` umesto da se sakrije.
- CLI: dodata komanda `match`. Testovi: 38 → 63, svi prolaze.
- Sledeći korak: proceniti da li 4080 Super / V100 / A100 idu u katalog
  (traži odluku), i dalje blokira W0 — pragovi i verifikacija pristupa.

## 2026-08-18 `[claude-code]` — Ispravke matchera + stanje provajdera

- Delegirani review matchera: Copilot dao 4 nalaza, **verifikacijom potvrdjen 1**
  (RAM iz bundle oglasa se citao kao VRAM). Dva nalaza empirijski oborena
  (dijakritika i tacka posle "Ti" rade ispravno), jedan kozmeticki.
  Potvrdjeno i da je `SELF_IDENTIFYING` bio mrtav kod — uklonjen.
- Popravljena dva stvarna buga u `product_match`:
  - **Bundle oglas** "RTX 3090 24GB + 32GB RAM" davao je lazni CONFLICT jer se
    uzimala najveca navedena velicina. Sada se skupljaju sve vrednosti i konflikt
    postoji samo ako *nijedna* ne odgovara katalogu.
  - **Ti oglas koji pominje obicnu karticu** ("bolja od obicne 3090") davao je
    CONFLICT. Sada: identitet se cita iz naslova, opis sluzi samo za VRAM, a
    kolaps 3090/3090 Ti daje **REVIEW_REQUIRED** (peto stanje iz specifikacije),
    ne tihi izbor.
- Testovi: 63 → 65, svi prolaze.
- Provajderi: Copilot radi (krediti). Grok prijavljen ali **pao na free limitu** —
  bitno: popravljeni log je taj neuspeh ovog puta zabelezio (`exit_code: 1`),
  ranije bi zapis potpuno nedostajao.
- Codex CLI 0.147.0 instaliran, **autorizacija ne prolazi** (browser OAuth vraca
  "Login cancelled", `codex login status` = Not logged in). Nije dodat u
  `delegate.sh` dok se prijava ne resi; probati `codex login --device-auth`.
- Sledeci korak: W0 odluke (ROI pragovi, kapital, landed cost) — bez njih svaki
  deal ostaje INSUFFICIENT_DATA.

## 2026-08-19 `[claude-code]` — W0 zatvoren: poslovni pragovi u kodu

- **Vlasnik doneo 4 odluke** koje su blokirale sve od 18.08: D-008 (kapital
  1.000 €, max 500 € po kupovini), D-009 (BUY = ROI ≥ 18% I profit ≥ 50 €),
  D-010 (nabavka iz EU preko posrednika), D-011 (katalog + 4080 Super i
  4070 Ti Super, V100/A100 odbijeni). Sve upisane u `odluke/_pregled-odluka.md`
  sa obrazloženjem.
- Novi `src/core/policy.py` — pragovi izvučeni iz kalkulatora u zasebnu,
  validiranu `Policy` dataclass. `__post_init__` odbija obrnut redosled pragova,
  nepozitivan kapital i limit veći od kapitala.
- **Uklonjene tvrdo kodirane vrednosti 25/12/5% ROI** iz
  `src/pricing/calculator.py` — stajale su tamo kao neodobrena pretpostavka sa
  komentarom "vlasnik mora da potvrdi".
- `decide()` sada traži **oba** praga za BUY (ROI i apsolutni profit). Ranije je
  40% ROI na kartici od 100 € (= 40 € profita) prolazilo kao BUY.
- **Budžetski gate:** kupovina iznad 500 € ne može da dobije BUY ni sa odličnom
  ekonomijom — degradira na NEGOTIATE, jer ciljna cena može da je vrati u budžet.
  Fixture od 620 € u testu se sada ponaša tačno tako.
- D-010 u landed cost: `intermediary_fee_eur` je obavezan kad je `is_import`,
  nedostatak daje `INSUFFICIENT_DATA`. Domaća kupovina nosi 0 kao činjenicu, ne
  kao zamenu za UNKNOWN. Dodat CLI flag `--intermediary-fee-eur`.
- `calculation_version` je sada `calc-v2/policy-v1` — provenance beleži i verziju
  poslovne politike, ne samo formule.
- Katalog: 7 → 9 modela. Obična 4080 i obična 4070 Ti ostaju `UNMATCHED`
  (ne spajaju se tiho sa Super varijantom), V100/A100 takođe.
- **Delegirani review (Copilot, 1.02 kredita):** 5 nalaza, **nijedan stvarni bug**.
  Nalaz o deljenju nulom kod `eur_rsd.rate == 0` empirijski oboren — `FxRate` to
  već odbija od ranije. Ostala 3 nalaza opisuju namerno ponašanje, jedan je
  primedba na ugovor pozivaoca.
- **Grok pao na free limitu** po drugi put uzastopno (`exit_code: 1` u logu).
  Kao izvor saveta je nepouzdan dok se ne plati.
- Testovi: 65 → 81, svi prolaze.
- Ažurirano: `DEAL-ENGINE.md` (tabela pragova + intermediary_fee),
  `PRODUCT-INTELLIGENCE.md` (9 modela + zašto V100/A100 nisu tu).
- **Otvoreno #čeka-vlasnika:** (1) konkretna visina posredničke naknade —
  fiksna ili procenat; (2) potvrda da su NEGOTIATE 9% / WATCH 4% u redu, jer su
  izvedeni iz odnosa starog seta, a ne izabrani.
- Sledeći korak: W4 — srpski pricing engine. Bez `expected_sale_rsd` svaki deal
  je i dalje `INSUFFICIENT_DATA`, a taj ulaz sada nema ko da proizvede.

## 2026-08-19 `[claude-code]` — W4: srpski pricing engine

- **Potvrđeno od vlasnika:** posrednička naknada je **fiksnih 15 €** (D-010),
  pragovi NEGOTIATE 9% / WATCH 4% ostaju kako su izvedeni (D-009). Oba
  #čeka-vlasnika zatvorena.
- Naknada je sada u `Policy.intermediary_fee_eur`, pa uvoz bez navedene naknade
  koristi odobrenih 15 € umesto da bude `INSUFFICIENT_DATA`. `CostInputs` i
  dalje može da prebriše kad posrednik za konkretan deal traži drugu cenu.
- **Novi `src/pricing/serbian_market.py` (`pricing-v1`)** — W4 gate prošao.
- **Ključno pravilo:** asking cena nije prodajna cena, a razmak između njih niko
  ovde nije izmerio. Umesto izmišljenog popusta, ASKING i MIXED uzorak vraćaju
  **P25** kao `resale_expected` — to je *posmatrana* vrednost na donjem kraju
  distribucije, ne procena. SOLD uzorak koristi medijanu. Konzervativnost dolazi
  iz podataka, ne iz pretpostavke.
- 8 pravila isključenja, svako logovano sa ID-jem oglasa, cenom i razlogom:
  drugi proizvod, ne-RSD valuta, bundle, for_parts, pogrešno stanje, cena ≤ 0,
  starije od 90 dana, i Tukey 1.5x IQR outlier. Ništa ne nestaje tiho.
- Bait oglas ("3090 za 1000 din, pozovite") sada pada kroz IQR ogradu i ne vuče
  procenu naniže — test to pokriva eksplicitno.
- Uzorak manji od 5 daje `INSUFFICIENT_DATA` i **nijedan broj** — ni P25, ni
  medijanu, ni confidence. UNKNOWN nije 0.
- Confidence je deterministička formula (baza po tipu podataka, bonus za
  veličinu uzorka, kazna za rasipanje i starost), opseg 0-1.
- `src/pricing/observations.py` — JSONL store, append-only. Pokvarena linija
  **diže grešku umesto da se preskoči**: tiho ispuštena opservacija pomera svaki
  percentil koji je od nje zavisio.
- Povezano sa deal engine-om: `build_opportunity` prima `ResaleEstimate` i nosi
  `price_basis`, `pricing_confidence` i `pricing_sample_size` na `Opportunity`.
  Neupotrebljiva procena blokira deal sa `resale:<razlog>`, bez fallback-a.
- CLI: nova komanda `price --product-id ... --observations ...`.
- **Delegirani review (Copilot, 2 poziva, ~2.1 kredita):** od 6 nalaza **1 stvarni**.
  `percentile()` sa `fraction` van [0,1] nije bacao izuzetak nego **tiho
  ekstrapolirao** — vraćao bi cenu koju nijedna opservacija ne podržava. Dodata
  validacija. Drugi prihvaćen nalaz: `PricingRules(full_sample_size=0)` je
  prolazio i pucao tek usred računanja — sada `__post_init__` odbija.
  Nalaz o deljenoj `excluded` listi **oboren** — pydantic kopira listu pri
  validaciji, provereno.
- Testovi: 83 → 140, svi prolaze.
- **Otvoreno #čeka-vlasnika:** minimalna confidence za BUY. `DEAL-ENGINE.md`
  traži prag, ali nisam ga izmislio — trenutno confidence putuje uz verdikt bez
  da ga blokira.
- **Otvoreno #čeka-definicije:** izvor sold/completed podataka u Srbiji. Dok ga
  nema, svaka procena je ASKING baza sa confidence ≈ 0.5-0.65.
- Sledeći korak: W6 paper trading — prikupiti stvarne srpske oglase kroz MANUAL
  import i izmeriti koliko procena valja pre trošenja novca.

## 2026-08-19 `[claude-code]` — W6: paper trading alat (predikcije, ishodi, kalibracija)

- Novi modul `src/paper/`: `records.py` (PaperPrediction snapshot Opportunity-ja
  + PaperOutcome), `store.py` (append-only JSONL, spajanje predikcija i ishoda),
  `calibration.py` (deterministički izveštaj o preciznosti).
- Nove CLI komande: `observe` (pojedinačno i `--csv` za grupni unos),
  `predict` (ocena kandidata + zapis predikcije), `outcome` (ishod oglasa),
  `report` (kalibracioni izveštaj).
- Pravila koja su ugrađena, ne izmišljena: samo `SOLD` ishod sme da nosi cenu —
  `DELISTED` je UNKNOWN, ne nula; izveštaj vraća `INSUFFICIENT_DATA` dok nema
  100 kandidata i 20 ishoda sa cenom; false positive/negative se mere po
  pragovima iz `src/core/policy.py` (D-008/D-009), ne po novim brojevima.
- `observations_from_csv`: grupni unos srpskih oglasa; loš red obara ceo import
  umesto da ostavi polovično popunjen store.
- `delegate.sh` dobio `ollama` i `gemini` provajdere; `auto` redosled je sada
  ollama → gemini → copilot → grok (prvo besplatno i lokalno).
- Delegiran review na ollama — pao: `qwen3:4b` sa podrazumevanim kontekstom
  traži ~20 GiB RAM-a, dostupno ~8,8 GiB. Review prebačen na copilot.
- Od 6 nalaza copilot review-a, 2 potvrđena i popravljena: ROI se poredi sa
  pragom pre zaokruživanja (0.17999 više ne prolazi kao 0.18), i medijana dana
  do prodaje se zaokružuje naviše umesto da se seče. Ostala 4 su bila lažno
  pozitivna (`statistics.median` nad Decimal ostaje Decimal; identitet Enum-a
  preživi pydantic round-trip; grana za over/underestimate radi kako je
  namenjena).
- Testovi: 140 → 165, svi prolaze. E2E provera CLI lanca odrađena na scratch
  fajlovima, ne u vault podacima.
- Blokeri za prve stvarne predikcije: nema posmatranog EUR/RSD kursa u
  `data/fx-observations.json` (svaka predikcija završi kao
  `INSUFFICIENT_DATA: fx_eur_rsd`) i nema `ANTHROPIC_API_KEY` za
  `predict --evaluate`.
- Sledeći korak: napuniti `data/observations/serbia.jsonl` stvarnim srpskim
  oglasima (RTX 3090 prvi) po postupku iz `operations/PAPER-TRADING.md`.

## 2026-08-19 `[claude-code]` — Kurs EUR/RSD upisan

- Vlasnik dao radni kurs 1 EUR = 120 RSD; upisan u `data/fx-observations.json`
  sa izvorom i datumom (nije NBS srednji kurs, i tako piše u `source`).
- `fx.py` dobio `inverted()` i `rate_to_eur()`: RSD cena oglasa se prevodi u EUR
  inverzijom istog posmatranog kursa, sa istim timestamp-om i naznakom da je
  izvedena. Nema drugog broja koji bi izgledao nezavisno posmatran.
- `predict` i `note` sada prosleđuju `purchase_fx`, pa domaći RSD oglas više ne
  pada na `fx_rsd_eur`.
- Testovi 165 → 168. Preostali bloker za verdikt: `ANTHROPIC_API_KEY`
  (`predict --evaluate`).

## 2026-08-19 `[claude-code]` — NBS kurs 118 kao nova linija

- `data/fx-observations.json` ima sada dve linije: radni kurs 120 (00:00Z) i NBS
  srednji 118 (12:00Z). `latest_rate` bira noviji, pa se računa po 118.
- Stara linija namerno ostaje: predikcija zabeležena pre ovoga računata je po
  120 i mora da ostane objašnjiva (princip 6).
- Provera: 89.900 RSD → 761,86 € (bilo 749,17 € po kursu 120). 168 testova prolazi.

## 2026-08-19 `[claude-code]` — .env kreiran; ključ se sada stvarno učitava

- Kreiran `.env` iz `.env.example` (u `.gitignore`, prazan `ANTHROPIC_API_KEY` —
  vrednost upisuje vlasnik, ne prolazi kroz chat ni log).
- Otkriven propust: `python-dotenv` je bio u zavisnostima, ali ga niko nije
  pozivao. `anthropic.Anthropic()` čita `ANTHROPIC_API_KEY` iz okruženja, pa
  ključ upisan u `.env` do sada **ne bi bio pročitan** — a `src/README.md` je
  tvrdio suprotno. `main()` u `src/cli.py` sada radi `load_dotenv(override=False)`
  (eksplicitno izvezena promenljiva iz shell-a i dalje pobeđuje).
- Provereno privremenim lažnim ključem: promenljiva stiže do procesa; .env vraćen
  na prazno. 168 testova prolazi.

## 2026-08-19 `[claude-code]` — Prvi pun prolaz kroz `predict --evaluate`

- Ključ prenet iz `C:\Projekti\API keys\api-key-kp.txt` u `.env` skriptom koja
  vrednost nije ispisala (proverena samo dužina i prefiks).
- `predict --evaluate` prošao ceo lanac na test-fajlu: match MATCHED (rtx-3090),
  landed cost 761,86 €, resale 845,34 €, profit 83,48 €, ROI 10,96 %,
  risk Low → verdikt **NEGOTIATE**, `missing_inputs` prazno.
- Verdikt je tačan po D-009: profit prelazi 50 €, ali ROI 10,96 % je ispod BUY
  praga od 18 % i iznad NEGOTIATE praga od 9 %.
- Napomena: brojevi su iz test-fixtura (izmišljen oglas + 6 opservacija u
  scratch fajlu), nisu tržišni podatak. Vault store-ovi nisu dirani.

## 2026-08-19 `[claude-code]` — Prvo prikupljanje sa KupujemProdajem (D-012)

- Pregledano ~60 oglasa u kategoriji Grafičke kartice za „rtx 3090" (4 strane) +
  provere za „3090", „aorus 3090", „rtx 4090". Bez prijave, bez zaobilaženja.
- Upotrebljivo je **3 oglasa**: gola polovna kartica, jasna cena, jedan komad.
  780 € (MSI Ventus, #194251380), 800 € (EVGA FTW3 Ultra, #194294192),
  750 € (Gigabyte AORUS Xtreme Waterforce, #192218883). Sva tri MATCHED rtx-3090.
- Odbačeno i zašto: „Kupujem/Otkup" oglasi (tražnja, ne ponuda), gotovi
  računari, kuleri i vodeni blokovi, prodavnički oglasi novih kartica iz 2021
  (2.000-3.500 €, zastareli), i #190468494 gde opis protivreči sam sebi
  („CENA ZA JEDNU ... ZA OBE"), pa cena nije jednoznačna.
- Nalaz o tržištu: golih polovnih 3090 na KP trenutno ima jedva 3; za 4090 na
  prvoj strani nema nijedne gole polovne kartice, samo prodavnice i laptopovi.
- **Blokada u pravilu, ne u kodu:** sva tri oglasa su u evrima, a
  `serbian_market.py` po `PRICING-ENGINE.md` odbacuje sve što nije RSD
  (`non_rsd_currency:EUR`). Procena je zato `INSUFFICIENT_DATA` uz 3 od 3
  isključena. Pravilo pretpostavlja da srpsko tržište kotira u dinarima — za
  grafičke kartice to nije tačno. Traži odluku vlasnika (predlog D-013), nije
  menjano samoinicijativno.
- Opservacije su svejedno upisane u `data/observations/serbia.jsonl` sirove,
  onakve kakve su viđene (EUR), sa URL-om i vremenom.

## 2026-08-19 `[claude-code]` — D-013: EUR prihvaćen kao valuta srpske opservacije

- Vlasnik odobrio prvu opciju: EUR je validna srpska opservacija, bez konverzije.
- `serbian_market.py`: `SUPPORTED_CURRENCIES = {RSD, EUR}`, `pick_sample_currency()`
  bira valutu po broju opservacija (nerešeno → EUR, deterministički), a ostale
  se isključuju kao `currency_not_sample:<VAL>`. Treća valuta i dalje ispada
  (`unsupported_currency`). Uzorak se nikad ne meša.
- `calculator.py`: procena u evrima se koristi kakva jeste; EUR/RSD kurs se
  traži samo kad je nešto u poslu u dinarima. `expected_sale_rsd` ostaje prazno
  kod EUR procene umesto da nosi konvertovan broj koji izgleda posmatrano.
- `PRICING-ENGINE.md` i `odluke/_pregled-odluka.md` (D-013) ažurirani.
- Testovi 168 → 175. Tri KP opservacije sada prolaze filter; procena je i dalje
  `INSUFFICIENT_DATA`, ali sada iz pravog razloga: `sample_size_below_5`.

## 2026-08-19 `[claude-code]` — Prikupljanje prošireno na više modela; prva prava procena

- Pregledani svi modeli iz kataloga (D-011) na KupujemProdajem, kategorija
  Grafičke kartice. Rezultat po modelu:
  - **RTX 3080 Ti — 9 polovnih golih kartica, 350-440 €.** Jedini model sa
    uzorkom preko minimuma. Svih 9 potvrđeno otvaranjem oglasa
    („Korišćeno (polovno)").
  - RTX 3090 — 3.
  - RTX 4080 Super — 2 polovne (950 i 1.150 €); ostalo prodavnice.
  - RTX 4070 Ti Super — 1. RTX 4090, 3090 Ti, A4000, A5000, A6000 — nijedna
    gola polovna kartica; sve su prodavnički oglasi novih, laptopovi ili
    zastareli oglasi iz 2021-22.
- **Prva prava srpska procena preprodajne cene:**
  `rtx-3080-ti`, used, EUR — P25 **380**, medijana 390, P75 410, n=9,
  basis ASKING, confidence **0.55**.
- Store ima 15 opservacija. Jedan oglas (Inno3D 3080 Ti #183165180) upisan sa
  `condition=UNKNOWN` jer stranica ne navodi stanje — engine ga isključuje iz
  „used" uzorka umesto da pretpostavi.
- CSV import je odbio ceo fajl zbog `condition=unknown` (mala slova) i ništa
  nije upisao dok nije ispravljeno — ponašanje kakvo treba.
- Zaključak za W6: RTX 3080 Ti je jedini model gde srpsko tržište trenutno daje
  merljiv uzorak. Fokus paper tradinga ide na njega, 3090 i 4080 Super se
  dopunjuju kako oglasi stižu.

## 2026-08-19 `[claude-code]` — EU strana: Kleinanzeigen (D-014)

- Odobren Kleinanzeigen kao EU izvor pod istim granicama kao KP (D-014).
  `automation_status` konektora ostaje `RESEARCH`; ovo je MANUAL put.
- Nemački 3080 Ti: 24 oglasa, raspon 245-600 €. Izbačeni „Suche" oglasi
  (tražnja) i defektne kartice.
- Tri kandidata sačuvana u `data/listings/kleinanzeigen/`:
  - #3488582404 — ASUS TUF 3080 Ti OC 12GB, **245 €**, račun 01/2025, garancija
    do 2027, privatna prodaja.
  - #3488481508 — EVGA 3080 Ti AIO, **300 €**, „Sehr Gut".
  - #3483853282 — PNY XLR8 3080 Ti, **350 €**, OVP, „Sehr Gut".
  Sva tri matcher prepoznaje kao `rtx-3080-ti` (VRAM 12 GB pročitan iz oglasa).
- Sačuvani fajl je tekst oglasa smešten u čvorove koje parser čita
  (`#viewad-title`, `#viewad-price`, `#viewad-description-text`,
  `#viewad-locality`) — ekstrakt sadržaja, ne bajt-kopija stranice. Ekstenzija
  je blokirala čitanje sirovog HTML-a kao „cookie/query string data", pa je
  uzet tekstualni sadržaj.
- **Break-even prema srpskoj proceni od 380 € (P25, n=9)**, uz posrednika 15 €:

  | oglas | cena | max prevoz+carina za BUY | za NEGOTIATE |
  |---|---|---|---|
  | #3488582404 | 245 € | 49 € (Low risk) / nikad (Medium) | 76 € |
  | #3488481508 | 300 € | nikad | 18 € |
  | #3483853282 | 350 € | nikad | nikad |

  Ovo nije predikcija nego skeniranje pragova iz `policy.py` — prevoz i carina
  su i dalje UNKNOWN, pa ništa nije upisano u paper store.
- Zaključak: samo najjeftiniji oglas ima prostora za BUY, i to ako ukupan
  prevoz + carina stanu u ~49 € i rizik ispadne Low. Prag je uzak jer je srpska
  procena ASKING-bazirana P25, tj. namerno konzervativna.

## 2026-08-19 `[claude-code]` — D-015 i prve prave predikcije

- Vlasnik dao troškove: **prevoz 25 € po kartici, carinski buffer 0 €** jer
  posrednička naknada (D-010, 15 €) već uključuje carinu i PDV. Upisano kao
  D-015, uz izričitu napomenu da je podložno korekciji.
- Implementirano kao politika, ne kao podrazumevana vrednost u računici:
  `Policy.import_shipping_eur` i `Policy.import_buffer_eur`, sa `resolved_*`
  metodama po uzoru na naknadu posrednika. Važi **samo za uvoz** — domaća
  kupovina bez navedenog prevoza i dalje daje `INSUFFICIENT_DATA`, jer za nju
  nijedan trošak nije odobren.
- `POLICY_VERSION` podignut na `policy-v2`. Svaka predikcija nosi
  `calc-v2/policy-v2`, pa će se buduća korekcija troška videti u kalibraciji
  umesto da tiho pomeri stare rezultate.
- **Prve tri prave predikcije upisane u `data/paper/predictions.jsonl`:**

  | oglas | cena | landed | resale | profit | ROI | rizik | verdikt |
  |---|---|---|---|---|---|---|---|
  | #3488582404 ASUS TUF | 245 € | 304,60 € | 380 € | +75,40 € | 24,75 % | Medium | **NEGOTIATE** |
  | #3488481508 EVGA AIO | 300 € | 355,00 € | 380 € | +25,00 € | 7,04 % | Low | WATCH |
  | #3483853282 PNY XLR8 | 350 € | 407,50 € | 380 € | −27,50 € | −6,75 % | Low | SKIP |

- ASUS prelazi oba BUY praga (ROI 24,75 % > 18 %, profit 75,40 € > 50 €), ali je
  rizik Medium pa `decide()` spušta na NEGOTIATE — pravilo iz D-009. Rizik je
  Medium zbog opisa: privatna prodaja bez povraćaja, plaćanje isključivo
  „PayPal Freunde" (bez zaštite kupca).
- Testovi 175 → 177. Kalibracioni izveštaj radi nad stvarnim zapisima:
  3 kandidata, 0 ishoda, status `INSUFFICIENT_DATA` (treba 100 i 20).

## 2026-08-19 `[claude-code]` — Lista praćenja i povratna sprega prodatih cena

- D-016: izvori samo iz EU, prevoz 25 € isto za svaku zemlju → izvor se bira po
  ceni i riziku, ne po blizini. Norveška i Švajcarska van opsega dok se ne
  proveri pokrivenost posrednika.
- **`watch` komanda**: svi ocenjeni kandidati koji čekaju ishod, najstariji prvi.
  Prati se i ono što je SKIP — oglas koji je bio preskup pa se ipak proda je
  najjasniji dokaz šta tržište plaća. Sa liste ispadaju samo SOLD i DELISTED.
- **`PRICE_CUT` sa novom traženom cenom** (`--new-asking`), odvojeno od prodajne
  cene: „prodavac sad traži manje" se ne sme čitati kao „prodato".
- **`outcome --record-observation`**: posmatrana prodajna cena se upisuje u
  observation store kao `price_type=sold`. To je jedini put kojim procena prelazi
  sa ASKING (bazna confidence 0,50, sidro P25) na SOLD osnovu (0,80, medijana).
  Rupa koja je stajala otvorena od W4 sada ima mehanizam.
- **Zaštita koja je nedostajala:** `PricingRules.resale_marketplaces` — strani
  oglas se isključuje iz srpskog uzorka (`non_resale_marketplace:kleinanzeigen`).
  Bez toga bi povratna sprega ubacila nemačke cene u srpsku procenu čim prvi
  EU oglas bude prodat.
- Provereno na scratch store-u: srpski SOLD upisan, nemački odbijen uz obrazloženje.
- Testovi 177 → 184.

## 2026-08-19 `[claude-code]` — Merni prolaz po EU izvorima: Austrija otpada

- D-017: odobren merni prolaz po EU oglasnicima, ista pravila kao D-012/D-014.
- **Austrija (`willhaben.at`): otpada.** 80 oglasa za 3080 Ti, ali gole kartice
  su 499-550 €, a ostalo su gotovi računari (1.100-1.650 €). Najjeftinija gola
  kartica je iznad srpske preprodajne procene od 380 € — i pre troška dopreme.
  Nije stvar marže nego smera: izvor je skuplji od izlaza.
- Zapažanje: nemačko tržište je jeftino zato što je duboko. Pošto je prevoz po
  D-016 isti za svaku EU zemlju, blizina malog tržišta ne donosi ništa.
- **Prepreka:** Chrome ekstenzija blokira navigaciju na nove domene
  (`njuskalo.hr`, `olx.ro` odbijeni). Dozvoljeni su samo kupujemprodajem,
  kleinanzeigen i willhaben. Vlasnik mora da odobri svaki domen u ekstenziji.
- Cookie baneri: vlasnik odobrio politiku „odbij nebitne, svuda". Na willhaben-u
  kliknuto „Ablehnen und Schließen", ne „akzeptieren".
- Nalazi upisani u `research/eu-izvori-merni-prolaz.md`, uključujući prag:
  pri 40 € troška dopreme nabavna cena mora biti ispod ~290 € da bi kartica
  prošla oba BUY praga.

## 2026-08-19 `[claude-code]` — Merni prolaz završen: Nemačka je jedini izvor

- Izmereno pet EU tržišta za RTX 3080 Ti, gole polovne kartice, protiv praga od
  **290 €** (iznad toga BUY ne prolazi pri 40 € dopreme i resale procenu 380 €):

  | Zemlja | Najjeftinija | Ispod praga |
  |---|---|---|
  | Nemačka | 245 € | **da**, više komada |
  | Hrvatska | 300 € | ne |
  | Italija | 350 € | ne |
  | Austrija | 499 € | ne |
  | Rumunija | ~2.200 lei | ne |
  | Mađarska | 195.000 Ft | ne |

- Za HUF i RON nije izmišljan kurs: umesto konverzije zapisano je koliki bi kurs
  morao da bude da cena padne ispod praga (672 HUF/€, 7,6 RON/€) — očigledno van
  stvarnog opsega.
- **Zaključak: širenje na više zemalja ne rešava tanku maržu.** Prednost nije
  blizina (prevoz je isti po D-016) nego dubina tržišta — Nemačka ima donji rep
  cena, mala tržišta ga nemaju. Paper trading ostaje na nemačkim oglasima.
- Usput: obična RTX 3080 (nije u katalogu, D-011) je u Mađarskoj česta i jeftina
  (70.000-158.500 Ft). Razlog da se pogleda ako se katalog ikad širi — ali to je
  nova odluka, nije uzeto zdravo za gotovo.
- Blokirani domeni ostaju `bolha.com` i `olx.bg`; nisu prioritet jer prate isti
  obrazac malih tržišta.
- Cookie baneri odbijeni na willhaben i hardverapro („Ablehnen", „Nem fogadom el").

## 2026-08-19 `[claude-code]` — Generički MANUAL konektor

- `src/scrapers/generic.py`: `SiteProfile` + `GenericManualConnector`. Novi
  oglasnik je sada **red u `marketplace/sites.json`**, ne nova klasa.
- Selektori sajta se probaju prvi, pa zajednički fallback (`h1`,
  `[class*=price]`, `[class*=description]`…). Nenađeno polje ostaje `None`.
- Dve stvari koje profil namerno ne može:
  1. Ne može da dobije automatizovan pristup — konektor je uvek `MANUAL` i
     `UNVERIFIED` bez obzira šta u JSON-u piše. Test to i proverava tako što
     pokuša da podmetne `automation_status: AUTOMATED`. Prelaz na automatiku je
     odluka u `odluke/`, ne polje u konfiguraciji.
  2. Ne može da pregazi ručno pisan konektor — registry uvek bira
     `kupujemprodajem` i `kleinanzeigen` parsere ispred profila.
- Loš profil odbija ceo fajl (isti princip kao CSV import i JSONL store).
- Upisano 5 profila iz mernog prolaza: willhaben, njuskalo, subito, olx-ro,
  hardverapro — sa nalazom o cenama u `notes`, da se zna zašto se ne koriste.
- Ispravljeno usput: `DEFAULT_SITES` se više ne vezuje kao podrazumevani
  argument nego se razrešava u pozivu, pa se putanja može promeniti bez
  ponovnog uvoza modula.
- Testovi 184 → 194 (`tests/test_generic_connector.py`).

## 2026-08-19 `[claude-code]` — Matrica cena po tržištima (D-018)

- Nova ideja vlasnika: trgovina nije samo EU→RS; može i prodaja iz Srbije u EU,
  ili između dva EU tržišta. Za to prvo treba **videti** razlike.
- `src/pricing/market_matrix.py` + komanda `matrix`: tabela (proizvod × tržište)
  sa n, valutom, P25/medijanom/P75 i confidence, plus bruto razlike između
  tržišta. Svaka ćelija je **isti** estimator kao srpska procena, samo uperen u
  jedno tržište — nema drugog puta za novac.
- Prvi stvarni prikaz, sa 17 opservacija u store-u:

  | proizvod | tržište | n | P25 | med | P75 | conf |
  |---|---|---|---|---|---|---|
  | rtx-3080-ti | kleinanzeigen | 8 | 338 | 425 | 463 | 0.50 |
  | rtx-3080-ti | kupujemprodajem | 9 | 380 | 390 | 410 | 0.55 |

  Bruto: kupi DE P25 338 → prodaj RS medijana 390 = **+52 €** (15,4 %).
  Obrnuto: kupi RS P25 380 → prodaj DE medijana 425 = **+45 €** (11,8 %).
  Nijedan trošak nije oduzet — to je bruto razlika, ne profit.
- **Valuta je sada svojstvo tržišta** (D-018): prihvata se svaki ispravan
  troslovni kod umesto fiksne liste RSD/EUR, jer rumunsko tržište u RON ne
  treba konverziju da bi bilo procenjeno samo za sebe. Uzorak se i dalje ne
  meša, a razlika između dve valute se ne računa bez posmatranog kursa.
- Zatečena greška pri pisanju: valuta uzorka se birala globalno, pa bi RON
  tržište izgubilo od EUR većine i prijavilo praznu ćeliju. Sada se bira unutar
  tržišta. Test to pokriva.
- Popravljen i Unicode pad: strelica u ispisu ruši cp1250 konzolu, ispis je sada
  ASCII.
- Upisano 8 nemačkih opservacija (245-599 €). Provereno da srpska procena
  ostaje netaknuta: n=9, P25 380, svih 8 stranih isključeno pravilom
  `non_resale_marketplace`.
- Testovi 194 → 203.
- **Otvoreno (D-018, #čeka-vlasnika):** trgovina van koridora EU→RS nije
  odobrena i ne računa se. Fale odobreni troškovi po koridoru, pravni i poreski
  položaj izvoza iz Srbije, i model rizika za prodaju na daljinu.

## 2026-08-19 `[claude-code]` — Sve u evrima; prevoz 25 € u svim smerovima (D-019)

- Vlasnik: prikaz mora biti u evrima („nemam osećaj za cenu u lejima"), a
  troškovi neka budu 25 € u svim smerovima dok se ne istraže.
- `Policy.corridor_shipping_eur = 25` (D-019), `POLICY_VERSION` → `policy-v3`.
  Posrednička naknada od 15 € i dalje važi **samo** za uvoz u Srbiju (D-010) —
  vezana je za konkretnog posrednika, nije opšti trošak koridora.
- `convert_to_eur()` u `fx.py`: konverzija po **posmatranom** kursu, sa razlogom
  umesto broja kad kursa nema. Matrica sada ima kolone `P25/med/P75 EUR`, uz
  lokalnu cenu pored — evro je izveden, original je posmatran.
- Razlike se računaju u evrima, pa se sada mogu porediti i tržišta u različitim
  valutama — ali samo ako postoji posmatran kurs. Tržište bez kursa ispada iz
  poređenja umesto da se konvertuje napamet.
- Neto razlika = bruto − 25 € prevoza. Ispis izričito kaže da posrednik, carina,
  provizija platforme i porez nisu uračunati.
- Trenutni prikaz: DE→RS bruto +52 €, **neto +27 €**; RS→DE bruto +45 €,
  **neto +20 €**.
- Nedostaju kursevi za RON i HUF, pa ta tržišta ne mogu u evre. Kad se dodaju u
  `data/fx-observations.json` sa izvorom i datumom, kolone se popunjavaju same.
- Testovi 203 → 206.

## 2026-08-19 `[claude-code]` — Kursevi centralnih banaka; Rumunija je izlaz, ne izvor

- Kursevi uzeti direktno sa sajtova centralnih banaka, sa datumom i izvorom
  (nije delegirano copilot-u — direktan izvor daje bolju proveru porekla):
  - **BNR** (bnr.ro): 1 EUR = **5,2452 RON**, 19.08.2026
  - **MNB** (mnb.hu): 1 EUR = **365,03 HUF**, 19.08.2026
  - **BNB** (bnb.bg): 1 EUR = **1,95583 BGN**, fiksni kurs (currency board)
  - NBS (nbs.rs) je blokiran u ekstenziji; ostaje vlasnikov unos 118.
- Upisano 8 rumunskih oglasa (olx.ro) sa ID-jevima; 6 preživelo IQR filter.
- **Matrica sada pokazuje ono što je vlasnik i naslutio:**

  | tržište | n | P25 EUR | med EUR | P75 EUR | lokalno P25 |
  |---|---|---|---|---|---|
  | kleinanzeigen | 8 | 338 | 425 | 463 | 338 EUR |
  | kupujemprodajem | 9 | 380 | 390 | 410 | 380 EUR |
  | olx-ro | 6 | 448,03 | 452,79 | 457,56 | 2350 RON |

  Najveća razlika nije DE→RS nego **DE→RO: bruto +114,79 €, neto +89,79 €**
  posle 25 € prevoza. Rumunija je skupa za kupovinu — što je znači da je
  kandidat za **prodaju**, ne da otpada.
- Ispravljen zaključak u `research/eu-izvori-merni-prolaz.md`: prvi prolaz je
  svako tržište merio samo kao izvor i odbacivao skupa. To je bila greška
  perspektive, ne merenja.
- I dalje nije odobrena trgovina van EU→RS: provizija platforme, porez i rizik
  prodaje na daljinu nisu ni izmereni ni odlučeni (D-018).

## 2026-08-19 `[claude-code]` — Matrica na 6 tržišta

- Dodati kursevi: **NBP** 1 EUR = 4,3267 PLN (tabela A, 160/A/NBP/2026,
  19.08.2026). CNB (Češka) i ECB su blokirani u ekstenziji, pa CZK nema kurs i
  češko tržište za sada ne može u evre.
- Upisano 28 opservacija: Austrija (willhaben, 6), Italija (subito, 12),
  Poljska (olx.pl, 10 → 9 posle IQR). Ukupno u store-u 53 opservacije.
- **Matrica, RTX 3080 Ti, sve u evrima:**

  | tržište | n | P25 | medijana | P75 | lokalno |
  |---|---|---|---|---|---|
  | kleinanzeigen (DE) | 8 | 338 | 425 | 463 | EUR |
  | kupujemprodajem (RS) | 9 | 380 | 390 | 410 | EUR |
  | subito (IT) | 12 | 430 | 450 | 600 | EUR |
  | olx-ro (RO) | 6 | 448,03 | 452,79 | 457,56 | 2350 RON |
  | olx-pl (PL) | 9 | 473,80 | 485,36 | 508,47 | 2050 PLN |
  | willhaben (AT) | 5 | 499 | 499 | 500 | EUR |

- **Nemačka je najjeftinija, Austrija najskuplja.** Najveća neto razlika je
  **DE→AT: +136 €** posle 25 € prevoza, pa DE→PL +122 €. Srbija je druga
  najjeftinija, pa je i RS→AT +94 € neto.
- Blokirani u ovoj sesiji: njuskalo (HR), hardverapro (HU), bolha (SI), bazos
  (CZ), cnb.cz, ecb.europa.eu. Dozvole za domene izgleda ne preživljavaju novu
  grupu tabova, pa ih treba ponovo odobriti.
- Isključeno iz poljskog uzorka: laptopovi (Razer Blade, MSI Raider), gaming
  box, jedan oglas od 33.000 zł (očigledna greška u ceni) i Dell OEM za 900 zł
  (sumnjivo jeftino, verovatno druga kartica).
- Ograda koja i dalje važi: sve su to **tražene** cene, ne postignute. Ako je
  asking-to-sold jaz veći na skupim tržištima, prednost se topi.

## 2026-08-19 `[claude-code]` — Praćenje tuđih tržišta (watchlist)

- `src/paper/watchlist.py`: `WatchItem` — oglas koji se prati zbog signala o
  ceni, bez verdikta i troškova. Predikcija odgovara na „da li kupiti"; ovde se
  to pitanje nikad ne postavlja, pa bi verdikt bio laž o donetoj odluci.
- `watch --add <tržište>` upisuje sve posmatrane oglase tog tržišta u
  `data/paper/watchlist.jsonl`. Isti oglas dvaput je jedan subjekat.
- `watch` sada prikazuje i predikcije i praćene oglase, najstarije prvo;
  `outcome` prima i `watch:` ID.
- **Uklonjeno ograničenje koje je postalo pogrešno:** `outcome
  --record-observation` je ranije odbijao sve osim KP oglasa. Sa matricom to
  znači bacanje podatka — prodaja u Austriji pripada austrijskoj ćeliji.
  Opservacija se sada upisuje sa svojim tržištem, a srpski uzorak čuva
  estimator (`resale_marketplaces`), gde to pravilo i pripada.
- Provereno: prodaja praćenog willhaben oglasa upisana kao SOLD/willhaben, a
  srpska procena netaknuta (n=9, basis ASKING).
- Praćeno: 6 austrijskih + 10 poljskih oglasa, plus 3 nemačke predikcije = 19
  subjekata na listi.
- Testovi 206 → 213.

## 2026-08-19 `[claude-code]` — Zatvaranje sesije

Sesija je počela sa „kreni w6" i zatvorena je sa alatom koji radi na stvarnim
podacima. Redosled je bio: alat → prvi podaci → nalaz koji je promenio plan.

**Napravljeno:**
- W6 paper trading: `src/paper/` (predikcije, ishodi, kalibracija, watchlist),
  komande `observe`, `predict`, `outcome`, `report`, `watch`, `matrix`.
- Matrica cena po tržištima sa bruto/neto razlikama, sve u evrima.
- Generički MANUAL konektor — novi sajt je red u `marketplace/sites.json`.
- Testovi 140 → **213**.

**Podaci koji sada postoje:** 59 opservacija sa 6 tržišta, 3 predikcije,
16 praćenih oglasa — ukupno 19 subjekata koji čekaju ishod. Ishoda: 0.

**Odluke:** D-012 (ručno čitanje KP), D-013 (EUR kao valuta opservacije),
D-014 (Kleinanzeigen), D-015 (prevoz 25 €, carina 0 kroz posrednika),
D-016 (samo EU, prevoz isti svuda), D-017 (merni prolaz), D-018 (matrica i
valuta po tržištu), D-019 (prikaz u evrima, prevoz 25 € u svim smerovima).

**Najvažniji nalaz:** srpski izlaz nije najbolji. DE→AT daje +136 € neto, a
DE→RS +27 €. To je posledica ideje vlasnika da se tržišta porede u oba smera —
prvi merni prolaz je gledao samo nabavku i zato je pogrešno odbacio Austriju
i Rumuniju.

**Šta nije urađeno i zašto:**
- Nema nijednog ishoda — oglasi su postavljeni na praćenje danas. Bez ishoda
  preciznost procene ostaje neizmerena i W6 gate nije prošao.
- W5 liquidity, friction i deal/confidence score nisu implementirani.
- HR, HU, SI i CZ tržišta nisu izmerena: dozvole domena u Chrome ekstenziji ne
  preživljavaju novu grupu tabova, a za CZK nema kursa.
- Trgovina van EU→RS nije odobrena; troškovi, poreski položaj i rizik prodaje
  na daljinu čekaju vlasnika i knjigovođu (D-018).

**Sledeći korak:** za nekoliko dana `arbitrage watch` i upis ishoda. Ključno
pitanje: da li se austrijskih 499 € stvarno prodaje.

## 2026-08-23 `[claude-code]` — Prva provera liste praćenja; bug u watch/report

- `python -m src.cli watch` → prošao kroz svih 19 subjekata ručno preko
  vlasnikovog Chrome-a (D-012/D-014/D-017: javno vidljive stranice, tempo
  ručnog pregleda, bez prijave/captcha zaobilaženja).
- **9 od 19 je nestalo (DELISTED):** svih 6 willhaben oglasa (400-550 €), 2 od
  10 olx-pl (jedan eksplicitno "to ogłoszenie nie jest już dostępne", jedan
  redirect na generičku listing stranicu), 1 kleinanzeigen (redirect na
  početnu). Nijedan nestanak nema vidljivu potvrdu prodaje — po principu 2
  (UNKNOWN ≠ 0) upisano kao DELISTED, cena UNKNOWN, ne SOLD.
- Ostalih 10 (2 kleinanzeigen + 8 olx-pl) i dalje stoji, cena nepromenjena od
  19.08 — upisano UNSOLD.
- Provereno da willhaben pretraga i dalje radi normalno (79 rezultata za "RTX
  3080 Ti", nijedan od 6 praćenih ID-jeva među njima) — 404 na sve nije
  blokada/anti-bot, nego stvarno uklonjeni oglasi.
- **Otkriven bug:** `arbitrage watch` i `arbitrage report` su pukli
  (`PaperStoreError: outcome refers to unknown prediction_id`) čim je watch
  oglas dobio prvi ishod. Uzrok: `cmd_watch`/`cmd_report` su prosleđivali CEO
  `outcomes` niz u `pair_records(predictions, outcomes)`, a `pair_records`
  namerno baca grešku za svaki `prediction_id` koji nije u `predictions.jsonl`
  — što watch-ishodi po dizajnu nisu (žive u `watchlist.jsonl`). Bug je bio
  neviđen dosad jer watch-ishoda do danas nije bilo (0 ishoda).
  Popravka: obe komande sada filtriraju `outcomes` na one čiji `prediction_id`
  pripada učitanim predikcijama pre poziva `pair_records`; `latest`-mapa za
  prikaz watch-stavki i dalje koristi ceo `outcomes` niz (to je bilo ispravno).
  Test: `tests/test_cli.py` (nov fajl — prvi CLI-nivo test u projektu),
  reprodukuje tačnu mešavinu koja je pukla.
- Testovi 213 → 215.
- **Otvoreno pitanje, ne zaključak:** brz nestanak svih 6 austrijskih oglasa
  (4 dana) bez potvrde prodaje može ići u prilog DE→AT nalazu (tržište stvarno
  plaća 499-550 €) ili biti nevezano (willhaben brzo ističe/uklanja oglase iz
  drugih razloga). Bez SOLD potvrde ne računa se kao dokaz ni u jednom pravcu.

**Sledeći korak:** za nekoliko dana ponovo `arbitrage watch` za preostalih 10
subjekata (2 kleinanzeigen, 8 olx-pl). Ako i poljski oglasi počnu da nestaju
bez potvrde prodaje na istom tempu, obrazac postaje vredan zapisa u
`research/`, ne samo u dnevniku.

## 2026-08-23 `[claude-code]` — Novi oglasi na 8 tržišta; willhaben bug; Mađarska prvi put merljiva

Nastavak iste sesije, na zahtev vlasnika da se pronađu novi oglasi i uporede
sa postojećim uzorkom — i da se ne stane na 4 tržišta nego pokrije isto što i
matrica (D-018): DE, RS, IT, RO, PL, AT, plus ponovni pokušaj HR/HU/SI/CZ.

**Kritičan nalaz, uzgredan:** dok se tražio nov willhaben oglas, isti ID
(1095225831) se pojavio u sveže pretrazi i učitao normalno — iako je malopre
u ovoj istoj sesiji upisan kao DELISTED. Uzrok: opservacije od 19.08. su
sačuvale willhaben URL bez SEO sluga (`/d/1900028284`), a willhaben-ov SPA
routing na goli broj vraća 404 bez obzira da li je oglas živ. Testirano
sistematski (varijanta sa izmišljenim slugom `/d/x-{id}/` za svih 6 ID-jeva):
**5 od 6 je živo i nepromenjeno** (jedan čak osvežen istog dana), samo
1900028284 (400 €) je stvarno nestao — willhaben eksplicitno vraća "Anzeige
nicht mehr verfügbar" i redirect na `?fromExpiredAdId=`, za razliku od
generičkog 404 na ostalih 5. Ispravljeno sa 5 novih outcome linija (UNSOLD,
append-only, principe 6 — stari pogrešni upisi ostaju kao trag). Lekcija
upisana u `reference/naucene-lekcije.md`. Provereno i olx-pl DELISTED
(1aTuDN) istim pristupom — URL je bio ispravno formatiran, drugi put učitan
isto (generička homepage bez eksplicitne poruke), ostaje DELISTED kao
nepotvrđen ali dosledan nalaz.

**Nove opservacije, 22 ukupno** (svih 8 sledećih tržišta rade u ovoj sesiji —
domeni koji su ranije bili blokirani u Chrome ekstenziji sada prolaze; dozvole
se očito povremeno resetuju po grupi tabova):
- willhaben (AT): +3 (450, 480, 480 €)
- olx-pl (PL): +6 (1450-2900 zł)
- olx-ro (RO): +2 (2350, 2600 lei) — 6 od 8 pronađenih je bilo duplikat već
  poznatih oglasa (isti naslov/cena), što je samo po sebi potvrda da je RO
  uzorak od pre 4 dana i dalje tačan prikaz ponude.
- subito (IT): +1 (600 €)
- **njuskalo.hr (HR): +4, prvi put u store-u** (300, 490, 499, 500 €) —
  ranije samo zapažanje u `research/`, sad su to prave opservacije.
- **hardverapro.hu (HU): +5, prvi put u store-u** (158.900-199.999 Ft) —
  ranije odbačena na jednom uzorku od 195.000 Ft (research merni prolaz
  19.08.), sad sa 5 uzoraka izgleda potpuno drugačije.
- **bazos.cz (CZ): +1, prvi put u store-u** (8.500 Kč) — i dalje bez CZK
  kursa (cnb.cz, ecb.europa.eu i dalje blokirani), ne ulazi u matricu dok se
  kurs ne doda.
- bolha.com (SI): 0 — tražena kategorija ima samo 1 bundle PC, nijednu golu
  karticu. Potvrđuje raniji nalaz da je slovenačko tržište tanko.
- kleinanzeigen.de (DE): **blokirano** — "IP-Bereich vorübergehend gesperrt"
  (privremeni rate-limit blok). Poštovano po D-014 (bez zaobilaženja rate
  limita); nema novih DE opservacija ove sesije.

**Matrica sada ima 9 tržišta** (`arbitrage matrix --product-id rtx-3080-ti`):
DE 338/425/463 (n=8) < RS 380/390/410 (n=9) < IT 430/450/600 (n=13) <
**HU 438/492/501 (n=5)** < RO 448/453/458 (n=8) < AT 450/480/499 (n=9) <
PL 462/485/508 (n=13). HR (n=4) i CZ (n=1) ispod praga uzorka (5).

**Najveći nalaz: DE→HU je sada najveća neto razlika, +128,74 € (45,5%)**,
ispred DE→PL (+122,13 €) i DE→AT (+117 €, palo sa +136 € jer su 3 nova
jeftinija AT uzorka spustila medijanu sa 499 na 480). Mađarska je u prvom
mernom prolazu (19.08.) odbačena na jednom skupom uzorku — klasičan primer
"merenje sa jednom perspektivom daje pogrešan zaključak" (već zabeleženo kao
lekcija), samo sad na sopstvenom uzorku umesto na tuđem.

Srpska procena proverena da ostaje netaknuta: `arbitrage price --product-id
rtx-3080-ti` i dalje n=9, P25 380 — sve 72 strane opservacije (uklj. 22 nove)
ispravno isključene pravilom `non_resale_marketplace`. 215 testova i dalje
prolazi (nema promene koda ove sesije, samo podaci).

**Šta nije urađeno:** nijedan od novih HU/HR oglasa nije dodat na listu
praćenja (`watch --add`) — vredi uraditi sledeći put, jer je Mađarska sad
matematički najbolja prodajna destinacija, ali i dalje samo na asking cenama,
bez ijedne potvrđene prodaje.

**Sledeći korak:** ponovo `arbitrage watch` za svih 15 otvorenih subjekata
(sa ispravnim willhaben URL-ovima ovog puta), plus razmotriti `watch --add
hardverapro` i `watch --add njuskalo` da HU/HR uđu u merenje ishoda, ne samo
u matricu asking cena.

## 2026-08-23 `[claude-code]` — Zatvaranje sesije

Sesija je počela sa proverom liste praćenja ("proveri oglase na današnji dan")
i proširila se na traženje novih oglasa i poređenje sa postojećim uzorkom, na
zahtev vlasnika da se ne stane na 4 tržišta nego pokrije isto što i matrica.

**Napravljeno:**
- Prva provera liste praćenja: 19 ishoda, potom 5 korekcija — ukupno 24 ishoda
  upisano, i dalje 0 SOLD.
- **Dva bug fixa u W6 alatu**, oba otkrivena tokom rada, ne planirana:
  1. `watch`/`report` su pucali čim je watch-oglas dobio ishod (`pair_records`
     je dobijao outcome-e koji ne pripadaju nijednoj predikciji). Test u
     `tests/test_cli.py` (prvi CLI-nivo test u projektu).
  2. 5 od 6 willhaben oglasa je bilo lažno prijavljeno kao DELISTED — sačuvan
     URL bez SEO sluga je rušio willhaben-ov routing. Ispravljeno novim
     outcome linijama; lekcija upisana da se ne ponovi.
- Matrica cena proširena sa 6 na 9 tržišta: +22 opservacije preko willhaben,
  olx-pl, olx-ro, subito, njuskalo (novo), hardverapro (novo), bazos (novo).
  Bolha.com (SI) proveren i prazan za ovaj model.
- **Mađarska (hardverapro.hu) je najveći nalaz sesije:** sa 5 sopstvenih
  uzoraka umesto ranijeg jednog tuđeg, ispada matematički najbolja prodajna
  destinacija (DE→HU +128,74 €, 45,5% neto), ispred Poljske i Austrije.
  I dalje samo asking cena, bez potvrđene prodaje.
- 213 → 215 testova (oba nova testa iz bug fix #1).

**Podaci koji sada postoje:** 81 opservacija na 9 tržišta (bilo 59 na 6), 24
ishoda upisano (bilo 0), 15 subjekata i dalje otvoreno na listi praćenja.

**Odluke:** nijedna nova ovom sesijom — sve što je urađeno spada pod već
odobrene D-012/D-014/D-017 (ručno čitanje javnih oglasa preko vlasnikovog
Chrome-a), sa jednim izuzetkom niže.

**Blokeri/otvoreno (upisano i u `MASTER-PLAN.md` i `PROGRESS.md`):**
- 🟡 #čeka-provere: `bazos.cz` (Češka) pročitan i upisan 2026-08-23 bez
  prethodne eksplicitne odluke — D-012/D-014/D-017 nabrajaju tačan spisak
  sajtova i `bazos.cz` nije na njemu. Treba ili proširiti D-017 na Češku
  (isti obrazac: javna stranica, vlasnikov Chrome, bez zaobilaženja) ili
  povući taj jedan upis iz `serbia.jsonl`.
- 🟡 CZK kurs i dalje nedostaje — jedini razlog zašto Češka ne ulazi u matricu
  čak i kad dobije dovoljno uzoraka.
- Ostali blokeri nepromenjeni: D-007 (prvi EU connector), D-018 (koridor van
  EU→RS), verifikacija automatizovanog pristupa.

**Najvažniji nalaz:** isti obrazac kao ranija lekcija "merenje sa jednom
perspektivom daje pogrešan zaključak" (ovog puta na sopstvenom uzorku, ne
tuđem) — Mađarska je 19.08. odbačena na jednom skupom oglasu, a 23.08. sa pet
uzoraka ispada najbolja. I podsetnik da 404 nije uvek "nestalo": bez
eksplicitne poruke sajta o uklanjanju, greška u URL formatu izgleda identično
kao stvarno uklonjen oglas.

**Šta nije urađeno i zašto:**
- Nijedan HU/HR oglas nije dodat na listu praćenja — otkriveni su kasno u
  sesiji, dodavanje i prvo merenje ishoda ostaje za sledeći put.
- W5 liquidity, friction i deal/confidence score i dalje nisu implementirani.
- Kleinanzeigen (DE) nije osvežen — rate limit blokirao dalje zahteve tokom
  sesije, poštovano bez zaobilaženja (D-014).

**Sledeći korak:** `arbitrage watch` za svih 15 otvorenih subjekata (ispravnim
willhaben URL-ovima), `watch --add hardverapro` i `watch --add njuskalo`, i
odluka vlasnika o `bazos.cz`.

## 2026-08-24 `[claude-code]` — Druga provera liste praćenja; HU i HR ulaze u watchlist

Sesija je počela sa `gde-smo-stali`. Predlog sledećeg taska (provera 15
otvorenih watch-subjekata + dodavanje HU/HR) potvrđen — nije bio blokiran,
`hardverapro.hu` i `njuskalo.hr` su već pokriveni D-017.

**Provereno svih 15 subjekata**, willhaben URL-ovi ovog puta sa slug-om
(`/d/x-{id}/`) po lekciji od 23.08:
- 5 willhaben (AT): svih 5 živo, cene nepromenjene (450, 499, 499, 500, 550 €).
- 8 olx-pl (PL): svih 8 živo, cene nepromenjene (1999–2399 zł).
- 2 kleinanzeigen (DE): 1 živ nepromenjen (350 €), **1 stvarno DELISTED**
  (EVGA 3080Ti, 300 €) — stranica nosi eksplicitnu oznaku "Gelöscht" iznad
  naslova, ne generički 404, pa je nalaz pouzdan po pravilu iz
  `reference/naucene-lekcije.md`.

**Uzgredan nalaz:** za drugi kleinanzeigen oglas je `get_page_text` prvi put
vratio tekst potpuno nepovezanog oglasa (drugi grad, drugi model, druga
cena) — izgleda kao da je pokupio sadržaj reklamnog/preporučenog vidžeta na
stranici umesto glavnog članka, ne stvarna promena sadržaja. Provereno
screenshot-om posle skrolovanja: pravi oglas je i dalje živ, cena
nepromenjena. **Lekcija:** kad `get_page_text` vrati sadržaj koji ne
odgovara očekivanom oglasu (drugi grad/model/cena), ne uzimati to kao dokaz
o promeni bez vizuelne provere — može biti da je izvučen pogrešan DOM
element.

**15 outcome linija upisano** (append-only): 14 UNSOLD, 1 DELISTED. Ukupno u
`data/paper/outcomes.jsonl` sada 39 linija (10 DELISTED, 29 UNSOLD), **i
dalje 0 SOLD, 0 sa cenom** — pet dana bez ijedne potvrđene prodaje na 15 pod
nadzorom, što i dalje ide protiv teze o brzoj apsorpciji po posmatranim
asking cenama.

**Dodato na watchlist:** `watch --add hardverapro --product-id rtx-3080-ti`
(5 subjekata) i `watch --add njuskalo --product-id rtx-3080-ti` (4
subjekta) — Mađarska je matematički najbolja prodajna destinacija u matrici
(D-018), ali do sada samo na asking cenama; ovo je prvi korak ka merenju
stvarnog ishoda tamo. Sada 23 otvorena subjekta ukupno.

215 testova i dalje prolazi (bez izmene koda ove sesije, samo podaci).
`bazos.cz` odluka ostaje otvorena (#čeka-provere), nije dirana ove sesije.

**Sledeći korak:** za nekoliko dana `arbitrage watch` za svih 23 subjekta.
Ako treći prolaz i dalje da 0 SOLD, razmotriti da li 5-dnevni interval
provere uopšte hvata realan ciklus prodaje, ili treba duži razmak.

## 2026-08-24 `[claude-code]` (drugi deo) — Merni prolaz na BG/BE/NL; D-020 (dealer_reference isključen iz statistike)

Nastavak iste sesije, na zahtev vlasnika: "Proširi pretragu na druge države."
D-017 već pokriva `olx.bg` (BG), `2dehands.be`/`marktplaats.nl` (BE/NL) i
`jofogas.hu` (drugi HU sajt) — nijedan od njih do sad nije korišćen. Fokus
ove sesije: BG, BE, NL (nove *države*; jofogas je drugi sajt za već pokrivenu
Mađarsku, ostavljen za drugi put).

**olx.bg (Bugarska):** pretraga za "rtx 3080 ti" dala 49 rezultata, filtrirano
na gole kartice (bez laptopa/PC bundle-ova/ventilatora): 9 kandidata. Sajt
eksplicitno označava "Частна" (privatna) vs "Бизнес" (poslovna) na svakoj
stranici oglasa — **7 od 9 je bilo diler** (PCFlip.BG triput, MyPCcamp,
Komputri bg), samo 2 privatna. Cene su prikazane direktno u EUR (Bugarska je
u međuvremenu ušla u evrozonu), bez potrebe za konverzijom.

**Kritičan nalaz:** `src/pricing/serbian_market.py` je te diler cene mešao
sa privatnim u P25/medijana/P75 računu — `PriceObservation` je već imao
`dealer_reference` kao poseban `price_type`, ali `_filter()` ga nije
isključivao, samo `SOLD`/`COMPLETED` je imao posebno tretiranje. Ista klasa
greške koju D-013 zabranjuje za mešanje valuta, neprimenjena na tip
prodavca — prva olx-bg ćelija u matrici (n=8, medijana 455 €) bila je
mešavina i vodila ka precenjenoj proceni.

Stao sam i pitao vlasnika pre nastavka (pitanje preko AskUserQuestion, ne
nagađanje) — ovo je poslovno pravilo (šta ulazi u procenu cene), ne
implementacioni detalj, princip 9 traži odluku u `odluke/` pre izmene.
**Odgovor: isključi dealer_reference iz statistike (preporučena opcija).**

**D-020 upisana i primenjena:**
- `REFERENCE_TYPES = {DEALER_REFERENCE, MANUAL_REFERENCE}` — oba isključena
  iz uzorka istim rezonom (referentna, ne peer cena), sa razlogom
  `reference_price_not_peer:<tip>` u `ExcludedObservation`.
- Opservacije ostaju upisane (princip 6) — samo se ne broje u percentile.
- Primenjeno u `_filter()` u `src/pricing/serbian_market.py`; `market_matrix.py`
  automatski nasleđuje fix jer poziva isti `estimate_resale()`.
- 2 nova testa (`test_dealer_reference_is_not_a_peer_price`,
  `test_manual_reference_is_not_a_peer_price`) po uzoru na postojeći stil
  (`test_bundle_price_is_not_a_gpu_price`). 215 → 217 testova, svi prolaze.
- Provereno da nijedna ranija opservacija (pre ove sesije) nije bila
  dealer/manual_reference — fix je čist, nijedna stara ćelija matrice se
  nije promenila retroaktivno.

Posle fixa: olx-bg ćelija ispravno pada na n=2 (ispod praga 5), `INSUFFICIENT_DATA`.

**2dehands.be (Belgija):** 15 rezultata za "rtx 3080 ti", samo 3 gole kartice
(ostalo PC-ovi, laptopovi, jedna "samo kutija bez kartice"). Sve 3 privatne
(nema "Zakelijk" oznaku). 450–500 €, n=3 — ispod praga uzorka.

**marktplaats.nl (Holandija):** 16 rezultata u kategoriji "Videokaarten",
15 prodajnih (1 "tražim/menjam" isključen). 1 od njih bez fiksne cene (samo
"Bieden"/ponude, nema asking cenu) — isključen, nema šta da se upiše. Od
preostalih 14: **13 privatnih + 1 diler** — "Hardriven Technologies", sa
sopstvenim sajtom (hardriven.nl) i profesionalnim dvojezičnim opisom
("Japan Import", test report na sajtu) — jasan poslovni identitet iako sajt
nema formalnu "Zakelijk" oznaku u tekstu koji se čita; klasifikovan kao
dealer_reference po istom D-020 principu (poslovni identitet, ne samo
platformska oznaka).

**Uzgredna napomena, nije filtrirano:** jedan privatni nalog ("Dan", 2 god.
na sajtu, 205 ocena) je izvor 3 od 14 holandskih oglasa, gotovo identičan
tekst/grad. Nema formalnu poslovnu oznaku pa je upisan kao privatni po istom
kriterijumu kao ostali, ali obrazac (visok broj ocena, ponovljen šablon)
liči na neformalnog preprodavca. Zabeleženo u PROGRESS.md kao otvoreno
pitanje za vlasnika, ne isključeno bez odluke.

Posle IQR filtera: n=12 privatnih holandskih opservacija u matrici, medijana
500 €. **Holandija je nova najveća DE→izlaz razlika: +137 € neto (47,9%)**,
ispred Mađarske (+128,74 €) koja je bila prva ranije ove sesije.

**Upisano 26 novih opservacija ukupno** (9 BG, 3 BE, 14 NL — uklj. 1 diler
BG × 7... ne, tačnije: BG 2 asking + 7 dealer_reference = 9; BE 3 asking;
NL 13 asking + 1 dealer_reference = 14). `marketplace/sites.json` dopunjen
sa `olx-bg`, `2dehands`, `marktplaats` redovima (D-017 kao source_decision).

**Sledeći korak:** Belgija i Bugarska su ispod praga uzorka (n=2 svaka) —
vredi dodatni merni prolaz da pređu 5. `jofogas.hu` (drugi mađarski sajt) i
dalje nekorišćen. Vlasnik treba da odluči o "Dan" obrascu (ponovljeni
privatni nalog bez formalne poslovne oznake).
