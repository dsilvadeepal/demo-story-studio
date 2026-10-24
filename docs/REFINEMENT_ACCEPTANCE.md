# Refinement reliability acceptance — October 23, 2026

## Verified outcome

| Scenario | Initial preview | Refined preview | Actual changes from preceding preview | Other rules / metrics | Active data |
| --- | ---: | ---: | --- | --- | --- |
| Renewable Energy Sales | 29 | 30 | 1,200 opportunity names: deployment → installation project | Every other rule unchanged; Sales and Service aggregate metrics unchanged | Revision 1 |
| Montréal HVAC Service | 31 | 32 | 8 users.division labels: Laval → Montréal Centre | Other region entries and all other rules unchanged; Sales and Service aggregate metrics unchanged | Revision 1 |

Neither final preview has an approval. No Apply or recovery action was performed. Full stored-table differences, rule comparisons and candidate integrity were checked independently of the UI. Evidence: [Sales](../evals/sparse-refinement-sales.json), [Service](../evals/sparse-refinement-service.json).

Browser checks confirmed the correct adapted page titles, preview revision, Preview & iterate highlight, automatic return from successful refinement to the main page, retained Detail Analysis/Breakdown tabs and actual changed-field counts. The Service region filter contains Montréal Centre; selecting it shows 637 cases, 429 closed and 7.8 days average closure time. These are filtered synthetic metrics, not operational outcomes.

## Implementation

- Sparse `refine_industry_adaptation` patch, grounded in exact affirmative user wording, merged into reviewed rules. No complete rule regeneration in industry refinement mode.
- Omitted fields and mapping entries preserved; ambiguous, unquoted or invalid replacements fail closed or require clarification.
- Execution counters reset per explicit generation; cumulative reservations and project cap remain unchanged.
- Tool-message IDs include proposal generation so later iterations cannot overwrite earlier tool evidence.
- Refinement clarification appears inside the open drawer, with a dedicated Continue action. The workflow stays in Preview & iterate during refinement. On success the drawer closes and updated data is on the page.

## Failures retained, not hidden

The first Sales attempt using the older brief failed initial validation (duplicate targets, followed by generic titles). It created no preview. The revised explicit-title brief in the recording guide succeeded; its opportunity refinement succeeded in one model call.

Service initially returned a patch whose request quote also included Keep/Preserve sentences. The server rejected it. The model then asked which original division should map to Montréal Centre. Answering “Change Central region to Montréal Centre.” succeeded; the refinement used three model calls including the rejected patch and clarification. Instructions now explicitly require only the change sentence and allow either original source or current target labels. This prompt improvement is not a claim that every future call will avoid clarification.

That clarification also exposed a UI defect: the question appeared behind the open drawer. It now appears within the drawer, covered by a dedicated UI test. The successful Service run was completed by closing the old drawer and answering the question; the fixed clarification placement is verified by the UI regression, not misrepresented as the original browser path.

The Sales live checkpoint exposed reused tool-message IDs after counter reset. The fix is covered by an inspection → proposal → refinement history-preservation regression. The Service checkpoint retains the complete tool sequence.

## Validation

- Full backend suite: **135 passed** in disposable databases.
- After the final instruction/evidence-ID changes: **20 targeted backend regressions passed**.
- Frontend: **37 passed**; production build passed after correcting the new test fixture type.
- `git diff --check` passed. Existing framework deprecations and Plotly chunk-size warning remain.
- Six eligible old previews were reversibly archived through the existing protected cleanup function to make room for the rehearsals. No history was permanently deleted in this pass.

## Practical limits

This is tested bounded refinement, not a universal natural-language correctness guarantee. Use exact existing-label → replacement wording for the recording. Unsupported mapping additions and vague semantic changes can require a fresh brief or clarification. Numeric refinements still use the earlier proposal path. Previous-preview comparison UI state is not reconstructed after a reload; saved revision data persists. Full keyboard/screen-reader/mobile accessibility and unattended provider hard stops remain unverified.

Use [the recording guide](PREVIEW_DEMO_RECORDING.md) and stop at Preview & iterate. External production-instance connection/deployment remains future scope.

Test session ended with the Nebius gate closed and $0.9416784 remaining in the original monitored allowance. Viewing retained previews remains available.
