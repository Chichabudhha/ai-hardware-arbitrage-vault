# CLAUDE.md — AI Hardware Arbitrage Serbia

> Source of truth za pravila rada Claude Code-a. Detaljna specifikacija je u `requirements/`, `architecture/`, `data/`, `marketplace/`, `pricing/` i `deal-engine/`.

## 1. CILJ PROJEKTA

Sistem pronalazi potcenjen polovan hardver koji se može nabaviti u Srbiji ili Evropi, izračunava stvarni landed cost u Srbiji, procenjuje realnu prodajnu cenu na srpskom tržištu i rangira prilike po očekivanom profitu, ROI, riziku i poverenju u podatke.

**Source markets:** Srbija + Evropa.
**Resale market:** Srbija.
**Primarni fokus MVP-a:** NVIDIA GPU sa visokim VRAM-om i AI upotrebom.

## 2. PRINCIPI

1. Ne izmišljaj podatke, cene, kurs, poreze, troškove, identifikatore ili dostupnost.
2. `UNKNOWN` nije isto što i `0`.
3. Asking price nije sold price.
4. AI tumači nestrukturisane podatke; deterministički kod računa novac, ROI i score.
5. Svaki izvedeni podatak mora imati provenance i timestamp.
6. Raw observations se ne prepisuju niti brišu zbog novih procena.
7. Marketplace connector se implementira samo putem dozvoljenog/API/feed/manual mehanizma. Ne zaobilaziti autentikaciju, rate limit, robots, access controls ili ToS.
8. Ne vršiti kupovinu automatski. Sistem daje BUY / NEGOTIATE / WATCH / SKIP preporuku; odluku donosi vlasnik.
9. Ne menjaj arhitekturu ili poslovna pravila bez odluke u `odluke/`.
10. Pre implementacije proveri `PROGRESS.md`, poslednje unose dnevnika i `MASTER-PLAN.md`.

## 3. SOURCE OF TRUTH

- `00-INDEX.md` — ulazna tačka
- `PROGRESS.md` — trenutno stanje
- `MASTER-PLAN.md` — faze i gate kriterijumi
- `requirements/REQUIREMENTS.md` — šta sistem mora da radi
- `architecture/ARCHITECTURE.md` — kako je sistem organizovan
- `data/DATA-MODEL.md` — canonical data model
- `marketplace/MARKETPLACE-STRATEGY.md` — izvori i pravila pristupa
- `pricing/PRICING-ENGINE.md` — procena srpske prodajne cene
- `deal-engine/DEAL-ENGINE.md` — landed cost, profit, ROI i scoring
- `odluke/_pregled-odluka.md` — odobrene odluke
- `reference/naucene-lekcije.md` — trajne lekcije

## 4. RADNI TOK

ANALYZE → SPEC/DECISION → IMPLEMENT → TEST → DOCUMENT → UPDATE PROGRESS → COMMIT/SYNC.

Jedan glavni task po sesiji je podrazumevan. Više taskova samo ako su direktno povezani ili korisnik to eksplicitno traži.

## 5. DATA QUALITY

Obavezni atributi za finansijske zaključke: source, listing ID, observed_at, currency, original price, product match, price type, confidence.

Ako nedostaje podatak koji utiče na landed cost ili resale estimate, rezultat je `INSUFFICIENT_DATA`, ne procena predstavljena kao činjenica.

## 6. SECURITY

API ključevi, tokeni, cookies, session data i privatni kredencijali nikad u vault, Git ili log. Koristi `.env`/OS secrets i `.gitignore`.

## 7. AI ORKESTRACIJA

Claude Code je orkestrator. Eksterni modeli (Copilot, Grok, Gemini) su savetnici
sa read-only pristupom i pozivaju se preko `.claude/bin/delegate.sh`.

Delegirati se sme: code review, predlozi testova, istraživanje, draft dokumentacije.

Ne sme se delegirati: obračun novca, ROI i score; verifikacija marketplace
pristupa; upis u `odluke/`; izmena fajlova; commit. Eksterni nalaz se verifikuje
testom pre primene — nalaz nije dokaz.

Svaki poziv se loguje u `operations/ai-delegacija-log.jsonl`. Detalji:
`operations/AI-ORKESTRACIJA.md`.

## 8. JEZIK I KOMUNIKACIJA

Dokumentacija i komunikacija sa vlasnikom: srpski ekavica. Kod, promenljive, API modeli i commit poruke: engleski.

Kratko, precizno, operativno. Bez nepotrebnog objašnjavanja.
