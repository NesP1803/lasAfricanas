from odf.opendocument import load
from odf.table import Table, TableRow, TableCell
from odf.text import P


def _cell_text(cell):
    texts = []
    for p in cell.getElementsByType(P):
        texts.append(''.join(t.data for t in p.childNodes if hasattr(t, 'data')))
    return ' '.join(texts).strip()


def parse_ods(file_path):
    doc = load(file_path)
    sheets = []
    for table in doc.spreadsheet.getElementsByType(Table):
        raw_rows = []
        for row in table.getElementsByType(TableRow):
            vals = []
            for cell in row.getElementsByType(TableCell):
                vals.append(_cell_text(cell))
            raw_rows.append(vals)
        if not raw_rows:
            continue
        headers = raw_rows[0]
        data = []
        for row in raw_rows[1:]:
            if not any(str(v).strip() for v in row):
                continue
            data.append(dict(zip(headers, row)))
        sheets.append({'sheet_name': str(table.getAttribute('name')), 'headers': headers, 'rows': data})
    return sheets
