import re
from zipfile import ZipFile
from xml.etree.ElementTree import iterparse

NS_MAIN = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
NS_REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
NS_PKG_REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CELL_RE = re.compile(r'([A-Z]+)')


def _column_index(cell_ref):
    if not cell_ref:
        return 0
    match = CELL_RE.match(cell_ref)
    if not match:
        return 0
    index = 0
    for char in match.group(1):
        index = index * 26 + (ord(char) - ord('A') + 1)
    return index - 1


def _text(element):
    if element is None:
        return None
    return ''.join(element.itertext())


def _read_shared_strings(zf):
    if 'xl/sharedStrings.xml' not in zf.namelist():
        return []

    values = []
    with zf.open('xl/sharedStrings.xml') as source:
        for event, elem in iterparse(source, events=('end',)):
            if elem.tag == NS_MAIN + 'si':
                values.append(''.join(elem.itertext()))
                elem.clear()
    return values


def _first_sheet_path(zf):
    names = set(zf.namelist())
    workbook_path = 'xl/workbook.xml'
    rels_path = 'xl/_rels/workbook.xml.rels'

    if workbook_path not in names or rels_path not in names:
        return 'xl/worksheets/sheet1.xml'

    first_rid = None
    with zf.open(workbook_path) as source:
        for event, elem in iterparse(source, events=('end',)):
            if elem.tag == NS_MAIN + 'sheet':
                first_rid = elem.attrib.get(NS_REL + 'id')
                elem.clear()
                break
            elem.clear()

    if not first_rid:
        return 'xl/worksheets/sheet1.xml'

    with zf.open(rels_path) as source:
        for event, elem in iterparse(source, events=('end',)):
            if elem.tag == NS_PKG_REL + 'Relationship' and elem.attrib.get('Id') == first_rid:
                target = elem.attrib.get('Target', 'worksheets/sheet1.xml')
                if target.startswith('/'):
                    return target.lstrip('/')
                return 'xl/' + target.lstrip('./')
            elem.clear()

    return 'xl/worksheets/sheet1.xml'


def _cell_value(cell, shared_strings):
    cell_type = cell.attrib.get('t')

    if cell_type == 'inlineStr':
        inline = cell.find(NS_MAIN + 'is')
        return _text(inline)

    value_node = cell.find(NS_MAIN + 'v')
    if value_node is None:
        return None

    raw = value_node.text
    if raw is None:
        return None

    if cell_type == 's':
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return None

    if cell_type == 'b':
        return 'TRUE' if raw == '1' else 'FALSE'

    return raw


def iter_xlsx_rows(path):
    with ZipFile(path) as zf:
        shared_strings = _read_shared_strings(zf)
        sheet_path = _first_sheet_path(zf)

        with zf.open(sheet_path) as source:
            for event, row_elem in iterparse(source, events=('end',)):
                if row_elem.tag != NS_MAIN + 'row':
                    continue

                row_values = []
                for cell in row_elem.findall(NS_MAIN + 'c'):
                    col_index = _column_index(cell.attrib.get('r', ''))
                    while len(row_values) <= col_index:
                        row_values.append(None)
                    row_values[col_index] = _cell_value(cell, shared_strings)

                row_elem.clear()
                yield row_values
