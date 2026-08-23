# Dashboard

## Open tasks

```dataview
table priority, workstream, status, blocked
from "tasks"
where status != "done"
sort priority asc
```

## Owner decisions

```dataview
table status
from "odluke"
where contains(file.content, "#čeka-vlasnika")
```

## Active opportunities

Kada aplikaciona baza bude dostupna, dashboard će čitati opportunity data iz aplikacije. Obsidian ostaje project-control layer, ne production database.
