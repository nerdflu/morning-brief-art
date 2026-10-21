"""Decode incoming Base64 images; preserve originals and make TRMNL-friendly exports."""
import base64
import io
import re
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance, ImageFilter, UnidentifiedImageError

for source in Path("incoming").glob("*.b64"):
    name = source.stem
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}-[a-z0-9-]+", name):
        raise ValueError(f"Invalid image filename: {name}")
    raw = base64.b64decode(source.read_text().strip(), validate=True)
    if len(raw) > 16_000_000:
        raise ValueError("Source image exceeds 16 MB")
    try:
        original = Image.open(io.BytesIO(raw))
        original.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Invalid source image: {name}") from exc
    if original.width * original.height > 35_000_000:
        raise ValueError("Source image dimensions too large")
    original = ImageOps.exif_transpose(original).convert("RGB")
    folder = Path("images") / name[:4] / name[5:7]
    folder.mkdir(parents=True, exist_ok=True)
    original_path = folder / f"{name}-original.png"
    display_path = folder / f"{name}.png"
    original.save(original_path, optimize=True)
    # Preserve fine strokes by resampling at 2x output resolution first.
    canvas = ImageOps.pad(original, (1920, 960), method=Image.Resampling.LANCZOS, color="white")
    gray = ImageOps.grayscale(canvas)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.3)
    # UnsharpMask strengthens edges before the final downsample.
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1.5, percent=160, threshold=2))
    gray = gray.resize((960, 480), Image.Resampling.LANCZOS)
    # Keep 8-bit grayscale; the TRMNL renderer can dither for its panel.
    gray.save(display_path, optimize=True)
    print(f"{name}: original {original.size}, display {gray.size}")
