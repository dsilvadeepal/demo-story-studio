# Demo Story Studio — current product requirements

Updated October 23, 2026 (America/New_York). This is the current product scope, superseding the early Retail/import proposal preserved in the archive (local working-copy reference; not included in this publication). The detailed implementation history is in the phase-two plan (local working-copy reference; not included in this publication).

## Product outcome

Help a demo builder adapt a connected Sales and Service dashboard to a prospect’s industry and geography. The main use case is semantic adaptation: customer and product names, opportunity names, service subjects, regions, case types and page titles must tell the same story across filters, charts, detail records and shared relationships.

This is more than replacing words in a screenshot. An opportunity name derives from its linked product family; service cases remain connected to the same accounts, contacts and owners; region filters use the revised owner divisions. Deterministic transformations preserve IDs, relationships and numeric facts while the model selects vocabulary. The human evaluates whether the business story is appropriate before publishing the exact revision.

Primary demo examples: Renewable Energy Sales and Montréal commercial HVAC Service. These are test scenarios, not hardcoded presets. The same bounded vocabulary contract supports other industries and regions.

## Implemented scope and boundaries

- Local, private React/TypeScript/Vite application with Plotly charts, FastAPI and PostgreSQL.
- Nine synthetic business tables: accounts, contacts, users, products, pricebooks, pricebook_entries, opportunities, opportunity_line_items and cases. Seed 42; baseline as-of October 21, 2026.
- Three Sales pages: Executive Summary, Pipeline Analysis, Detail Analysis. Two Service pages: Trend, Breakdown. Industry-specific page titles preserve these analytical meanings.
- Real database-backed previews, comparisons, connected examples, validation, revision history, recovery and explicit owner approval/activation.
- One bounded LangChain/LangGraph assistant, monitored Nebius calls, confirmed Mem0 preferences/recipes, durable checkpoints and local traces. LangSmith live tracing acceptance remains pending.
- Numeric/date transformations remain supporting capabilities. Industry adaptation requires explicit whole-dataset scope because shared entities affect both dashboards.
- No Retail, live source refresh, Salesforce/Tableau writes, production tenant connections, automatic deployment, currency conversion, technician scheduling, dispatch optimization or new business entities.

Montréal HVAC is a semantic service-demo adaptation. Existing owners can be described in the story as service teams, but the application does not create technician skills, routes, work orders or scheduling facts. Money remains USD unless a future separately designed currency capability is added.

## Five-phase user journey

| Phase | Required experience |
| --- | --- |
| 1 Choose | Two clear Sales and Service entry points; concise introduction. Brand/title returns home. |
| 2 Inspect | Working dashboard stays visible. Clearly label current data versus saved preview, revision and evidence context. |
| 3 Describe | One Customize action opens a short brief form. Industry adaptation explicitly selects the whole dataset. Audience/purpose are optional. |
| 4 Preview & iterate | Automatically show a successfully created preview and highlight this phase. Expand Review changes for naming rules, representative connected examples and full-dataset checks. Detailed record differences remain optional. |
| 5 Approve & apply | One explicit owner action states that it replaces the current dataset. Backend still binds approval to the exact hash/revision, then activates atomically. The model cannot perform either action. |

The recording deliberately stops at Preview & iterate. Talk through the final owner action without clicking it.

## Refinement contract

The side drawer is for a refinement instruction only. It retains text and an actionable error if generation fails. On success it closes, selects the new preview on the main page and shows actual changes since the preceding preview. Closing the drawer alone neither generates nor applies changes.

For an existing industry preview, the agent calls `refine_industry_adaptation` with sparse edits rather than generating a replacement rule set. Each edit identifies a supported field, an existing category/page when applicable, exact replacement wording and a verbatim affirmative instruction from the current request. The server merges that edit into the previously reviewed proposal. Omitted rules remain unchanged; all normal vocabulary and dataset validations run again. Each successful refinement creates a new immutable revision.

Use precise instructions, for example “Change opportunity template to {family} installation project {number}” or “Change region Laval to Montréal Centre.” Ambiguous or unsupported requests require clarification; arbitrary natural-language rewrites are not guaranteed. Mapping refinements currently target existing mapping entries; adding a mapping when no mapping existed is outside this patch contract. Numeric-operation refinement uses the existing bounded proposal path and does not gain this industry-specific preservation guarantee.

## Agent and authority

Initial industry generation: retrieve confirmed memory context → inspect industry vocabulary → propose industry adaptation → deterministic candidate materialization, comparison and validation → human review interrupt.

Industry iteration: load reviewed rules from the checkpoint → request-grounded sparse refinement tool (or clarification) → deterministic merge, materialization and validation → new review interrupt. Full checkpoints retain evidence; compact inference context avoids resending unrelated history. Per-generation limits are six model calls, twenty tool calls, two repair attempts and 120 active seconds, excluding human waiting. Financial reservations remain cumulative across generations.

PostgreSQL owns records, revisions, approval, budgets and workflow checkpoints. Mem0 is optional confirmed preference/recipe context, never business or approval authority. Provider credentials stay in ignored server-side configuration. No unrestricted SQL-writing tool or browser database credentials.

## Integrity, review and cost requirements

1. Industry transformations preserve row counts, IDs, foreign keys, quantities, prices, dates, stages and metric definitions. Optional region/case-type mappings change labels, not assignment/status semantics.
2. Compare matching filters and metric definitions. Drop incompatible old filters visibly when switching vocabulary; preserve valid filters and page context.
3. Review naming rules and a few linked examples, backed by checks across the complete dataset. Samples are not a substitute for validation.
4. Keep baseline immutable; preview creation and refinement never move the active pointer. Reject stale approval, invalid hashes and unapproved activation. Mutation retries are idempotent.
5. Reversible history cleanup archives eligible old previews while protecting active, approved and workflow-referenced revisions. The visible-history cap is 20; archived data still occupies storage.
6. Live model testing remains within the owner-approved $1 cumulative monitored allowance and $10 cumulative Nebius project ceiling. A timed application gate is not proof of a provider billing hard stop. No unattended paid fallback.

## Future product vision — outside this build

A future user could sign in, connect a permitted demo org/instance, adapt an isolated copy and publish the reviewed result to that chosen destination. Production connectors, tenant isolation, per-org authorization, deployment mapping and rollback require separate design and acceptance. This build demonstrates the middle portion: inspection, coherent adaptation, preview, refinement and local human-controlled activation.

## Acceptance and evidence

The current [project plan](PROJECT_PLAN.md) tracks implemented work and remaining acceptance. [Refinement verification](docs/REFINEMENT_ACCEPTANCE.md) records the latest local and live checks, revision IDs, failures and limitations. Test results establish bounded local behavior; they do not prove hosted deployment, universal semantic correctness or production integration.
