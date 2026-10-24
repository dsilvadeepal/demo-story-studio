# Target dictionary

Nine tables and all source aliases are in ../../replica-field-map.md. Target column definitions are authoritative in backend/app/db.py. Each has dataset_id + id primary key and dataset-scoped foreign keys. Money NUMERIC(18,2), quantities NUMERIC(12,2), probability NUMERIC(5,2) percent, UTC timestamptz. Case account and contact are optional; contact/account consistency is enforced. Opportunity amounts derive from lines. Cases without accounts never acquire invented accounts.

Manifest records fixed as-of 2026-10-21, generator version 1, seed 42, canonical checksums, counts, revision and semantic version. No source rows or private company data are used.
