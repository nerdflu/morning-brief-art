"""Validate each input independently; retain sources and report partial failure."""
import base64
import binascii
from datetime import date
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

MAX_BYTES = 16_000_000
MAX_PIXELS = 35_000_000


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def decode_one(source, root):
    name = source.stem
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("invalid_filename")
    date.fromisoformat(name[:10])
    # Bound allocation before reading or decoding; retain the original .b64 untouched.
    if source.stat().st_size > (MAX_BYTES + 2) // 3 * 4 + 2:
        raise ValueError("encoded_source_too_large")
    encoded = source.read_bytes().strip()
    raw = base64.b64decode(encoded, validate=True)
    if len(raw) > MAX_BYTES:
        raise ValueError("source_too_large")
    with Image.open(io.BytesIO(raw)) as image:
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("dimensions_too_large")
        image.load()
        original = ImageOps.exif_transpose(image).convert("RGB")
    canvas = ImageOps.pad(original, (1920, 960), method=Image.Resampling.LANCZOS, color="white")
    gray = ImageOps.autocontrast(ImageOps.grayscale(canvas), cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.3)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=1.5, percent=160, threshold=2))
    gray = gray.resize((960, 480), Image.Resampling.LANCZOS)
    # Render both in memory before changing any existing archive file.
    outputs = []
    folder = root / "images" / name[:4] / name[5:7]
    for suffix, image in (("-original", original), ("", gray)):
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        outputs.append((folder / (name + suffix + ".png"), buffer.getvalue()))
    for path, data in outputs:
        atomic_write(path, data)
    return {"state": "complete", "source_sha256": hashlib.sha256(encoded).hexdigest(),
            "display": str(outputs[1][0].relative_to(root)), "width": 960, "height": 480}


def run(root):
    results = {}
    for source in sorted((root / "incoming").glob("*.b64")):
        try:
            results[source.name] = decode_one(source, root)
        except (ValueError, binascii.Error, OSError, Image.DecompressionBombError) as error:
            # No raw input or exception detail: malformed input might contain private text.
            reason = "invalid_base64" if isinstance(error, binascii.Error) else type(error).__name__
            results[source.name] = {"state": "failed", "reason": reason}
            print("::error::Encoded image failed validation or publication; see decode report")
    report = {"sources": results, "failed": sum(r["state"] == "failed" for r in results.values())}
    atomic_write(root / ".pipeline-status" / "decode.json", (json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps({"processed": len(results), "failed": report["failed"]}))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(run(Path.cwd()))
