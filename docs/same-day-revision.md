# Manual same-day artwork replacement

Local implementation proposal. Publishing this code does not call the image API:
only an explicit **Generate approved art revision** dispatch on main can do so.
Never push a changed daily request to obtain a replacement; keep daily generation
and its request files unchanged.

The manual envelope has exactly two objects:

- `request`: existing public-safe date/concept/style/layout/public_safe contract.
- `revision`: `id` (immutable lowercase slug, maximum 40 characters),
  `supersedes_manifest_url` (exact completed original ledger manifest URL),
  `max_reservation_cents` (explicit accounting allowance, not a provider hard cap),
  `approval_reference` (public-safe approval reference; never private conversation).

With the current reviewed policy the required reservation is AUD 0.50, while
successful reported usage settles using the existing buffered cost estimate.
This does not change the AUD 5 monthly ceiling, pricing, model, n=1, quality=low,
1024-square size, or retry policy. No uncertain reservation is released.
A lower allowance stops before any paid call. The provider offers no exact
per-call dollar cap; approval must cover that limitation.

Each revision uses ledger key `DATE:revision:ID`, a fingerprint of the complete
request and revision approval, and filenames `DATE-revision-ID-flare-original.png`,
`DATE-revision-ID-flare.png`, and `manifests/DATE-revision-ID.json`. The original
record, image files, and date manifest remain unchanged. Duplicate complete
requests return the same result. Changed fingerprints stop. Reserved, submitted,
or uncertain revisions cannot run again; uncertain results freeze the monthly
allowance using the existing rule. Workflow reruns are rejected. All art writers
use the existing global concurrency group.

Revision non-school display framing uses `band-fill-v1`: center-crop the marks
into 936x172, centered on the existing 960x480 canvas. It fills the band without
stretching but may cut off edge subjects. Review the resulting crop before use.
Default daily `contain-v1` and school framing remain unchanged.

## Reviewed delivery sequence

1. Review/merge the art code and manual workflow, with no request-file changes.
2. Verify fresh main, original completed ledger manifest, intended revision ID,
   public-safe prompt, one-call approval and remaining monthly allowance.
3. Have exactly one operator dispatch the revision workflow once. Never rerun a
   failed/unknown outcome. Inspect durable ledger and workflow evidence instead.
4. Obtain the completed immutable manifest. Review original/display pixels and
   the actual TRMNL band render. Paid retries are not part of this procedure.
5. `revision_switch.verify_manifest` independently fetches the immutable manifest
   and both PNGs, checking equality, SHA-256 hashes, dimensions and archive host.
6. Switch only the selected existing Briefs row through `switch_same_row`. Its
   adapter must supply atomic compare-and-swap plus readback; no Sheet credentials
   or transport are bundled here. It preserves row fields and payload content,
   changes the image column and any matching payload image/hero references, and
   refuses a different hero or changed row. A refreshed headline/body must be
   separately reviewed and included through the chosen Sheet delivery route.
7. Poll/refresh TRMNL and inspect the hosted preview/device. The art publisher
   alone does not switch the Sheet or refresh the device.

**Remaining integration requirement:** a real Sheet adapter satisfying the CAS
contract, or an explicitly reviewed serialized Sheet update procedure, must be
selected before live use. Do not treat the tested fake adapter as a deployed
Sheet connection. No generation should be dispatched until the parent reviews
this route and coordinates the sole caller.

## Local validation

Use the existing Pillow 11.3.0 environment:
`/Users/mikehancock/Documents/Codex/2026-10-22/task-17/.venv-flare-test/bin/python -m unittest discover -s tests -v`

Tests use synthetic PNGs, fake API/public responses, temporary ledgers and local
bare Git repositories. No real API or Sheet writes occur.
