"""Bounded public-concept contract, not a claim that regex can prove privacy."""
from datetime import date
import re

STYLES = {
    'linocut': 'Bold linocut.',
    'woodcut': 'Expressive woodcut.',
    'ink': 'Playful ink drawing.',
    'paper-cut': 'Graphic paper-cut shapes.',
    'geometric': 'Inventive geometric poster.',
    'etching': 'High-contrast etching.',
}
MAX_CONCEPT_CHARS = 280
MAX_PROMPT_BYTES = 512
# Obvious unsafe input is rejected; upstream author must still review the concept.
SENSITIVE = re.compile(r'\b(?:child(?:ren)?|kid(?:s)?|custody|medical|diagnosis|medication|patient|bank|account|invoice|salary|password|secret|private|cat(?:s)?|dog(?:s)?)\b', re.I)
CONTACT = re.compile(r'https?://|www\.|@|\b\d{4,}\b|\+\d|[\\<>]')


def validate_public_request(request):
    expected = {'date', 'concept', 'style', 'layout', 'public_safe'}
    if not isinstance(request, dict) or set(request) != expected:
        raise ValueError('request_requires_date_concept_style_layout_public_safe')
    if request['public_safe'] is not True:
        raise ValueError('upstream_public_safety_review_required')
    if not isinstance(request['date'], str):
        raise ValueError('invalid_date')
    day = date.fromisoformat(request['date'])
    if day.isoformat() != request['date']:
        raise ValueError('invalid_date')
    concept = request['concept']
    if not isinstance(concept, str) or not 8 <= len(concept) <= MAX_CONCEPT_CHARS:
        raise ValueError('concept_length_invalid')
    if any(ord(c) < 32 or ord(c) > 126 for c in concept):
        raise ValueError('concept_must_be_printable_ascii')
    if SENSITIVE.search(concept) or CONTACT.search(concept):
        raise ValueError('concept_contains_restricted_content')
    style = request['style']
    layout = request['layout']
    if not isinstance(style, str) or style not in STYLES:
        raise ValueError('unsupported_style')
    if layout not in ('school', 'non-school'):
        raise ValueError('unsupported_layout')
    ratio = '2:1' if layout == 'school' else '5.1:1'
    prompt = (concept.strip() + ' ' + STYLES[style] +
              ' Black ink, white background, bold lines. No text, people, cats or dogs.' +
              ' Keep all key details inside a central horizontal ' + ratio + ' crop-safe strip.')
    if len(prompt.encode('ascii')) > MAX_PROMPT_BYTES:
        raise ValueError('prompt_budget_exceeded')
    return day.isoformat(), prompt
