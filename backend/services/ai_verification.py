"""
AI / Local File Verification Service
=====================================
After a file is uploaded and parsed, this module checks whether the
auto-detected data type (Nominal, Binary, Continuous, etc.) is actually
correct for the file's content.

Two verification methods:
  1. "ai"    — sends a compact column summary to Gemini and asks it to
               confirm or correct the detected type.
  2. "local" — a deterministic rule-based cross-check (no API call),
               used automatically if Gemini is unavailable or fails.

Both paths return the same shape so the admin panel can display them
identically:
    {
        'verified': True/False,
        'method': 'ai' | 'local',
        'notes': 'short human-readable explanation',
    }
"""
import os
import json


def _local_verify(detected_type: str, columns_meta: list) -> dict:
    """
    Deterministic, no-API-call sanity check.
    Re-derives the type from columns_meta using the same rules as
    universal_analysis.py and compares it to what was stored.
    """
    if not columns_meta:
        return {'verified': False, 'method': 'local', 'notes': 'No column metadata available to verify.'}

    numeric = [c for c in columns_meta if c.get('python_type') in ('integer', 'float')]
    text    = [c for c in columns_meta if c.get('python_type') == 'string']
    dates   = [c for c in columns_meta if c.get('python_type') in ('datetime', 'date_string')]

    def is_id(c):
        n = c.get('name', '').lower()
        return 'id' in n or 'respondent' in n

    non_id_num  = [c for c in numeric if not is_id(c)]
    non_id_text = [c for c in text if not is_id(c)]

    names_set = set(c.get('name', '').lower() for c in columns_meta)
    joined    = ' '.join(names_set)

    has_entity = any(n in names_set for n in ['state', 'country', 'region', 'district', 'province'])
    has_year   = 'year' in names_set
    has_time   = any(c.get('name', '').lower() in
                     ('month', 'date', 'week', 'quarter', 'period', 'time') for c in columns_meta)

    BINARY_VALS = {'yes', 'no', 'true', 'false', '1', '0', 'y', 'n',
                   'pass', 'fail', 'active', 'inactive'}
    binary_hit, text_with_top = 0, 0
    for c in non_id_text:
        top = c.get('top_values', [])
        if not top:
            continue
        text_with_top += 1
        vals = {str(v.get('value', '')).strip().lower() for v in top}
        if vals and vals.issubset(BINARY_VALS):
            binary_hit += 1

    ordinal_kw = ['level', 'rating', 'rank', 'grade', 'satisfaction', 'performance',
                  'frequency', 'stage', 'priority', 'tier']
    has_ordinal = any(kw in joined for kw in ordinal_kw)

    if has_entity and has_year and len(non_id_num) >= 3:
        rederived = 'Panel'
    elif (len(dates) > 0 or has_time) and len(non_id_num) >= 2 and len(non_id_text) <= 1:
        rederived = 'TimeSeries'
    elif text_with_top >= 2 and binary_hit / text_with_top >= 0.5:
        rederived = 'Binary'
    elif len(non_id_text) >= 2 and len(non_id_num) <= 1 and not dates:
        rederived = 'Ordinal' if has_ordinal else 'Nominal'
    elif len(non_id_text) >= 1 and len(non_id_num) <= 2 and not dates:
        rederived = 'Ordinal' if has_ordinal else ('Nominal' if len(non_id_num) == 0 else 'Mixed')
    elif len(non_id_text) == 0 and len(non_id_num) > 0:
        rederived = 'Discrete' if all(c.get('python_type') == 'integer' for c in non_id_num) else 'Continuous'
    else:
        rederived = 'Mixed'

    match = (rederived == detected_type)
    notes = (
        f"Local cross-check confirms '{detected_type}' "
        f"({len(non_id_num)} numeric, {len(non_id_text)} categorical columns)."
        if match else
        f"Local cross-check suggests '{rederived}' but file was stored as '{detected_type}'. "
        f"Manual review recommended."
    )
    return {'verified': match, 'method': 'local', 'notes': notes}


def _ai_verify(detected_type: str, columns_meta: list, file_name: str) -> dict:
    """
    Ask Gemini to confirm the detected data type makes sense for this column profile.
    Falls back to local verification if Gemini is unavailable or errors out.
    """
    api_key = os.getenv('GEMINI_API_KEY', '').strip()
    if not api_key:
        return _local_verify(detected_type, columns_meta)

    try:
        from google import genai

        col_summary = []
        for c in columns_meta[:15]:
            col_summary.append({
                'name': c.get('name'),
                'type': c.get('python_type'),
                'unique_values': c.get('unique_count', c.get('unique', None)),
            })

        prompt = f"""You are verifying an automated data-type classifier for a statistics platform.

File: {file_name}
System-detected data type: {detected_type}
Columns ({len(columns_meta)} total, showing up to 15):
{json.dumps(col_summary, indent=2)}

The possible data types are: Nominal, Ordinal, Binary, Continuous, Discrete, TimeSeries, Panel, Mixed.

Based on the column names and types, is "{detected_type}" the CORRECT classification for this dataset?
Reply with EXACTLY this format, nothing else:
VERDICT: YES or NO
REASON: <one short sentence>
"""

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        text = (response.text or '').strip()

        verdict_line = next((l for l in text.split('\n') if l.upper().startswith('VERDICT')), '')
        reason_line  = next((l for l in text.split('\n') if l.upper().startswith('REASON')), '')

        verified = 'YES' in verdict_line.upper()
        reason = reason_line.split(':', 1)[-1].strip() if ':' in reason_line else text[:200]

        return {
            'verified': verified,
            'method': 'ai',
            'notes': reason or f"Gemini confirmed type as {'correct' if verified else 'questionable'}.",
        }

    except Exception as e:
        # Any AI failure → fall back to local deterministic check
        fallback = _local_verify(detected_type, columns_meta)
        fallback['notes'] = f"AI verification unavailable ({str(e)[:80]}); used local check instead. " + fallback['notes']
        return fallback


def verify_file_data_type(detected_type: str, columns_meta: list, file_name: str, use_ai: bool = True) -> dict:
    """
    Main entry point. Tries AI verification first (if enabled and key present),
    otherwise falls back to local rule-based verification.
    """
    if use_ai and os.getenv('GEMINI_API_KEY', '').strip():
        return _ai_verify(detected_type, columns_meta, file_name)
    return _local_verify(detected_type, columns_meta)
