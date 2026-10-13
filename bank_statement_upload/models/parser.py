import io
import re
from datetime import date

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    from PyPDF2 import PdfReader

MONTHS = {m: i for i, m in enumerate(
    ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}
DATE_RE = re.compile(r'^(\d{2})-([A-Za-z]{3})-(\d{4})$')
AMOUNT_RE = re.compile(r'^\d[\d,]*\.\d{2}$')
SKIP_RE = re.compile(r'Bank of Khartoum|End of Statement|^Page\b', re.I)


def _fragments(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages:
        frags = []

        def visitor(text, cm, tm, font_dict, font_size, _f=frags):
            t = ' '.join((text or '').split())
            if not t:
                return
            cm = cm or [1, 0, 0, 1, 0, 0]
            tm = tm or [1, 0, 0, 1, 0, 0]
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            _f.append((x, y, t))

        page.extract_text(visitor_text=visitor)
        pages.append(frags)
    return pages


def _split_description(desc):
    """Return (operation type, transaction ref, account/customer number)."""
    head = desc.split(' - ')[0] if ' - ' in desc else desc.split('#')[0]
    op_type = head.strip()
    m = re.search(r'ref\.\s*(.*?)(?:\s+Transfer\s+ref\.|$)', desc)
    ref = m.group(1).strip() if m else ''
    m = re.search(r'#\s*(\d+)', desc)
    return op_type, ref, (m.group(1) if m else '')


def parse_statement(pdf_bytes):
    """Parse a Bank of Khartoum PDF statement.

    Returns a list of dicts. Amounts are as written by the bank
    (bank_debit / bank_credit); the caller reverses them.
    """
    pages = _fragments(pdf_bytes)
    cols = {}
    for frags in pages:
        for x, _y, t in frags:
            if t in ('Debit', 'Credit', 'Balance') and t not in cols:
                cols[t] = x
    if len(cols) < 3:
        raise ValueError('Could not find the Debit / Credit / Balance headers in the PDF.')
    xd, xc, xb = cols['Debit'], cols['Credit'], cols['Balance']
    left = xd - (xc - xd) / 2.0
    b1 = (xd + xc) / 2.0
    b2 = (xc + xb) / 2.0

    result = []
    for frags in pages:
        rows = []
        for x, y, t in frags:
            m = DATE_RE.match(t)
            if m and x < left and m.group(2).lower() in MONTHS:
                rows.append([y, date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))), [], {}])
        rows.sort(key=lambda r: -r[0])
        for x, y, t in frags:
            if DATE_RE.match(t) and x < left:
                continue
            if SKIP_RE.search(t):
                continue
            row = None
            for r in rows:
                if r[0] >= y - 3:
                    row = r
                else:
                    break
            if row is None:
                continue
            if AMOUNT_RE.match(t) and x >= left:
                col = 'debit' if x < b1 else ('credit' if x < b2 else 'balance')
                row[3][col] = float(t.replace(',', ''))
            elif x < left:
                row[2].append((y, x, t))
        for _y, dt, desc_frags, amt in rows:
            desc = ' '.join(t for _y2, _x2, t in sorted(desc_frags, key=lambda f: (-round(f[0]), f[1])))
            if not desc or ('debit' in amt) == ('credit' in amt):
                continue
            op_type, ref, acct = _split_description(desc)
            result.append({
                'date': dt,
                'description': desc,
                'op_type': op_type,
                'ref': ref,
                'account_no': acct,
                'bank_debit': amt.get('debit', 0.0),
                'bank_credit': amt.get('credit', 0.0),
                'balance': amt.get('balance', 0.0),
            })
    return result
