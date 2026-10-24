# Demo Story Studio

A personal learning project for adapting connected analytics demos to a customer's industry—without breaking the records, relationships or numbers behind the dashboard.

As a Demo Product Manager for analytics, I regularly need pre-sales demos to reflect a customer's business context. Demo Story Studio explores how a bounded AI agent can prepare those changes for human review: company and product names, opportunity names, case subjects, regions, case types and dashboard titles stay connected across Sales and Service.

## What the app does

**Choose → Inspect → Describe → Preview & iterate → Approve & apply**

1. Choose Sales or Service and inspect the current dashboard.
2. Describe the desired industry, terminology and regions.
3. Generate an isolated preview backed by actual synthetic database records.
4. Review naming rules, representative connected examples and full-dataset checks.
5. Refine specific wording through a side drawer. Industry refinements merge a small patch into the reviewed rules, preserving omitted rules.
6. Optionally approve and apply the exact revision using one explicit owner action. The backend separately validates approval and activation.

The demo recording stops at **Preview & iterate**. Creating or refining a preview never replaces the current dataset.

### Example scenarios

- **Renewable Energy Sales:** commercial-property customers, solar/battery equipment and linked deployment opportunities; refine only opportunity wording to “installation project.”
- **Montréal HVAC Service:** HVAC equipment and service terminology with regional owner labels; refine one region to “Montréal Centre.” Region changes relabel existing groups; they do not schedule technicians or create dispatch routes.

Both are examples of the generic adaptation contract, not hardcoded industry presets. Currency and analytical definitions remain unchanged.

## Architecture

| Component | Role |
| --- | --- |
| React, TypeScript, Vite, Plotly | Five dashboard pages, filters, record evidence and review UI |
| FastAPI, Pydantic, SQLAlchemy | Typed APIs and bounded transformations |
| PostgreSQL | Nine synthetic business tables, immutable revisions, approval, budgets and workflow checkpoints |
| LangChain + LangGraph | One tool-calling agent, stateful control flow, clarification, bounded repair and human-review interrupts |
| Nebius | Live rehearsals used `Qwen/Qwen3-235B-A22B-Instruct-2507`; Fireworks is an optional supported provider |
| Mem0 | Explicitly confirmed cross-session preferences and successful recipes; never record or approval authority |
| Local traces | Tool and cost evidence; external LangSmith tracing is disabled pending separate verification |

Initial adaptation uses `inspect_industry_context` and `propose_industry_adaptation`. Iteration uses `refine_industry_adaptation` or `request_clarification`. Deterministic services materialize and validate candidates. The model has no approval/activation tool and no unrestricted SQL-writing access.

Sparse industry edits require exact replacement wording grounded in the current request. Ambiguous or unsupported instructions may require clarification. This preservation guarantee applies to industry-rule refinement; numeric/date edits retain their separate bounded proposal path.

## Run locally

Prerequisites: Python 3.11+, Node 20+, Docker. Locally tested with Python 3.14.3, Node 24.18 and PostgreSQL 17.

```sh
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.lock
npm --prefix frontend ci
backend/.venv/bin/python scripts/setup_local.py
npm --prefix frontend run build
backend/.venv/bin/python scripts/serve.py
```

Open **http://127.0.0.1:8010**. The generated owner password is stored locally in `.local/owner-password`. PostgreSQL binds to loopback port 55439 and persists in the `demo-story-studio-pg` Docker volume. These commands do not create hosted resources.

Use an ignored `.env` for provider keys; `.env.example` contains placeholders only. Restrict `.env` to mode 0600. Credentials alone do not enable live calls: provider and memory allowances are separately gated. Do not upload `.env`, `.local`, database dumps, private logs or course materials.

## Validation

```sh
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

Backend tests create isolated disposable PostgreSQL databases and roles. Run local setup first; never point test provisioning at a production database.

Latest local verification: **135 backend tests passed**, followed by **20 targeted regressions** after final refinement changes; **37 frontend tests and the production build passed**. These are local results, not hosted acceptance.

Live preview-only rehearsals verified:

- Sales 29 → 30: only 1,200 opportunity names changed.
- Service 31 → 32: only eight owner-region labels changed, after clarification.
- All other rules and both dashboards' aggregate metrics stayed unchanged; baseline revision 1 remained active.

An earlier initial Sales attempt failed validation safely. Human review remains necessary for semantic realism; successful tests do not guarantee every natural-language request or provider call succeeds.

## Data and safety boundaries

The baseline is reproducibly generated synthetic data (seed 42, as-of October 21, 2026). Nine business tables cover accounts, contacts, users, products, pricebooks, pricebook entries, opportunities, opportunity lines and cases. This is an independent learning project, not an official Salesforce product or a production CRM integration.

- Preserve IDs, relationships, numeric facts, dates, stages and metric definitions during industry adaptation.
- Bind approval to the exact immutable revision and reject stale activation.
- Keep execution limits per generation and financial accounting cumulative; unknown model charges retain reservations.
- Archive eligible old previews reversibly; archive does not reclaim disk storage.
- No customer data, source-system writes, production tenant connections or automatic org deployment.

## Deployment

The current tested runtime is local. Replit deployment is being prepared and is not yet claimed as verified. Hosting needs persistent PostgreSQL, separate restricted runtime roles, secure owner authentication, secrets and account-specific cost checks. A frontend-only deployment cannot run this application. Local model allowances must not be copied to a second environment as if they were additional credit.

## Project documents

- [Current product requirements](FOUNDATION_PRD.md)
- [Current build plan](PROJECT_PLAN.md)
- [Recording walkthrough and talk track](docs/PREVIEW_DEMO_RECORDING.md)
- [Refinement acceptance](docs/REFINEMENT_ACCEPTANCE.md)

Built iteratively with Codex: product-directed implementation, local regression testing, live rehearsals and UI review. Production sign-in, connection to individual customer/demo instances and deployment into those instances remain future scope.
