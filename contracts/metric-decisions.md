# Metric decisions

- Opportunity money is the sum of quantity × line price; no header amount is invented. Opportunity counts and cycles aggregate at distinct opportunity grain before dimension joins.
- Source total-sales last-N label says closed date but its expression uses created date. This app deliberately uses close date for total-sales periods; the original expression remains in source-metric-contracts.json.
- Sales trend uses created-date cohorts and ignores the Executive close-date filter as captured. Pipeline charts exclude created-date publishers where recorded; effective period exclusions are shown per component.
- Win rate is won/all count; conversion is won/closed money. Empty denominator is null.
- Product breakdown money uses matching lines; distinct opportunity counts can overlap and must not be summed.
- Service is closed when closed_date is non-null. Calendar-day duration is measured in UTC. Created-case charts use created-date cohorts; metric catalog records closed-date bindings for closed and duration metrics.
- Missing account cases remain in totals under Unassigned account. Reason means case type, not an invented field.
- Deal size uses opportunity total rather than misleading source line-grain buckets, explicitly documented here.
- Source styling is intentionally replaced by the approved light workspace. No source action parity is asserted.
