# Replacement art section for the existing Morning Brief writer

Replace only the old image-generation/Base64-upload section. Keep the existing text schedule and existing Google authentication. Do not create another brief writer or schedule.

1. Publish/update today's Brisbane-date `Briefs` row and set it ready **before** waiting for art. Preserve the text even if art fails. Art is eligible in every mode, including solo. Use the existing row for the date; never append a duplicate row to add an image.
2. Check `nerdflu/morning-brief-art/manifests/YYYY-MM-DD.json`. If it already contains a verified, publicly retrievable image for this date, use that image without a new generation request.
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

Contract: exactly these five fields. `concept` must be 8–280 printable ASCII characters, reviewed for public safety; no URLs, contact details, sensitive information, cats or dogs. Styles: `linocut`, `woodcut`, `ink`, `paper-cut`, `geometric`, `etching`. Layout: `school` for the 2:1 presentation, `non-school` for the 5.1:1 presentation. Layout determines crop-safe composition only; do not include personal reasons for the layout in the concept. The route preserves the original and creates a 960×480 grayscale display image.

5. This request-file commit triggers the image route once the approved workflow is enabled. Poll the matching workflow and `manifests/YYYY-MM-DD.json`; do not create a second request, rerun a paid job, or rewrite a failed request. A completed date is idempotent. A charged/uncertain outcome needs review, not regeneration.
6. On a successful matching manifest, fetch its `image_url` publicly and verify a PNG of 960×480 before writing it to column H (`image_url`) of the **same existing date row**. Preserve all other cells. Do not use a guessed URL, an original image URL, an expired API URL or a link to the JSON itself.
7. If art is pending, budget-blocked, invalid, failed or uncertain, leave H blank and keep the ready text row intact. Report the exact status/run URL. A later verified image may be attached to the same row without republishing or duplicating text. Never mark an image failure as success, exceed A$5/month, change credentials, or create a competing brief schedule.

Operational prerequisites: root-approved workflow deployment and budget reconciliation; the current writer must be able to commit the request file and update its existing Sheet row. No additional Google credentials are required by this image route.
