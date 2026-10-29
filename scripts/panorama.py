"""Opt-in panorama contract. No network calls or production default changes.

Flare supports at most 3:1. Ask for a complete scene in a 380px band on a
1872x624 canvas, then discard ONLY verified empty paper. Never crop subjects.
"""
import hashlib
import io
from PIL import Image, ImageOps
from public_prompt import validate_public_request

CONTRACT = 'panorama-v1'
SOURCE_SIZE = (1872, 624)
DISPLAY_SIZE = (1872, 380)
BAND = (0, 122, 1872, 502)


def parameters(request):
    validate_public_request(request)  # Preserve five-field public safety contract.
    prompt = (request['concept'].strip() +
        ' Detailed editorial pen-and-ink panorama on white paper, restrained grays.'
        ' Imaginative, playful surreal storytelling; layered scenery, unexpected perspective,'
        ' varied fine lines, hatching and stippling. Sophisticated, never babyish.'
        ' Not a literal agenda, icon, logo, vector, paper-cut, basic silhouette or photograph.'
        ' Compose the COMPLETE scene across 85-95% of the canvas width inside the'
        ' horizontal band x=0..1871, y=122..501 (1872x380). Leave y=0..121 and'
        ' y=502..623 completely blank white paper. No subject may extend outside that band.'
        ' Keep upper-left of the scene light and calm for a separate date overlay.'
        ' No lettering, dates, headlines, people, cats or dogs. Preserve delicate linework.')
    prompt += (' Warm, witty, adventurous storybook energy without preschool cuteness.'
               if request['layout'] == 'school' else
               ' Sophisticated editorial surrealism, architecture, design and elegant visual wit.')
    return {'model': 'gpt-image-2.5-flare', 'n': 1, 'quality': 'low',
            'size': '1872x624', 'output_format': 'png', 'prompt': prompt}


def derive_panorama(raw):
    with Image.open(io.BytesIO(raw)) as source:
        if source.format != 'PNG' or source.size != SOURCE_SIZE:
            raise ValueError('panorama_source_contract_mismatch')
        gray = ImageOps.grayscale(ImageOps.exif_transpose(source))
    # Reject rather than silently cut away ink. Tiny antialias variations in
    # nominally white paper are tolerated; visible pale-gray subjects are not.
    outside = (gray.crop((0, 0, 1872, 122)), gray.crop((0, 502, 1872, 624)))
    if any(part.getextrema()[0] < 248 for part in outside):
        raise ValueError('scene_outside_reserved_band_review_required')
    scene = gray.crop(BAND)
    marks = scene.point(lambda p: 255 if p < 248 else 0).getbbox()
    if not marks or marks[2] - marks[0] < round(DISPLAY_SIZE[0] * .85):
        raise ValueError('scene_too_narrow_review_required')
    output = io.BytesIO()
    scene.save(output, format='PNG', optimize=True)
    display = output.getvalue()
    return display, {'format_contract': CONTRACT, 'width': 1872, 'height': 380,
                     'original_width': 1872, 'original_height': 624,
                     'source_band': list(BAND), 'sha256': hashlib.sha256(display).hexdigest(),
                     'original_sha256': hashlib.sha256(raw).hexdigest()}
