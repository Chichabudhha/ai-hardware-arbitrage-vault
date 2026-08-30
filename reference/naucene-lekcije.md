# Naučene lekcije — AI Hardware Arbitrage Serbia

> Popunjava se progresivno, nikad unapred. Svaka lekcija = greška ili
> gotcha koji se desio jednom i ne sme da se ponovi. Organizuj po temi.
> Ovo je verovatno najvažniji fajl u vault-u za sprečavanje ponavljanja
> istih grešaka kroz sesije.

## Tracking
- {{npr. "GTM consent update handler mora slati eksplicitne vrednosti za
  sve kategorije — prazan update ne preklapa prethodno stanje"}}

## Konektor / API dijagnostika
- {{npr. "prazan odgovor za kampanju ne znači grešku — proveri spend pre
  nego što pretpostaviš kvar"}}
- Ollama HTTP 500 "model requires more system memory" nije kvar modela ni
  servera — ollama podrazumevano alocira KV cache za pun kontekst modela
  (qwen3 ima 256K → traži 20.1 GiB). Rešenje je `options.num_ctx` (8192 radi
  na 16 GB RAM). Greška se vidi samo na sirovom HTTP odgovoru; `/api/generate`
  preko klijenta vraća tiho prazan `response`.

## AI delegacija
- **Grok `--permission-mode plan` blokira delegaciju.** U plan režimu grok
  pokušava da pokrene shell da bi proverio nalaze, biva blokiran, pa se vrti u
  prazno i ne vrati nijedan nalaz. Read-only se postiže allowlistom alata:
  `--tools "read_file,grep,list_dir"` (interni ID-jevi; shell je
  `run_terminal_cmd`, ne `bash`). Copilot koristi druga imena: `view,glob,grep`.
- **Ograničenje trajanja mora da bude unutar skripte, ne oko nje.** Kad spoljni
  `timeout` ubije `delegate.sh`, provenance log se nikad ne upiše — a zapis koji
  nedostaje ne razlikuje se od poziva koji se nikad nije desio. Sada je
  `timeout` oko samog poziva provajderu, pa se exit 124 loguje kao i svaki drugi.
- Delegatu treba eksplicitno reći da nema shell; inače troši turnove pokušavajući
  da pokrene testove umesto da opiše slučaj koji orkestrator treba da izvrši.

## Product matching / embeddings
- **`nomic-embed-text` se NE SME koristiti za `product_match`.** Izmereno
  2026-08-18 na stvarnim formulacijama oglasa: kosinusna sličnost za
  "RTX 3090 24GB Gigabyte Gaming OC" vs "RTX 3080 10GB Gigabyte Gaming OC"
  je **0.930**, dok je isti proizvod drugačije opisan samo **0.708**.
  Embedding hvata površinsku sličnost teksta, ne značenje broja modela.
  Posledica da se pusti u produkciju: 3080 (10GB) bi se spojio sa 3090 (24GB) —
  potpuno različita vrednost i AI upotrebljivost.
  **Ispravno:** čip se izvlači deterministički (zatvoren skup: 3090, 3090 Ti,
  4090, 4080 Super, A4000/A5000/A6000, V100, A100), regexom, ne modelom.
  Embedding sme najviše kao sekundarni signal za duplikat *unutar već
  potvrđenog istog čipa*, nikad kao primarni kriterijum.

## SEO
- {{npr. "content parity bitniji od redirekcija samih po sebi"}}

## Tehnički / build
- {{npr. specifičan JS bug u page builderu, verzija-zavisan}}

## Komunikacija / proces
- {{npr. "vlasnik projekta preferira X format izveštaja"}}

## Tvrdo kodirana vrednost sa komentarom "vlasnik mora da potvrdi" je i dalje pretpostavka

`src/pricing/calculator.py` je četiri sesije nosio `BUY_MIN_ROI = 0.25` uz
komentar da vrednost čeka potvrdu. Komentar ne sprečava kod da računa — svaki
verdikt u tom periodu je bio izveden iz neodobrenog broja, iako je `PROGRESS.md`
istovremeno prijavljivao pragove kao blokirane.

**Pravilo:** poslovna vrednost koja nije odobrena ne sme da ima podrazumevanu
vrednost u kodu. Ili je odluka u `odluke/` i konfiguracija u `src/core/policy.py`,
ili je obavezan ulaz koji daje `INSUFFICIENT_DATA` kad nedostaje.

## Visok ROI nije isto što i posao

40% ROI na kartici od 100 € je 40 € profita. BUY zahteva **oba** praga —
procentualni i apsolutni — jer procenat sam po sebi ne pokriva vreme, transport
i rizik po dealu. Isto važi za budžet: prilika iznad limita po kupovini ne može
da bude BUY bez obzira na ekonomiju.

## Tiha ekstrapolacija je gora od izuzetka

`percentile()` sa `fraction` van [0,1] nije pucao — linearna interpolacija je
uredno vratila broj izvan opsega uzorka. To je cena koju nijedna opservacija ne
podržava, isporučena kao validan rezultat. Delegirani review je to našao.

**Pravilo:** funkcija koja računa novac mora da odbije ulaz van domena, ne da ga
ekstrapolira. Izuzetak se primeti, pogrešan broj se ne primeti.

## Konzervativnost mora da dođe iz podataka, ne iz pretpostavke

Asking cena je iznad realizovane, ali za koliko — niko ovde nije izmerio.
Iskušenje je bilo staviti faktor (npr. 0.85) i nastaviti. To bi bio izmišljen
broj u srcu svakog verdikta.

**Rešenje:** P25 posmatrane distribucije umesto medijane. Konzervativan je, ali
je *posmatran* — svaka vrednost koja ulazi u procenu postoji u nekom oglasu.
Kad se pojave sold podaci, medijana tih podataka preuzima.

## Preskočena opservacija pomera svaki percentil

Prva verzija JSONL loader-a je htela da preskoči pokvarenu liniju i nastavi.
Kod uzorka od 6 oglasa, jedna preskočena linija menja P25 za nekoliko hiljada
dinara — a niko ne bi znao da se to desilo.

**Pravilo:** u statističkom ulazu, pokvaren zapis je greška, ne šum koji se
ćuti. Isto važi i za `load_rates` (ista lekcija, drugi modul).

## Zaokruživanje pre poređenja može da promeni odluku

U kalibracionom izveštaju realizovan ROI se kvantizovao na 4 decimale pa
poredio sa pragom iz `policy.py`. ROI od 0.17999 tako postaje 0.1800 i prolazi
prag od 0.18 — false positive nestane iz izveštaja, a nastao je od zaokruživanja
za prikaz.

**Pravilo:** poredi u punoj preciznosti, zaokružuj samo ono što se prikazuje.
Isto važi za medijanu dana do prodaje: `int()` seče 1.5 na 1 i tržište uvek
ispadne brže nego što jeste.

## Lokalni model nije besplatan ako ne stane u RAM

`qwen3:4b` je 2,5 GB na disku, ali sa podrazumevanim kontekstom traži ~20 GiB
memorije i odbija da se učita na mašini sa ~9 GiB slobodnih. Kontekst se
smanjuje na serveru (`OLLAMA_CONTEXT_LENGTH` za `ollama serve`), ne na klijentu.

**Pravilo:** pre nego što se delegacija prebaci na lokalni model, proveri da li
uopšte može da se učita sa veličinom prompta koja se stvarno šalje.

## Merenje sa jednom perspektivom daje pogrešan zaključak

Prvi prolaz po EU oglasnicima merio je svako tržište **samo kao izvor** i
odbacivao ono što je skupo. Rumunija i Austrija su tako „otpale". Kad je
napravljena matrica sa oba smera, ispalo je da su upravo one najbolji **izlaz**:
DE→AT daje +136 € neto, a DE→RS, na kojem se radilo, samo +27 €.

**Pravilo:** pre nego što se tržište odbaci, proveri da li je odbačeno zato što
ne valja ili zato što je mereno samo iz jednog ugla. Zaključak „preskupo" uvek
ima drugu stranu.

## Konfiguracija ne sme da odobrava pristup

Generički konektor učitava sajtove iz JSON-a. Prva verzija je dozvoljavala da
profil postavi `automation_status`. To znači da neko ko doda red u konfiguraciju
može da odobri automatizovan pristup sajtu — odluku koja po pravilima traži
proveru ToS-a i unos u `odluke/`.

**Pravilo:** konfiguracija opisuje *kako* se nešto čita, nikad *da li* sme.
Status pristupa je uvek `MANUAL` bez obzira šta u fajlu piše, i test to proverava
pokušajem da podmetne `AUTOMATED`.

## Zaštita postavljena na pogrešnom sloju baca podatke

`outcome --record-observation` je odbijao sve osim srpskih oglasa, da nemačka
cena ne bi ušla u srpsku procenu. Kad je matrica dodala i druga tržišta, isto
pravilo je počelo da **baca** podatak: prodaja u Austriji nije imala gde da ode,
iako pripada austrijskoj ćeliji.

**Pravilo:** zaštitu stavi tamo gde je posledica, ne tamo gde je ulaz. Srpski
uzorak čuva estimator (`resale_marketplaces`); upis opservacije samo beleži šta
je viđeno i gde.

## Prikaz u stranoj valuti je neupotrebljiv, konverzija je izvedena

Vlasnik nema osećaj za cenu u lejima ni forintama, pa tabela u lokalnim valutama
ne služi ničemu. Ali konverzija ne sme da izbriše original: iznos u evrima je
izveden podatak, a ono što u oglasu piše je posmatrano.

**Rešenje:** prikazuj evro, ali drži lokalnu cenu pored njega, i konvertuj samo
po kursu koji ima izvor i datum. Tržište bez kursa prikazuje `-` i razlog, a ne
približnu cifru — i ispada iz poređenja umesto da uđe sa izmišljenim kursom.

## Anti-bot 404 i "stvarno uklonjeno" izgledaju identično — proveri obe hipoteze

Willhaben je 19.08. sačuvan sa URL-om bez SEO sluga (`/d/1900028284` umesto
`/d/naziv-oglasa-1900028284/`). Ta forma vraća 404 bez obzira da li je oglas
živ ili ne — willhaben-ov SPA routing zahteva bilo kakav ne-prazan tekst pre
ID-ja (čak i besmislen, npr. `x-1900028284`), sam broj nije dovoljan. Dana
23.08. je 404 na svih 6 sačuvanih URL-ova pogrešno protumačen kao 6 stvarnih
uklanjanja i upisan kao DELISTED. Otkriveno slučajno: isti ID se pojavio u
pretrazi sa punim URL-om i učitao se normalno.

**Pravilo:** kad se stranica ne učita, proveri da li greška ide uz **eksplicitnu
poruku o uklanjanju** specifičnu za taj sajt (willhaben: "Anzeige nicht mehr
verfügbar" / redirect na `?fromExpiredAdId=`; olx: "to ogłoszenie nie jest już
dostępne") pre nego što se to upiše kao DELISTED. Generički 404/homepage
redirect bez te poruke je dvosmislen — proveri i URL format (nedostaje li
slug, parametar, deo putanje) pre nego što se protumači kao dokaz o sadržaju.
Ako je sumnjivo, probaj varijantu URL-a sa izmišljenim slugom umesto golog ID-ja
— ako se stranica učita, greška je bila u formatu URL-a, ne u oglasu.

Ispravka pogrešnog upisa ide kao **nova outcome linija** (append-only, princip
6), sa napomenom da ispravlja raniji pogrešan upis — stara linija ostaje na
disku kao trag greške, ne briše se.

## Dva izvora koja dele isti outcome namespace moraju da se filtriraju pre spajanja

Predikcije (`predictions.jsonl`) i praćeni oglasi (`watchlist.jsonl`) su
odvojeni fajlovi, ali dele isti `outcome` store i isti ID prostor
(`prediction_id` vs `watch:marketplace:id`). `pair_records()` namerno baca
grešku na outcome čiji ID ne postoji među predikcijama — ispravno ponašanje
za slučaj kad je ID otkucan pogrešno. Ali `cmd_watch`/`cmd_report` su prosleđivali
**ceo** outcomes niz toj funkciji, iako on sadrži i outcome-e za watch-stavke
koje po dizajnu nikad neće biti u `predictions.jsonl`. Dok watch-ishoda nije
bilo (0), bug je bio nevidljiv — pojavio se tek kad je prva serija watch-ishoda
upisana.

**Pravilo:** kad dve strukture dele isti outcome/ID prostor, filtriraj skup na
onaj koji odgovara trenutnom kontekstu **pre** poziva funkcije koja tretira
nepoznat ID kao grešku. Test za ovakav bug mora da postavi both-and-scenario
(bar jedan zapis iz svake strukture sa svojim outcome-om) — test koji koristi
samo jednu vrstu ne bi ovo uhvatio, što je i razlog zašto je bug prošao kroz
213 postojećih testova.

## "Uzorak se ne meša" važi i za tip prodavca, ne samo za valutu

D-013 zabranjuje mešanje valuta u jednom P25/medijana/P75 uzorku. Isti princip
je prećutno prekršen na drugom mestu: `PriceObservation` je od početka imao
`dealer_reference` kao poseban `price_type` (za razliku od `asking`), ali
`src/pricing/serbian_market.py` ga nikad nije isključivao iz statistike — samo
`SOLD`/`COMPLETED` je imao posebno tretiranje u `_basis()`. Diler cena nosi
maržu koju privatni prodavac nema; mešana u uzorak, sistematski gura medijanu
naviše.

Nalaz je slučajan: merni prolaz kroz `olx.bg` (2026-08-24) je otkrio da je
7 od 9 nađenih oglasa za isti model bilo od preprodavaca hardvera (sajt ih
eksplicitno označava "Бизнес" nasuprot "Частна"), a samo 2 privatna — prva
verzija ćelije u matrici (n=8) bila je mešavina koja je izgledala kao normalan
rezultat, bez ikakve greške ili crasha koji bi je odao.

**Pravilo:** svaki dodatni `price_type`/`observation_type` u modelu podataka
mora da ima **odgovarajuću granu u filteru** koji hrani statistiku, ne samo da
postoji kao opcija u enumu. Prisustvo tipa u modelu nije dokaz da je obrađen u
proračunu — proveri filter, ne samo šemu. Ispravljeno u D-020: `dealer_reference`
i `manual_reference` isključeni iz uzorka (razlog `reference_price_not_peer:*`),
opservacije ostaju upisane (princip 6), samo se ne broje.

## Platformska oznaka za diler/privatno nije univerzalna — proveri poslovni identitet i kad oznaka nedostaje

Kriterijum za dealer_reference (D-020) je platformska oznaka ("Бизнес" na
olx.bg, "Zakelijk" na 2dehands/marktplaats). Ali `marktplaats.nl` oglas
"ROG Strix RTX 3080 Ti — Japan Import | Hardriven" nije nosio takvu oznaku u
tekstu koji se čita, a prodavac je bio nedvosmisleno firma: ime "Hardriven
Technologies", sopstveni sajt (hardriven.nl) sa test izveštajem, profesionalan
dvojezičan opis. Klasifikovan kao dealer_reference na osnovu tih signala, ne
platformske oznake koje nije bilo.

**Pravilo:** platformska oznaka je *dovoljan* dokaz za dealer_reference, ali
nije *neophodan* — jasan poslovni identitet u samom oglasu (ime firme,
sopstveni sajt, profesionalan copy) je isti kvalitet dokaza. Obrnuto: visok
broj ocena ili ponovljeni oglasi kod *privatnog* naloga bez ijednog od tih
znakova (npr. "Dan" na marktplaats.nl, 205 ocena, 3 skoro identična oglasa)
nije dovoljan dokaz sam po sebi — zabeleži kao otvoreno pitanje
(#čeka-vlasnika), ne izjednačavaj tiho sa diler statusom bez odluke.

## Diler se često otkrije tek kad se prati ishod, ne pri prvom unosu

Na njuskalo.hr i hardverapro.hu je diler status prošao neprimećen pri prvom
unosu opservacija (23.08) — ime prodavca i pravni podaci se čitaju tek na
detaljnoj stranici oglasa, a pri masovnom unosu se pažnja usmerava na cenu i
specifikaciju, ne na prodavca. Otkriveno je tek 2026-08-30, slučajno, tokom
`watch` provere istog oglasa (gde se stranica ionako otvara ponovo). Dva
primera: "eRadar Tech d.o.o." (njuskalo, pravni podaci sa matičnim brojem i
samo-sertifikacijom po Aktu o digitalnim uslugama) i "MvilágKft" (hardverapro,
Kft = d.o.o., plaćena Ultra objava, radnja sa radnim vremenom, 69 drugih
oglasa).

**Pravilo:** dealer_reference klasifikacija (D-020) nije jednokratna provera
pri unosu — vredi je ponoviti kad god se stranica oglasa ponovo otvara (watch
provera, price_cut, bilo koji razlog za povratak), jer se prvi put lako
previdi. Ako se otkrije pogrešna klasifikacija na **postojećoj** opservaciji
(ne na novoj), ispravka nije novi append red nego izmena `price_type` polja
na postojećem redu — `_filter()` u `serbian_market.py` broji svaki red iz
`serbia.jsonl` nezavisno, bez dedup po `source_listing_id`, pa bi dodavanje
novog reda samo udvostručilo opservaciju umesto da je ispravi. Ovo je
suprotno od `outcomes.jsonl`, gde `watch`/`report` uzima najnoviji ishod po
`prediction_id` i ispravka ide kroz nov append red (vidi lekciju o willhaben
URL bugu) — dve različite strukture podataka, dva različita načina ispravke.

## hardverapro.hu ima sopstvenu eksplicitnu oznaku za nestao oglas: "Archív –" / "Archivált hirdetés"

Kao i willhaben ("verkauft"/"Anzeige nicht mehr verfügbar") i olx ("to
ogłoszenie nie jest już dostępne"), i hardverapro ima specifičnu, ne-generičku
oznaku kad oglas više nije aktivan: naslov dobija prefiks "Archív –" i
stranica sadrži tekst "Archivált hirdetés". Otkriveno 2026-08-30 na 3 od 5
praćenih hardverapro oglasa.

**Važno:** "arhivirano" ≠ "prodato". Za razliku od willhaben-ovog "verkauft"
(koje sadrži samu reč "prodato" i tretira se kao SOLD), hardverapro-ovo
"archivált" ne tvrdi ništa o razlogu uklanjanja — oglas može biti arhiviran i
zato što je prodat, i zato što ga je prodavac povukao, i zato što je istekao.
Tretirano kao DELISTED, ne SOLD, po principu 2 (UNKNOWN ≠ 0) — isti oprez kao
za generički 404, samo sa čvršćim dokazom da je stranica namerno uklonjena
(ne anti-bot blokada ili URL bug).
