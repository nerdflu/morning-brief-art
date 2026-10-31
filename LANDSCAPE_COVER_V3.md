# Native landscape contract — released 1 November 2026

This policy removes software-added solo letterboxing. It does not require an exact display aspect ratio: the plugin's CSS cover viewport chooses the visible crop.

The existing service has successfully requested 1872×624 with the current model; that known 3:1 request is retained. No new size capability or paid call was tested. The prompt now requests a whole landscape, no internal blank composition strip, with important forms near the central vertical 60% and peripheral scenery allowed to crop. It retains the approved contrast, readable focal subjects and selective detail direction.

`mode-aware-ink-v3` keeps both school and non-school family source and display processing byte-compatible with v2. Only explicit solo requests use native PNGs, preserving every source pixel in grayscale at the returned size. No canvas, padding, resize, crop, threshold or dithering is added. Acceptable landscape bounds are 600–4096 pixels wide, 200–2048 high, ratio 1.25–4 and at most 8,388,608 pixels. Portrait, blank and invalid inputs stop without retry. Manifests declare actual dimensions, full source bounds and `landscape-cover-v3`; public PNG bytes/hash/dimensions are verified against that declaration. Originals remain archived unchanged before derivation.

Requests still use exactly five fields. The new layout enum solo is backward-compatible alongside unchanged school and non-school values. Solo requires the new policy and is rejected before ledger mutation when disabled. Model, quality, count, monthly cap, reservation, uncertain-call freeze, one-request/date guard, manual revision identity and approved-current-pointer precedence are unchanged. School, family and legacy assets/manifests stay valid. The reviewed `.pipeline/art-policy.json` now enables v3 after the matching saved producer instructions were read back. No workflow trigger or existing production request changed.

## Coordinated activation sequence (completed)

1. Publish the compatible renderer and pure service support while retaining policy v2.
2. Read and narrowly update the existing saved producer: keep school 960×480, family and legacy solo v2 1872×400; use the new solo layout enum only for confirmed solo mode. For solo `landscape-cover-v3`, require verified public PNG bytes/hash and exact manifest-declared dimensions within the bounds above, rather than fixed 1872×400. Continue to prefer the approved current manifest over historical canonical art. Preserve the existing schedule, cap, privacy and text fallback.
3. Only after saved validation readback, enable v3 policy for future daily requests. No existing date needs regeneration. Family Geo requests retain the non-school enum, v2 derivative and existing contain composition; they never enter the native landscape path.
4. Verify the first ordinary job's archive, manifest, public PNG, existing-row update and hosted render. Do not retry a paid outcome blindly.

Rollback: disable v3 for future jobs, restore the prior renderer if needed, retain v3 acceptance for already published URLs and preserve all ledgers, approved pointers and archived originals. Do not delete history or create another schedule.

Local tests exercise exact pixel preservation at native and off-ratio sizes, public archive publication, duplicate and uncertain-call guards, approved-revision precedence and unchanged school output. No real image API was called.
