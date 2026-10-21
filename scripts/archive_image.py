"""Download a supplied image and create a crisp monochrome TRMNL asset."""
import io
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance, UnidentifiedImageError

date = os.environ["BRIEF_DATE"]
slug = os.environ["SLUG"]
url = os.environ["IMAGE_URL"]
if not re.fullmatch(r"20\\d{2}-(0[1-9]|1[0-2])-(0[1-9]|[12]\\d|3[01])", date):
    raise ValueError("Invalid YYYY-MM-DD date")
if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
    raise ValueError("Invalid slug")
parsed = urllib.parse.urlsplit(url)
if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
    raise ValueError("image_url must be a public HTTPS image URL")
request = urllib.request.Request(url, headers={"User-Agent": "morning-brief-art/1.0"})
with urllib.request.urlopen(request, timeout=30) as response:
    if urllib.parse.urlsplit(response.geturl()).scheme != "https":
        raise ValueError("Image redirect must remain HTTPS")
    raw = response.read(12_000_001)
if len(raw) > 12_000_000:
    raise ValueError("Image too large")
try:
    image = Image.open(io.BytesIO(raw))
    image.load()
except (UnidentifiedImageError, OSError) as error:
    raise ValueError("Not a valid image") from error
if image.width * image.height > 30_000_000:
    raise ValueError("Image dimensions too large")
image = ImageOps.exif_transpose(image).convert("RGB")
# Fit to a 2:1 landscape artwork area. Black/white only; no grey pixels.
image = ImageOps.pad(image, (960, 480), color="white", method=Image.Resampling.LANCZOS)
image = ImageEnhance.Contrast(image).enhance(1.6)
image = image.convert("L").point(lambda x: 255 if x >= 155 else 0, mode="1")
folder = Path("images") / date[:4] / date[5:7]
folder.mkdir(parents=True, exist_ok=True)
output = folder / f"{date}-{slug}.png"
image.save(output, optimize=True)
print(f"Saved {output}")
