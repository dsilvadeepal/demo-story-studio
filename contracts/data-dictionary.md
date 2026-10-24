# Synthetic business-data dictionary

The dashboards share nine business tables. Column definitions and constraints are authoritative in [backend/app/db.py](../backend/app/db.py).

| Table | Purpose and relationships |
| --- | --- |
| `accounts` | Customer names, types and industries; shared by Sales and Service. |
| `contacts` | Contact names and titles, linked to an account. |
| `users` | Record owners, with department and division labels. |
| `products` | Product names, codes and families. |
| `pricebooks` | Named price lists. |
| `pricebook_entries` | Product and pricebook relationship, with unit price. |
| `opportunities` | Sales deals linked to an account and owner; includes stage, probability and dates. |
| `opportunity_line_items` | Opportunity products via pricebook entries, with quantity and line price. |
| `cases` | Service cases with subject, type, priority, status, origin and dates; linked to owner and optionally account/contact. |

Each business table has a composite `dataset_id` + `id` primary key and dataset-scoped foreign keys. Sales opportunities and Service cases connect through shared accounts, not a direct opportunity-to-case foreign key. A case contact must belong to its linked account. Cases without accounts retain that absence.

Money uses `NUMERIC(18,2)`, quantities `NUMERIC(12,2)`, and probability `NUMERIC(5,2)` as a percentage. Timestamps use UTC. Opportunity amounts derive from quantity × line price; there is no invented header amount. See [metric decisions](metric-decisions.md).

A separate `datasets` manifest tracks as-of date, generator version, seed, checksums, row counts, revision, semantic version and presentation metadata. It is not one of the nine business tables. Workflow, memory, budget and approval tables are also outside this business-table count.

The baseline uses seed 42, generator version 1 and an as-of date of October 21, 2026. Records are synthetic; no private customer rows are included.
