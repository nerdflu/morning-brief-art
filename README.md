# Morning Brief Art

Public, guest-safe illustrations for the TRMNL wall display.

## Archive

Store daily images at `images/YYYY/MM/YYYY-MM-DD-description.png`.

For each image, use a public raw URL:
`https://raw.githubusercontent.com/nerdflu/morning-brief-art/main/images/YYYY/MM/filename.png`

Images should be landscape, high contrast, black-and-white, thick-lined, and legible on small e-ink displays. Avoid personal/private details, including custody references. Keep original artwork separately if useful; optimize a display copy for e-ink.

The Morning Brief Google Sheet `Briefs` tab has an `image_url` column (H). Set that cell only after the image is uploaded and its public URL is verified. Artwork is allowed in every mode, including solo days. Leave the cell blank when no verified image is available; text delivery must continue.


## Daily image route

See [pipeline operation and budget safeguards](PIPELINE.md) and the [existing writer handoff](WRITER_ART_SECTION.md). Commit one reviewed public-safe `requests/YYYY-MM-DD.json`; no Base64 transport or second brief schedule is needed. Text remains available without an image.
