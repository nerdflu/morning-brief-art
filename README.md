# Morning Brief Art

Public, guest-safe illustrations for the TRMNL wall display.

## Archive

Store daily images at `images/YYYY/MM/YYYY-MM-DD-description.png`.

For each image, use a public raw URL:
`https://raw.githubusercontent.com/nerdflu/morning-brief-art/<immutable-commit>/images/YYYY/MM/filename.png`

Images use expressive hand-drawn black-and-white forms, confident contrast and selective readable detail. See [mode contracts and active revision selection](MODE_CONTRACTS.md). Avoid personal/private details, including custody references. Always preserve the complete original and its verified display derivative.

The Morning Brief Google Sheet `Briefs` tab has an `image_url` column (H). Set that cell only after the image is uploaded and its public URL is verified. Artwork is allowed in every mode, including solo days. Preserve an existing verified image, otherwise leave the cell blank when none is available; text delivery must continue.


## Daily image route

See [pipeline operation and budget safeguards](PIPELINE.md) and the [existing writer handoff](WRITER_ART_SECTION.md). Commit one reviewed public-safe `requests/YYYY-MM-DD.json`; no Base64 transport or second brief schedule is needed. Text remains available without an image.
