"""Deterministic display framing; never invokes the image API."""
import io
from PIL import Image, ImageOps, ImageEnhance


def derive_display(raw, layout, framing='contain-v1'):
    if framing not in ('contain-v1', 'band-fill-v1'):
        raise ValueError('unsupported_framing')
    with Image.open(io.BytesIO(raw)) as source:
        original = ImageOps.exif_transpose(source).convert('RGB')
    if layout == 'school':
        display = ImageOps.pad(original, (960, 480), color='white', method=Image.Resampling.LANCZOS)
        display = ImageEnhance.Contrast(ImageOps.grayscale(display)).enhance(1.3)
    elif layout == 'non-school':
        gray = ImageEnhance.Contrast(ImageOps.grayscale(original)).enhance(1.3)
        # Fit actual marks, not the square's empty background, into the shallow
        # 5.1:1 renderer band. 172px leaves >=8px vertical margin inside 188px.
        bounds = gray.point(lambda value: 255 if value < 250 else 0).getbbox()
        display = Image.new('L', (960, 480), 255)
        if bounds:
            left, top, right, bottom = bounds
            bounds = (max(0,left-4),max(0,top-4),min(gray.width,right+4),min(gray.height,bottom+4))
            # Revision-only framing fills the band without stretching. This is
            # a deliberate central crop; edge subjects require visual review.
            fit = ImageOps.fit if framing == 'band-fill-v1' else ImageOps.contain
            marks = fit(gray.crop(bounds), (936, 172), method=Image.Resampling.LANCZOS)
            display.paste(marks, ((960-marks.width)//2, (480-marks.height)//2))
    else:
        raise ValueError('unsupported_layout')
    buffer = io.BytesIO()
    display.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()
