import csv


def parse_csv(file_path):
    with open(file_path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    if not rows:
        return []
    headers = [str(h).strip() for h in rows[0]]
    data = []
    for row in rows[1:]:
        if not any(str(x).strip() for x in row):
            continue
        data.append(dict(zip(headers, row)))
    return [{'sheet_name': 'CSV', 'headers': headers, 'rows': data}]
