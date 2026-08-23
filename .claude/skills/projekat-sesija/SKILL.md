---
name: projekat-sesija
description: Master radni tok za AI Hardware Arbitrage Serbia. Koristi na početku svake radne sesije, kad korisnik kaže "nastavljamo", "gde smo stali", "sledeći zadatak", "šta je sledeće", ili na kraju sesije kad kaže "zatvaramo sesiju", "to je za danas", "upiši napredak".
---

# AI Hardware Arbitrage Serbia — protokol radne sesije

CLAUDE.md nosi pravila i kontekst (učitan je automatski — ne ponavljaj ga).
Ovaj skill nosi TOK: kako se sesija otvara, bira zadatak, izvršava, i
zatvara. Jedan glavni zadatak po sesiji, osim ako korisnik eksplicitno traži
više.

Ovaj skill zamenjuje ručno kopiranje Prompta #2 i #3 iz
`promptovi/PROMPTOVI.md` — ista logika, samo se sada aktivira automatski na
odgovarajuće fraze. Promptovi ostaju dostupni za eksplicitno/ručno pozivanje
ako je ikad potrebno.

## 1. Otvaranje sesije (uvek, ovim redom)

1. Pročitaj `[[PROGRESS]]` — "Gde smo stali", Gotovo/U toku/Blokirano,
   Sledeći zadatak
2. Pročitaj poslednjih 5 unosa u `[[DNEVNIK-NAPRETKA]]` (najnoviji na vrhu
   ili dnu, po konvenciji fajla)
3. Pročitaj `[[MASTER-PLAN]]` — Prioritet, aktivni workstream, Raspored po
   nedeljama (uporedi današnji datum), i sekciju Zavisnosti — zadatak
   blokiran na #čeka-vlasnika se ne bira dok ne stigne
4. Predloži **1 glavni zadatak** (+ eventualno 1 quick-win ≤15 min) i
   sačekaj potvrdu ako izbor nije očigledan iz korisnikove poruke — ne
   počinji da radiš pre potvrde

Ako `PROGRESS.md`, `DNEVNIK-NAPRETKA.md` ili `MASTER-PLAN.md` još imaju
`{{PLACEHOLDER}}` vrednosti (projekat nije bootstrap-ovan), reci to
korisniku i ponudi Prompt #1 iz `promptovi/PROMPTOVI.md` umesto da nagađaš
sadržaj.

## 2. Izvršavanje

- Radi u okviru workstream-a iz `MASTER-PLAN.md` — ne skači između njih bez
  razloga u istoj sesiji
- Pre veće izmene: analiza → predlog opcija → odobrenje vlasnika →
  izvršenje (za nepovratne/destruktivne izmene)
- Ne izmišljati brojeve, identifikatore, cene, datume — ako nešto nije
  potvrđeno u CLAUDE.md/PROGRESS.md, reci "nema podataka" i pitaj

## 3. Zatvaranje sesije (uvek, ovim redom)

1. `[[DNEVNIK-NAPRETKA]]` — novi unos: `## {{YYYY-MM-DD}} \`[tag]\` —
   kratak naslov`, sa konkretnom bullet listom (ne "radio na SEO" nego
   "dodao 3 meta title-a"), odlukama, blokerima, sledećim korakom
2. `[[PROGRESS]]` — **prepiši** (ne dodavaj) sa novim stanjem: Gotovo / U
   toku / Blokirano / Sledeći zadatak / Poslednje sesije
3. `[[MASTER-PLAN]]` — štikliraj završene zadatke, ažuriraj status workstream-a
4. Ako je doneta veća odluka danas → `[[odluke/_pregled-odluka]]`
5. Ako je naučena lekcija (bug, gotcha, pogrešna pretpostavka) →
   `[[reference/naucene-lekcije]]`
6. Otvorena pitanja za vlasnika → označi #čeka-vlasnika u MASTER-PLAN.md i
   jasno navedi šta se čeka

## 4. Napomena o auto-sync-u

Ako projekat koristi Obsidian Git ili sličan auto-sync alat (vidi CLAUDE.md
§9), ne komituj ručno u git osim na eksplicitan zahtev — sync radi to sam.
