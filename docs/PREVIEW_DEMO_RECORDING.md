# Demo Story Studio — click, type and narration guide

Updated October 23, 2026. Stop at **Preview & iterate**. Do not click **Approve & apply**. Service-only recording. Saved initial/refined Service revisions: 31/32; newly generated revision numbers will differ. Latest test evidence and revisions: [REFINEMENT_ACCEPTANCE.md](REFINEMENT_ACCEPTANCE.md). The prompts below were used in the current rehearsal; other wording may require clarification.

## Handout check and recommended video cut

Checked against the [October 2026 Week 3 handout](https://docs.google.com/document/d/1ixizY2Bd-FUkT6nhYPNRVbtP-LFGqUWHP9tB9HgcH6Q/) on October 23. Choose **bring your own use case, code track (LangChain + LangGraph)**. The video must be five minutes or less and show the app, explain the build and AI coding-tool use, and demonstrate the result live. A Google Doc and GitHub code-assets link are separate deliverables; this recording guide does not submit them.

Use **Service — Montréal commercial HVAC** for the entire live flow, including one region refinement. Explain the shared Sales/Service account model without opening a second dashboard. Use the flexible screen-by-screen pacing below; aim for 4:40, leaving 20 seconds of buffer. Provider latency varies: rehearse the pacing; if trimming waits, label the cut rather than implying instant generation.

Stopping at preview is a defensible demonstration of this product’s intended human handoff. Show a real generated preview and a refinement, then explain the unclicked final action. The handout does not explicitly certify a preview-only stopping point, so do not call that instructor-approved or claim activation was demonstrated.

### Screen-by-screen talk track — flexible pacing

Follow the screen, not a stopwatch. The durations are rehearsal targets, not deadlines to click. Finish each explanation, pause briefly, then take the indicated action. Aim for about 4:40 overall; the handout maximum is five minutes. If you need longer on review or clarification, shorten the architecture explanation. Keep the preview and refinement explanation clear. Never describe a result before it appears.

#### 1. Home — introduce your role and the problem · about 25 seconds

**Stay here:** Studio home, with both Sales and Service cards visible. Do not open a dashboard yet.

**Say:** “As a Demo Product Manager for analytics, I help shape pre-sales demos around each customer’s industry and business context. A common task is customizing dashboard labels and connected records so the demo feels relevant. I built Demo Story Studio to help prepare those changes for human review.”

**Point to the Service card and say:** “I’ll show a commercial HVAC service demo for Montréal. Sales and Service share customer accounts, so the story needs to stay consistent across both.”

**Then click:** **Open Service dashboard →**. Wait for the dashboard to load.

#### 2. Current dashboard — show what needs changing · about 25 seconds

**Stay here:** the Service dashboard. If a saved preview is selected, click **Current** first. Show the current label and chart briefly.

**Say:** “This is our starting dashboard, using synthetic data. The charts and records are connected, so adapting the story means more than changing the title.”

**Now click:** **Breakdown**. Open a case with a linked account and point to its customer and owner. Close the record details before continuing.

**Say:** “A customer account can have sales opportunities and service cases. Changing its name must stay consistent wherever it appears, without breaking those links.”

**Then say:** “I’ll describe the changes I want.” **Click Customize this dashboard ✧.**

#### 3. Describe dialog — enter and explain the brief · about 35 seconds

**Stay here:** the open dialog. Paste this into **Your brief**, but do not submit yet.

```text
Commercial HVAC support in Montréal, entire dataset, preview only. Customers: Commercial Property Group. Central→Laval, East→Longueuil, West→Saint-Laurent. Case subjects: Cooling Failure, Refrigerant Leak, Thermostat Fault, Preventive Maintenance. Use eight distinct HVAC equipment families, five distinct HVAC support case types, and {family} service agreement {number} opportunities. Page titles: HVAC Sales Overview, HVAC Sales Pipeline, HVAC Deal Details, HVAC Service Trends, HVAC Service Workload. Preserve facts, IDs, relationships and USD.
```

**With the brief visible, say:** “I’m asking for Montréal service regions, HVAC case subjects and equipment terminology. Because these accounts also have sales records, the brief includes matching service-agreement opportunity names. We’ll stay in Service for this demonstration.”

**Now check:** **Use the entire dataset instead of the visible filters and dates**.

**Say:** “This keeps the shared customer story consistent across the connected dataset while preserving the facts and relationships.”

**Then click:** **Prepare preview**.

#### 4. Generation — explain the agent while the request runs · about 25 seconds

**Stay in the app:** show the processing status. If the preview arrives early, leave it visible and finish this explanation before opening review. Do not switch rapidly between code and the dashboard.

**Say:** “There is one bounded agent behind this. LangChain connects a Qwen model on Nebius to typed tools. It inspects the existing vocabulary, then proposes adaptation rules. LangGraph manages the steps, state and human-review pause. Deterministic backend code creates and validates the candidate records.”

**Wait for an actual result.** If clarification appears, read it, answer it and click **Continue with clarification**. If an error appears, use the failure guidance later in this document; do not say a preview was created.

#### 5. Preview — inspect the connected result · about 40 seconds

**First point to:** **Preview dataset**, the new revision and highlighted **4 Preview & iterate**.

**Say:** “This is a separate preview. The current dataset has not been replaced.”

**Now click:** **Review changes · revision …**. Point to the naming rules.

**Say:** “Rather than reviewing thousands of records, I start with the rules used to generate their names.”

**Now show:** one connected example, then its validation results. Pause on each before speaking.

**Say:** “The connected example ties sales and service records to a common account. We adapt that customer story together, rather than relabeling each dashboard independently. Checks cover protected facts and relationships; I still judge whether the terminology makes sense.”

**Then:** collapse review and remain on **Breakdown**. Open **Region / division**, point to Laval, Longueuil and Saint-Laurent, then select Laval and inspect an HVAC case and its type. Reset the filter and close record details.

**Say:** “The vocabulary now appears in the dashboard and filters. These regions label existing owner groups; this prototype does not dispatch technicians. I want to refine one region name.”

#### 6. Refinement drawer — request one change · about 40 seconds

**Click:** **Refine preview**. With the drawer open, paste this into **Review note or requested change**. Do not submit until you have explained it.

```text
Change Central region to Montréal Centre.
```

**Say before submitting:** “I want the group originally called Central—now shown as Laval—to be called Montréal Centre. The other regions and naming rules should stay unchanged.”

**Now click:** **Request changes**.

**While it runs, say:** “The agent proposes a small patch, and the server preserves the omitted rules. It creates another preview revision for me to review.”

**If clarification appears:** read it. If it asks which source region to rename, enter `Change Central region to Montréal Centre.` in **Your clarification** → **Continue with clarification**. Explain: “When the request is ambiguous, the agent asks rather than guessing.”

**After success only:** the drawer closes and the main page selects the new preview. Point to the actual changed-field summary. Open **Region / division** and show **Montréal Centre**, with Longueuil and Saint-Laurent retained. Select the renamed region and inspect a case’s owner division, then reset the filter.

**Say:** “The refinement is now visible on the page. I check that only the owner-division labels changed and that the other naming rules remain intact. Closing the drawer alone does not apply anything; a successful request creates this new preview.”

Do not promise eight changed labels unless the displayed result confirms that count. If the result differs from the intended patch, review it honestly rather than narrating success.

#### 7. Memory — explain what persists · about 25 seconds

**Now expand:** **Saved preferences, recipes and conversation memory**. Stay on that panel; do not save a new memory during this take.

**Say:** “PostgreSQL checkpoints retain the conversation and workflow state. Mem0 is a separate layer for explicitly confirmed preferences and successful recipes across sessions. It does not own the business records or approve changes. Its lifecycle was tested separately; I’m explaining that capability here, not demonstrating a fresh memory save.”

**Then:** collapse the panel.

#### 8. Build process — briefly show Codex · about 30 seconds

**Switch to:** this Codex conversation, with one actual coding request from the reference section visible. Show the request before explaining it. Then show `backend/app/agent/refinement.py` or `docs/REFINEMENT_ACCEPTANCE.md` as the resulting artifact.

**Say:** “I used Codex to build and test iteratively, with React and TypeScript for the interface, FastAPI for the backend and PostgreSQL for the data. I supplied the product direction and tested the experience. When refinement changed unrelated labels, we replaced full regeneration with this sparse-patch approach and added regression tests.”

**Then return to:** the app’s preview. Do not show environment files, keys or private logs.

#### 9. Human handoff — close on the preview · about 25 seconds

**Click:** **Review changes · revision …** and locate **Approve & apply**. Point to it; **do not click it**.

**Say:** “This is the human decision point. Approve and apply would validate and activate this exact revision, replacing the current dataset. I’m stopping at preview so I can review further. Connecting and publishing to a real customer instance is future scope; this build demonstrates the customization and review workflow.”

**Finish with the preview visible.** No Sales dashboard walkthrough is needed: the shared-account explanation and connected review example establish the relationship. If you include a saved preview, identify it as previously generated.

### How it was built — presenter reference

| Component | Actual role and accurate wording |
| --- | --- |
| React, TypeScript, Vite, Plotly | Dashboard, filters, record evidence, review and refinement drawer. |
| Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL | Typed API/contracts, relational data, immutable previews, deterministic transformations and protected lifecycle. |
| Single bounded agent | Model chooses tools/arguments within a constrained graph. No multi-agent team, separate reviewer agent or unrestricted autonomous database editing. |
| LangChain + LangGraph | Model/tool integration plus state, routing, durable checkpoints, clarification and human-review interrupts. |
| Nebius Qwen/Qwen3-235B-A22B-Instruct-2507 | Configured live inference model, verified from local runtime configuration. Fireworks is supported but is not the provider used for these rehearsals. |
| Mem0 managed memory | Confirmed qualitative preferences and successful recipes. Prior save, recall, update and forget lifecycle tests passed. Current recording does not need a live memory write. |
| PostgreSQL checkpoints | Current run/messages, reviewed proposal, evidence and interrupt state; distinct from cross-session preference memory. |
| Local traces and evaluations | Recorded tool/cost evidence and local test results. LangSmith live tracing remains unverified and is disabled; do not present it as the observed tracing system. |
| Codex | AI coding collaborator used for implementation, UI revisions, tests and debugging. You supplied product direction, reviewed behavior and chose the scope. |

**Memory demonstration boundary:** At this guide update the external Mem0 gate is disabled; explaining the implemented memory design is accurate, but do not claim the current Sales/Service preview retrieved a helpful preference or demonstrate a fresh Mem0 save as if it were available. Previously verified lifecycle evidence is in `evals/phase2-mem0-live-results.json`. If you show that evidence, label it as a prior test.

### Actual coding prompts you can show in Codex

These are owner requests from this build conversation, distinct from the business prompts entered into the app:

> “Yes, let's build the industry adaptation capability. Make that the main use case and update the plan and submission markdown to reflect it.”

> “Yes, go ahead and redesign the review screen around the summary, naming rules, a few connected examples, and validation results. Include the futuristic UI improvements we discussed too.”

> “Go ahead and fix the refinement issues so it only changes what I ask for, then test both sales and service again through preview and iteration.”

Show one prompt plus the resulting source or test evidence. No need to expose API keys, environment files, passwords or private logs. The handout asks you to describe AI coding-tool use; a short authentic Codex view makes that concrete.

### Handout coverage checklist

- [x] Project overview, target user and value: opening narration.
- [x] Dataset and implemented scope: nine synthetic tables; local customization, future org deployment separated.
- [x] Agent control flow, tools, state, human review and failures: timed narration and reference table.
- [x] Build tools and actual AI coding prompts: architecture and Codex segment.
- [x] Iterations and learning: unwanted label changes → sparse patch; hidden clarification → drawer fix.
- [x] Exact app inputs and expected results: screen-by-screen walkthrough above.
- [ ] Record and time the final video at five minutes or less; confirm the live result is visible.
- [ ] Prepare/share the separate Google Doc and reviewed GitHub link; submit through the handout form when ready.

## Before recording

Open http://127.0.0.1:8010/. AI is enabled at the owner’s request until they ask to close it. The remaining monitored allowance and project cap still apply; unknown-cost failures can stop calls. Viewing a saved preview needs no model call. For a saved demonstration, choose the dashboard → Revision history → desired revision → Preview revision, and say it was generated earlier. Keep a saved preview available if a live provider call fails.

## Service recording reminders

- Follow steps 1–9 above; the initial brief and refinement prompt sit beside their clicks and narration.
- Use a case with an account for the connected-record explanation. Some synthetic cases have no account; that is retained source coverage, not a broken join. Do not imply every case has a matching opportunity.
- Sales opportunities and Service cases reference the same account table; they are not directly linked to each other. The shared account provides the connection.
- The region change relabels existing owner divisions; it does not relocate customers, reassign cases, schedule technicians or create routes.
- Currency remains USD, as requested in the brief. This is vocabulary adaptation, not a full Canadian currency/localization implementation.
- Stop at **Preview & iterate**. Point to **Approve & apply**, explain it, and leave it unclicked.

## Explain the tools accurately

- Confirmed memory retrieval supplies optional context at startup; it does not authorize changes.
- `inspect_industry_context` reads current families, case subjects, regions, case types and page meanings.
- `propose_industry_adaptation` submits the initial structured vocabulary proposal.
- `refine_industry_adaptation` submits only explicit field/category edits during iteration; `request_clarification` handles missing/ambiguous intent.
- Deterministic services materialize the revision, validate relationships/protected facts and compute actual differences. These are workflow operations, not additional agents.
- Approval and activation are owner-controlled backend transitions outside the model’s tool set.

## If a live attempt fails

Do not narrate it as successful. Say: “The request stopped safely and current data is unchanged. I can clarify the wording or use the saved preview to continue reviewing.” Do not automatically retry an unknown-cost timeout. Exact titles and explicit mappings reduce ambiguity but cannot guarantee every provider call succeeds.
