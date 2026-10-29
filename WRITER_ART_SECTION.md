# Replacement art section for the existing Morning Brief writer

Replace only the old image-generation/Base64-upload section. Keep the existing text schedule and existing Google authentication. Do not create another brief writer or schedule.

1. Publish/update today's Brisbane-date `Briefs` row and set it ready **before** waiting for art. Preserve the text even if art fails. Art is eligible in every mode, including solo. Use the existing row for the date; never append a duplicate row to add an image.
2. Fetch `manifests/current/YYYY-MM-DD.json` first and follow its immutable manifest URL only after validating its date, source, revision approval, identity, supported contract and SHA-256. An approved revision takes precedence over the archived canonical manifest. Invalid or ambiguous selection fails closed: preserve verified H and report; never generate or silently fall back. With no pointer, preserve an existing verified approved revision, otherwise reuse the verified canonical `manifests/YYYY-MM-DD.json`. Test/staged/rejected/uncertain artifacts and originals are ineligible. See [versioned contracts](MODE_CONTRACTS.md).
3. Otherwise author a fresh, day-specific public-safe visual concept. Vary the concept and visual treatment substantially; inspect recent `requests/` files to avoid repeating the same scene. Do not default to beaches/coffee. No cats or dogs. Never pass the brief, names, child/custody information, private calendar details, medical or financial information, contact details, or private source text to the image route. Use public seasonal/cultural/weather observations or an original non-personal visual idea. Review the concept before declaring it public-safe; automated validation is not a substitute for this review.
4. Commit exactly one small JSON file to `requests/YYYY-MM-DD.json` on the art repository's main branch using the existing GitHub connection. Do not generate an image in ChatGPT, serialize Base64, or upload a placeholder. Do not change an existing request for a date or dispatch a second image job. Check the existing request/ledger before writing.

Example (replace the concept and style creatively, not mechanically):

```json
{
  "date": "2026-10-27",
  "concept": "A surreal orchestra of dancing olive branches beneath festival bunting, with tiny architectural arches forming the stage.",
  "style": "linocut",
  "layout": "non-school",
  "public_safe": true
}
```

Contract: exactly these five fields. `concept` must be 8–280 printable ASCII characters, reviewed for public safety; no URLs, contact details, sensitive information, cats or dogs. Styles remain `linocut`, `woodcut`, `ink`, `paper-cut`, `geometric`, `etching`; prefer `ink`. They are texture hints beneath shared reference-led direction: large expressive focal subjects, confident black/white shapes, selective medium detail, readable context and white space, not clipart or miniature etched clutter. Vary concepts without private disclosures or baked-in text.

`school` retains the left-hand 2:1 box and oversized right checklist: school-2x1-v2 publishes 960×480 from a complete 1536×768 source. `non-school` uses solo-panorama-v2: 1872×400 from a 1872×624 source whose blank margins alone may be removed. Never crop subjects or stretch a 2:1 scene into a panorama. The service owns source composition. Legacy 960×480 remains accepted under legacy-v1. Preserve all original pixels, historical manifests and URLs.

5. This request-file commit triggers the image route once the approved workflow is enabled. Poll only the matching workflow and active selected manifest; do not create a second request, rerun a paid job, or rewrite a failed request. A completed date is idempotent. A charged/uncertain outcome needs review, not regeneration.
6. On a successful matching manifest, fetch its `image_url` publicly and verify actual public PNG bytes, SHA-256, date, immutable display URL and versioned mode dimensions (legacy/school 960×480; solo-v2 1872×400) before writing it to column H (`image_url`) of the **same existing date row**. Re-read date and current H before the write; never replace a newer approved selection. Preserve all other cells and read back the exact URL. Do not use a guessed URL, an original image URL, an expired API URL or a link to the JSON itself.
7. If art is pending, budget-blocked, invalid, failed or uncertain, preserve existing verified H (otherwise leave it blank) and keep the ready text row intact. Report the exact status/run URL. A later verified image may be attached to the same row without republishing or duplicating text. Never mark an image failure as success, exceed A$5/month, change credentials, or create a competing brief schedule.

Operational prerequisites: root-approved workflow deployment and budget reconciliation; the current writer must be able to commit the request file and update its existing Sheet row. No additional Google credentials are required by this image route.

Keep the existing enabled daily 4am Brisbane task and end condition. Never rerun a paid job or change a completed request. Named revisions require separate explicit approval and immutable audit identity. Preserve the A$5 cap, conservative reservation and uncertain-outcome guards.
