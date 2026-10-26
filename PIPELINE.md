# Morning Brief external image route

Input example:
```json
{"date":"2026-10-27","concept":"A brass marching band of animated olive branches parades beneath geometric bunting","style":"linocut","layout":"non-school","public_safe":true}
```
The writer creates a fresh, day-specific **public-safe concept**, not a private brief passthrough. Concepts are bounded printable ASCII (8–280 characters); six style enums support varied original art. `public_safe:true` attests upstream review, while obvious sensitive/contact content is rejected. Regex is defense-in-depth, not a privacy guarantee. No children, medical/financial/private content, cats or dogs; no default coast/coffee template. The generated prompt stays within 512 ASCII bytes. School layouts request a central 2:1 crop-safe strip; non-school layouts request 5.1:1. Original bytes and the 960×480 derivative remain preserved. Solo receives art equally; no exclusion mode.


`generate_daily.generate` reserves durably, submits exactly one existing Flare low/1024-square call, keeps original PNG bytes unchanged, derives grayscale 960×480 PNG, and delegates archive/public verification to a publisher adapter. Completed dates return their recorded manifest without another call; changed concepts on the same date conflict. Any uncertain/API/validation/publication failure blocks date retries and freezes the remaining month's ledger. Billing month is actual UTC execution month, not user-supplied artwork date. The route uses the existing saved Actions secret; no new credentials, scheduler or Sheets writer is created.

## GitHub Actions integration

`git_daily.py` uses existing repository credentials and OpenAI Actions secret. `.github/workflows/generate-daily.yml` is request-triggered, with manual dispatch also available; there is no cron. All mutating art workflows must use the same Actions concurrency group `morning-brief-art-writer` with cancellation disabled. The adapter fetches and fast-forwards main, requires a fresh checkout, commits its imported pilot/reservation/submission ledger before API access, normally pushes (no force), and confirms remote HEAD before returning. Git conflicts stop rather than retry or replay paid calls. Tests use a lightweight local JSON fake; production uses only the Git-backed adapter.

`GitPublisher` archives original and derived bytes, commits and pushes them, then GET-verifies exact bytes/dimensions at immutable commit URLs. It commits a per-date manifest and publicly GET-verifies that JSON; the result includes manifest_url plus image_url. API image bytes remain on the runner if push fails, and the workflow uploads failure recovery evidence for seven days. Any uncertain outcome blocks regeneration. Manual recovery must inspect durable state and retained bytes, not rerun a paid request. No Sheet writes occur; sole existing writer must consume the verified image_url.

Before the first paid production dispatch, run fixture CI and explicitly reconcile the pilot under the approved policy below. Every mutating art workflow shares the lock. Reconciliation application must also run under that shared lock from a fresh main checkout; the script refuses otherwise. No new server, database service, Google credential or renderer change is needed.

## Sole-writer request handoff

The existing ChatGPT writer first completes the text row, then commits exactly one small public-safe `requests/YYYY-MM-DD.json`. The push trigger runs only on main request changes (plus explicit manual dispatch for an approved test); there is no new cron or competing brief writer. The resolver validates event before/after commit SHAs, checks ancestry, takes only added/modified request paths from that event diff, requires exactly one correctly dated filename, and reads JSON from that exact event commit via argv-safe `git show`. Historical failed requests are never swept/reprocessed. JSON date must match filename. Multiple changed requests fail closed rather than selecting one arbitrarily.

Writer polls `manifests/YYYY-MM-DD.json`, verifies its date/public image, and updates only H on the same existing row. Missing/pending/failed art never blocks text or causes another text writer. The existing writer must use this handoff; no second writer is created.

## Budget reconciliation proposal

October pilot currently reserves all A$5; no generation can proceed by default. `scripts/reconcile_budget.py` previews an explicit reconciliation. Applying requires an approval reference and `--apply`, and must only happen after user/root approves it. It retains original A$5 reservation, pilot run ID, estimate, and approval provenance. It does NOT claim invoice settlement.

Proposed pilot hold: A$0.10 (US$0.006025 × conservative 2 AUD/USD ×1.2 tax/fee buffer ≈A$0.01446, rounded upward). Proposed new-call hold: A$0.50 each before submission. After validated successful generation and verified publication, settle conservatively to ceil(estimated USD cost ×2 FX ×1.2 fees/tax ×100) +1 cent, minimum 3 cents. Retain raw usage, USD estimate, original reservation, formula and invoice_verified=false in the ledger. Current validated 512 input/4096 output maximum gives US$0.12544 ×2×1.2 ≈A$0.301056. These are reviewed estimates/envelopes, not a provider-enforced billing cap. Unexpected usage/model/outcome freezes new spending. At the observed usage, each successful image accounts for A$0.03; 31 such images plus A$0.10 pilot would be A$1.03. This is a projection, not a spending promise; every request still needs A$0.50 headroom. Unknown or invalid usage retains the hold and freezes further spending. Never silently raise A$5.

The production entrypoint permits only the current Australia/Brisbane date. Date idempotency prevents a second paid generation. The historical pilot evidence is never edited; reconciliation creates a separate durable accounting entry. See WRITER_ART_SECTION.md for the existing-writer instructions.
