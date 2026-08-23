---
id: HA-002
title: Implementacija AI GPU Arbitrage Engine-a za EU i Srbiju
status: TODO
assigned: claude-code
dependencies:
  - HA-001
tags:
  - feature
  - gpu-arbitrage
  - deal-engine
  - scraper
created: 2026-08-18
---

# 🚀 Task HA-002: AI GPU Arbitrage Engine

## 🎯 Cilj
Razviti automatizovani modul koji pretražuje oglase polovnih računara i komponenti u EU (eBay, Kleinanzeigen, Willhaben) i Srbiji (KupujemProdajem, Limundo), fokusirajući se na grafičke karte sa velikom količinom VRAM-a pogodne za AI/LLM primenu (RTX 3090, 4090, A4000/A5000, Workstation/Server GPUs). System procenjuje realnu vrednost, izračunava maržu i rizik, te generiše Obsidian note spremne za Kanban i Dataview.

---

## 📐 Arhitektura Modula

### 1. Scraper Layer (`src/scrapers/`)
- **EU Sources:** eBay DE/AT, Kleinanzeigen.de, Willhaben.at.
- **RS Sources:** KupujemProdajem.com, Limundo.com.
- **Target Products:**
  - NVIDIA RTX 3090 / 3090 Ti (24GB)
  - NVIDIA RTX 4090 / 4080 Super / 4070 Ti Super (16GB+)
  - NVIDIA RTX A4000 / A5000 / A6000 / Tesla V100 / A100
- **Handling:** Anti-bot mere, proxy rotacija, rate-limiting, resursno štedljiv HTML parsing (BeautifulSoup4 / Playwright).

### 2. AI Evaluation & Parser (`src/deal_engine/evaluator.py`)
- Korišćenje LLM (Claude API / OpenAI API) za analizu teksta oglasa:
  - Izvlačenje tačne specifikacije (Model, VRAM, Brand, Stanje).
  - Detekcija rizika (Mining rig rasprodaja, oštećenja, nedostatak ambalaže/garancije, sumnjivi nalozi).

### 3. Pricing & Profit Calculator (`src/pricing/calculator.py`)
- **Formula:**
  $$\text{Net Profit} = \text{Target Resale Price (RS)} - (\text{Purchase Price} + \text{Shipping} + \text{Import/Customs Buffer} + \text{Risk Reserve})$$
- **Risk Multipliers:**
  - *No Warranty / Mining:* +15% Risk Buffer
  - *EU Import (Posta/Shipper):* Fiksni dodatak za transport (€25–€50 zavisi od težine)
  - *Verified Local Deal:* Minimalan risk buffer (0–5%)

### 4. Obsidian Sync (`src/obsidian_sync/writer.py`)
- Automatsko kreiranje `.md` fajlova u vault-u pod direktorijumom `dnevnik/deals/` koristeći standardizovani `DEAL-template.md`.

---

## ✅ Definition of Done (DoD)
- [ ] Implementiran skraper za bar 1 EU sajt (Kleinanzeigen ili eBay) i 1 RS sajt (KupujemProdajem).
- [ ] LLM parser uspešno ekstrahuje VRAM i garanciju iz opisa oglasa.
- [ ] Calculator izračunava profit i generiše rizik skor (Low/Medium/High).
- [ ] Generisana Obsidian nota uspešno se prikazuje na Kanban tabli i u Dataview tabeli.
- [ ] Svi novi fajlovi i promane su verzionisane preko Git-a u skladu sa `LINTER-RULES.md`.