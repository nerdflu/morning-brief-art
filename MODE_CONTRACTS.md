# Mode-aware illustration contracts v2 and v3

Requests retain exactly `date`, `concept`, `style`, `layout`, `public_safe`. Existing styles remain accepted; prefer `ink`. The shared service supplies the illustration direction: expressive large subjects, confident black and white shapes, selective medium-scale detail, original playful storytelling, and clear negative space. It does not force miniature etched scenery or icon-like silhouettes.

| Mode | Source PNG | Public display PNG | Contract |
|---|---|---|---|
| school | 1536 × 768 | 960 × 480 | school-2x1-v2 |
| non-school (family and existing solo requests) | 1872 × 624 | 1872 × 400 | solo-panorama-v2 |
| solo (explicit new request) | request 1872 × 624; bounded landscape accepted | actual native source dimensions, grayscale | landscape-cover-v3 |

School retains the complete source scene with high-quality grayscale resize. The backward-compatible non-school v2 path requires a complete shallow scene spanning at least 85% of the width, at most 388 pixels tall, with a 400-pixel window preserving every non-paper pixel and a six-pixel margin. It never stretches or crops subjects. If the generated scene exceeds that window, a reliability fallback proportionally contains the complete original on the same1872x400 canvas, without stretching or clipping. It records framing_fallback, fit_size and paste_xy. This is not default art direction and never makes another paid call; blank/invalid sources still stop for review. No dates or headlines are generated into artwork. Existing dated assets and manifests remain immutable.

## Selection and publication

Fetch `manifests/current/YYYY-MM-DD.json` first. Its immutable commit-pinned `manifest_url` selects the verified daily image or an explicitly approved revision. Validate date, source, revision identity, format contract, actual public PNG dimensions and SHA-256 before writing the existing Sheet row's image cell. Test artifacts and originals are never eligible. An invalid pointer fails closed: preserve the currently verified image and publish text normally. Never silently fall back from an approved revision to its historical canonical manifest. With no pointer, preserve an existing verified approved revision; otherwise the legacy canonical manifest remains supported.

Legacy manifests without `format_contract` remain 960 × 480. New filenames encode their contract. Explicit solo requests under v3 retain the whole landscape without software-added padding, resize or cropping; see LANDSCAPE_COVER_V3.md for bounds and validation. Both old request enums retain byte-identical behavior. The renderer preserves school and family composition, and uses a bounded CSS cover header only in solo mode. Existing solo v2 displays can resolve their matching immutable archived original, with the verified display as fallback. New v3 URLs require solo mode and the correct date/revision path.

## Reliability and release

`.pipeline/art-policy.json` gates new generation policy. Code/config pushes do not trigger generation; only the existing dated-request workflow does. Publish backward-compatible code before activation, deploy the compatible renderer, update and read back the existing saved producer task, then enable the new policy. Do not run the producer during cutover. Preserve its enabled daily 4 am Australia/Brisbane schedule.

The existing A$5 monthly cap and A$0.50 reservation remain. A submitted call temporarily holds the whole cap until validated usage is durably recorded. Cancellation or uncertain outcome blocks another call pending review; a known successful response with formatting failure retains the original reservation. There are no automatic paid retries, and completed dates cannot generate again. Text fallback is independent of image success.

Rollback: disable `art-policy.json` first; preserve current pointers, approved image cells, all archives and ledger records. Restore the prior task prompt and renderer only as a coordinated operation; legacy URLs remain valid. Never roll back durable ledgers or delete originals to retry.
