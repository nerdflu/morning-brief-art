"""Versioned mode contracts. No network, spending or activation side effects."""
import hashlib
import io
from PIL import Image, ImageOps
from public_prompt import validate_public_request

POLICY = 'mode-aware-ink-v2'
CONTRACTS = {
    'school': {'id': 'school-2x1-v2', 'source': (1536,768), 'display': (960,480), 'suffix': 'school-v2'},
    'non-school': {'id': 'solo-panorama-v2', 'source': (1872,624), 'display': (1872,400), 'suffix': 'solo-panorama-v2'},
}
ART_DIRECTION = (
    ' Original hand-drawn black-and-white editorial illustration. One dominant expressive'
    ' subject or group, at most two supporting groups. Confident varied black contours,'
    ' purposeful black masses balanced with clean white paper; selective medium-scale'
    ' detail and hatching. Simple lighter distant scenery. Main gestures and forms must'
    ' read at phone size without zoom. Witty, imaginative and sophisticated, never'
    ' preschool-cute. Avoid flat vector/cutout clipart, miniature etched worlds, repeated'
    ' tiny windows, all-over stippling and pale grey texture wash. Original fictional'
    ' characters or objects only, no real-person likeness, private scenes, text, dates,'
    ' headlines, cats or dogs. Calm light upper-left for a separate date overlay.')


def contract(layout):
    return CONTRACTS[layout]


def parameters(request):
    validate_public_request(request)  # unchanged five-field/private-input guard
    c = contract(request['layout'])
    composition = (
        ' Compose directly on the native 1536x768 (2:1) canvas for the school left box.'
        ' Fill 85-95% of its width with one complete scene; no baked-in blank side'
        ' gutters, internal letterbox, padded near-square picture or central strip.'
        ' Reserve the upper-left 40% of width and 20% of height (x=0..614,y=0..154)'
        ' as light quiet background for the opaque date badge; no faces, heads or'
        ' important story details there. Use the remaining canvas for large readable'
        ' subjects and supporting scenery; retain modest safe outer margins.'
        if request['layout'] == 'school' else
        ' Compose a genuinely shallow full-width panorama as a few large connected'
        ' forms, not many tiny objects. Use 85-95% width. The COMPLETE scene must fit'
        ' inside y=104..503 on the 1872x624 canvas; outside that band only blank white'
        ' paper. Keep all subjects away from the band edges. Readable at 468x100.')
    prompt = request['concept'].strip()+ART_DIRECTION+composition
    if len(prompt.encode('ascii')) > 1800:
        raise ValueError('bounded_service_prompt_exceeded')
    return {'model':'gpt-image-2.5-flare','n':1,'quality':'low',
            'size':f"{c['source'][0]}x{c['source'][1]}",'output_format':'png','prompt':prompt}


def derive(raw, layout):
    c = contract(layout)
    with Image.open(io.BytesIO(raw)) as source:
        if source.format != 'PNG' or source.size != c['source']:
            raise ValueError('source_contract_mismatch')
        gray = ImageOps.grayscale(ImageOps.exif_transpose(source))
    meta = {'format_contract':c['id'],'layout':layout,'width':c['display'][0],
            'height':c['display'][1],'original_width':c['source'][0],
            'original_height':c['source'][1],'framing':c['id']}
    if layout == 'school':
        # Native2:1 ->2:1: preserve the complete source, no threshold/contrast/crop.
        output = gray.resize(c['display'], Image.Resampling.LANCZOS)
        meta['source_crop_bounds'] = [0,0,*c['source']]
    else:
        # Prefer the complete shallow window; contain the full source if the
        # model ignores the requested band. Never crop subjects or call AI again.
        marks=gray.point(lambda p:255 if p<253 else 0).getbbox()
        if not marks: raise ValueError('blank_panorama_needs_review')
        top=max(0,min(gray.height-400,(marks[1]+marks[3]-400)//2))
        fits=(marks[2]-marks[0]>=round(gray.width*.85) and marks[3]-marks[1]<=388
              and marks[1]-top>=6 and top+400-marks[3]>=6)
        if fits:
            box=(0,top,gray.width,top+400)
            output=gray.crop(box);meta['source_crop_bounds']=list(box)
        else:
            fitted=ImageOps.contain(gray,c['display'],Image.Resampling.LANCZOS)
            output=Image.new('L',c['display'],255)
            xy=((output.width-fitted.width)//2,(output.height-fitted.height)//2)
            output.paste(fitted,xy)
            meta.update(framing='solo-panorama-v2-whole-source-fallback',
                        source_crop_bounds=[0,0,*gray.size],framing_fallback=True,
                        fit_size=list(fitted.size),paste_xy=list(xy))
    buf=io.BytesIO();output.save(buf,format='PNG',optimize=True)
    return buf.getvalue(), meta


def expected(manifest):
    value=manifest.get('format_contract','legacy-v1')
    if value == 'legacy-v1':
        return (960,480)
    for c in CONTRACTS.values():
        if value==c['id']:
            return c['display']
    raise ValueError('unsupported_display_contract')
