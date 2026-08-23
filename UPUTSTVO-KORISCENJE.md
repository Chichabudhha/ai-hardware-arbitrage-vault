# Uputstvo — AI Hardware Arbitrage Serbia

## 1. Pokretanje

Otvori vault u Obsidian-u i pokreni Claude Code iz root foldera:

```powershell
cd putanja\\do\\ai-hardware-arbitrage-serbia
claude
```

## 2. Prva sesija

Pokreni `/gde-smo-stali` ili reci: `nastavljamo`.
Claude prvo čita `PROGRESS.md`, dnevnik i `MASTER-PLAN.md`.

Prvi task je `[[tasks/HA-001-bootstrap]]`. Ne implementirati application code dok W0 nije zatvoren.

## 3. Obsidian

Vault koristi postojeći workflow template i namenjen je za:
- Obsidian Git — sync/versioning
- Dataview — dashboards i task/market views
- Kanban — operativni task board
- Linter — Markdown/frontmatter consistency

Ne čuvati secrets u vault-u.

## 4. Sesije

Početak: `nastavljamo` / `/gde-smo-stali`.
Kraj: `zatvaramo sesiju` / `/zatvori-sesiju`.

Claude ažurira `DNEVNIK-NAPRETKA.md`, `PROGRESS.md`, odluke i lessons learned prema skill-u.
