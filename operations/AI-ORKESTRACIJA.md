# AI Orkestracija

> Claude Code je orkestrator. Eksterni modeli su savetnici sa read-only pristupom.
> Odluku, izmenu fajla i commit uvek radi orkestrator.

## Status provajdera (provereno 2026-08-19)

| Provajder | Stanje | Kako se koristi |
|---|---|---|
| **Copilot CLI** | ✅ radi, autentikovan | `copilot -p` — headless, troši AI kredite |
| **Grok CLI** | ✅ instaliran i prijavljen | `grok -p`, troši xAI kvotu |
| **Gemini CLI** | ❌ nije instaliran | `npm i -g @google/gemini-cli` + `GEMINI_API_KEY` |
| **Ollama** | ⚠️ ima `qwen3:4b`, ali **pada zbog RAM-a** | vidi ispod |

`delegate.sh` od 2026-08-19 podržava i `--provider ollama` i `--provider gemini`.
U `auto` režimu redosled je: ollama (lokalno, besplatno) → gemini (besplatna
kvota) → copilot → grok. Oba nova provajdera nemaju alate za čitanje repoa —
vide samo ono što im se pošalje kroz `--files`, pa je prazan `--files` greška.

**Ollama trenutno ne radi na ovoj mašini:** `qwen3:4b` sa podrazumevanim
kontekstom traži ~20 GiB, a slobodno je ~8,8 GiB (`model requires more system
memory`). Da bi se koristio, treba smanjiti kontekst na serveru
(`OLLAMA_CONTEXT_LENGTH`, postavlja se za `ollama serve`, ne za klijenta) ili
uzeti manji model. Do tada review ide na copilot.

Provera u svakom trenutku:

```bash
bash .claude/bin/ai-status.sh
```

## Podela posla

| Radi orkestrator (Claude Code) | Može da se delegira |
|---|---|
| Sve izmene fajlova i commit-i | Code review i drugo mišljenje |
| Deterministički kod za novac, ROI, score | Predlozi test slučajeva |
| Odluke o arhitekturi i poslovnim pravilima | Istraživanje (izvori + datum) |
| Compliance procena marketplace pristupa | Draft dokumentacije |
| Interpretacija oglasa u produkciji (`deal_engine/evaluator.py`) | — |

**Nikad se ne delegira:** obračun novca, verifikacija ToS-a/pristupa, upis u
`odluke/`, i bilo šta što daje broj koji ide u `Opportunity`. Razlog: princip 4
iz `CLAUDE.md` — AI tumači tekst, deterministički kod računa novac (D-005).

## Delegacija

```bash
bash .claude/bin/delegate.sh --role review \
  --task "Proveri risk scoring na edge slučajevima" \
  --files src/deal_engine/risk.py,src/pricing/calculator.py
```

Uloge: `review` · `tests` · `research` · `docs`.
Opcije: `--provider auto|copilot|grok`, `--task @fajl.md`.

Šta skripta garantuje:

1. **Read-only delegat** — dobija samo `view,glob,grep` (+`web_fetch` za
   `research`). Ne može da kreira ni menja fajlove.
2. **Zaštita tajni** — odbija zadatak ili fajl koji liči na kredencijal
   (`sk-`, `ghp_`, `xai-`, `AKIA`, privatni ključevi, `*_API_KEY=`), i sve
   `.env`, `secrets/`, `*.pem`, `*.key` putanje. Ništa se ne šalje.
3. **Pravila u promptu** — delegatu se svaki put prosleđuju projektna pravila:
   ne izmišljaj podatke, UNKNOWN ≠ 0, ne računaj novac, ne predlaži zaobilaženje
   ToS-a, ne menjaj fajlove.
4. **Provenance** — svaki poziv se loguje u `operations/ai-delegacija-log.jsonl`
   (vreme, provajder, uloga, fajlovi, hash prompta, exit kod, putanja izlaza).
   Izlazi idu u `.claude/delegation-out/`.

## Obavezan korak posle delegacije

Nalaz eksternog modela **nije dokaz**. Orkestrator ga verifikuje pre primene:
reprodukuj problem testom, pa tek onda menjaj kod. Lažno pozitivni nalazi su
česti — u prvom prolazu 2 od 6 nalaza su bila stvarna.

## Šta se šalje van

Delegacija šalje sadržaj fajlova xAI-ju odnosno GitHub-u. Vault je poslovni
dokument — ne delegiraj `odluke/`, `operations/PAPER-TRADING.md` ni bilo šta sa
brojkama kapitala. Kod u `src/` je bezbedan za slanje.

## Cena

Copilot naplaćuje AI kredite po pozivu: ~0.36 za trivijalan poziv, ~2.14 za
review tri modula. Ograniči po sesiji preko `--max-ai-credits` ako treba.
