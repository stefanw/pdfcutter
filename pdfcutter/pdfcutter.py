import functools
import logging
import operator
import re
import subprocess

from lxml import etree

from .utils import (
    fuzzy_compare, overlap_horizontal, overlap_vertical,
    repr_ascii, similar, get_compare,
    remove_hyphenation, remove_multispace
)

logger = logging.getLogger(__name__)

REGEXP_NS = "http://exslt.org/regular-expressions"

COMPARISONS = {
    'gt': operator.gt,
    'gte': operator.ge,
    'lt': operator.lt,
    'lte': operator.le,
    'eq': operator.eq,
    'similar': similar,
}


def get_page_number_for_item(item):
    return int(item.getparent().attrib['number'])


class PDFCutter(object):
    tags = ['text', 'image']

    def __init__(self, filename=None, xml=None):
        self.filename = filename
        if filename is not None:
            xml_bytes = PDFCutter.convert_pdf(filename)
            self.xml = xml_bytes
        elif xml is not None:
            if isinstance(xml, str):
                xml = xml.encode('utf-8')
            self.xml = xml
        else:
            raise ValueError('No PDF filename or xml given')
        self.root = etree.fromstring(self.xml)
        self.pages = {}
        self.fonts = None
        self.offsets = list(self.get_offsets())

    def __str__(self):
        if self.filename:
            return '<PDFCutter filename="{}">'.format(self.filename)
        return '<PDFCutter xml=({} chars)>'.format(len(self.xml))
    __repr__ = __str__

    @classmethod
    def convert_pdf(cls, filename, binary='pdftohtml',
                    ignore_images=True, hidden_text=True):
        args = [
            binary,
            '-xml',
            '-stdout',
        ]
        if ignore_images:
            args.append('-i')
        if hidden_text:
            args.append('-hidden')

        args.append(filename)
        xml_bytes = subprocess.check_output(args)
        return xml_bytes

    def get_offsets(self):
        offset = 0
        for p in self.root.xpath('//page'):
            yield offset
            offset += float(p.attrib['height'])

    def all_elements_xpath(self):
        return '//page/*[{}]'.format(
            ' or '.join('self::{}'.format(t) for t in self.tags)
        )

    def all(self):
        all_elements = self.root.xpath(self.all_elements_xpath())
        return Selection(all_elements, cutter=self)

    def filter(self, **kwargs):
        return self.all().filter(**kwargs)

    def get_page_for_item(self, item):
        page_number = get_page_number_for_item(item)
        if page_number not in self.pages:
            self.pages[page_number] = Page.from_item(item)
        return self.pages[page_number]

    def get_offset_for_page(self, page):
        return self.offsets[page.number - 1]

    @property
    def num_pages(self):
        return len(self.root.xpath('//page'))

    def collect_fontspecs(self):
        fonts = {}
        for fontspec in self.root.xpath('//fontspec'):
            fonts[fontspec.attrib['id']] = fontspec.attrib
        return fonts

    def get_fontspec(self, fontid):
        if self.fonts is None:
            self.fonts = self.collect_fontspecs()
        return self.fonts.get(fontid)

    def get_debugger(self, **kwargs):
        if self.filename is None:
            raise Exception('Requires instantiation with PDF filename.')
        from .debug import VisualDebugger

        return VisualDebugger(self.filename, **kwargs)


class Page(object):
    def __init__(self, page_element):
        assert page_element.tag == 'page'
        self.page = page_element

    @classmethod
    def from_item(cls, item):
        return Page(item.getparent())

    @property
    def number(self):
        return int(self.page.attrib['number'])

    @property
    def attrib(self):
        return self.page.attrib

    @property
    def width(self):
        return float(self.page.attrib['width'])

    @property
    def height(self):
        return float(self.page.attrib['height'])

    def get_font(self, fontid):
        return self.pdfcutter.get_fontspec(fontid)

    def match_font(self, item, font):
        fontspec = self.get_font(item.attrib['font'])
        for k, v in font.items():
            if not v(fontspec[k]):
                return False
        return True


class Selection(object):
    def __init__(self, selected, cutter):
        self.cutter = cutter

        if not isinstance(selected, (list, tuple)):
            selected = [selected]

        selected.sort(key=fuzzy_compare)

        self.selected = selected
        self.pages = set(self.cutter.get_page_for_item(s) for s in selected)

    def __repr__(self):
        return '<{}({}, {}, {}, {}) \'{}\'>'.format(
            self.__class__.__name__,
            self.left,
            self.right,
            self.width,
            self.height,
            repr_ascii(self.text()) or ''
        )

    def __iter__(self):
        return iter(type(self)(s, self.cutter) for s in self.selected)

    def __nonzero__(self):
        return bool(self.selected)

    def __len__(self):
        return len(self.selected)

    def __getitem__(self, item):
        try:
            return type(self)(self.selected[item], self.cutter)
        except IndexError:
            return type(self)([], self.cutter)

    def __or__(self, other):
        return type(self)(
            list(set(self.selected) | set(other.selected)),
            cutter=self.cutter
        )

    def __and__(self, other):
        return type(self)(
            list(set(self.selected) & set(other.selected)),
            cutter=self.cutter
        )

    @property
    def page(self):
        assert len(self.pages) == 1
        pages = list(self.pages)
        return pages[0]

    @property
    def left(self):
        if not self.selected:
            return float('inf')
        return min(self.int_attrib('left'))

    @property
    def right(self):
        if not self.selected:
            return -float('inf')
        return max([
            sum(x) for x in zip(self.int_attrib('left'),
                                self.int_attrib('width', 0))
        ])

    @property
    def offset_tops(self):
        return list(
            self.cutter.get_offset_for_page(page) for page in self.pages
        )

    @property
    def top(self):
        if not self.selected:
            return float('inf')
        return min(self.int_attrib('top'))

    @property
    def doc_top(self):
        if not self.selected:
            return float('inf')
        return self.top + min(self.offset_tops)

    @property
    def bottom(self):
        if not self.selected:
            return -float('inf')
        return max([
            sum(x) for x in zip(self.int_attrib('top'),
                                self.int_attrib('height', 0))
        ])

    @property
    def doc_bottom(self):
        if not self.selected:
            return -float('inf')
        return self.bottom + max(self.offset_tops)

    @property
    def width(self):
        if not self.selected:
            return 0
        return max(self.int_attrib('width', 0))

    @property
    def height(self):
        if not self.selected:
            return 0
        return max(self.int_attrib('height', 0))

    @property
    def midx(self):
        return (self.left + self.right) / 2

    @property
    def midy(self):
        return (self.top + self.bottom) / 2

    @property
    def doc_midy(self):
        return (self.doc_top + self.doc_bottom) / 2

    @property
    def elements(self):
        return self.selected

    @property
    def element(self):
        if self.selected:
            return self.selected[0]
        return None

    def filter(self, search=None, auto_regex=None, regex=None, xpath=None,
               tag='text', page=None, pages=None, check=None, **kwargs):
        if search is not None:
            # FIXME: very poor escaping try ahead
            logger.debug('Searching %s', repr_ascii(search))
            r = search.replace('"', r'\"')
            search = 'self::*[contains(., "%s")]' % r
            search = etree.XPath(search)
        elif auto_regex is not None:
            if auto_regex.startswith('^'):
                auto_regex = re.sub(r'^\^', r'^\s*', auto_regex)
            if auto_regex.endswith('$'):
                auto_regex = re.sub(r'\$$', r'\s*$', auto_regex)
            regex = auto_regex.replace(' ', r'\s+')
            logger.debug('Searching[auto-re] %s', repr_ascii(regex))
            r = regex.replace('"', r'\"')
            search = 'self::*[re:test(., "%s", "i")]' % r
            search = etree.XPath(search, namespaces={'re': REGEXP_NS})
        elif regex is not None:
            logger.debug('Searching[re] %s', repr_ascii(regex))
            r = regex.replace('"', r'\"')
            search = 'self::*[re:test(., "%s", "i")]' % r
            search = etree.XPath(search, namespaces={'re': REGEXP_NS})
        if xpath is not None:
            if xpath.startswith('['):
                xpath = 'self::*' + xpath
            xpath = etree.XPath(xpath, namespaces={'re': REGEXP_NS})

        position_checks = []
        for k, v in kwargs.items():
            assert '__' in k
            pos, comp = k.split('__')
            assert pos in ('top', 'bottom', 'left', 'right',
                           'doc_top', 'doc_bottom', 'midx', 'midy', 'doc_midy',
                           'width', 'height')
            comp_func = COMPARISONS[comp]
            position_checks.append(get_compare(comp_func, pos, v))
        position_check = None
        if position_checks:
            position_check = functools.reduce(
                lambda a, b: lambda x: a(x) and b(x), position_checks
            )

        cls = self.__class__

        result = []
        for item in self.selected:
            selitem = cls(item, self.cutter)
            if check is not None and not check(selitem):
                continue
            if search is not None and not search(item):
                continue
            if xpath is not None and not xpath(item):
                continue
            if tag is not None and item.tag != tag:
                continue
            if position_check:
                if not position_check(selitem):
                    continue
            if page is not None:
                if Page.from_item(item).number != page:
                    continue
            if pages is not None:
                if Page.from_item(item).number not in pages:
                    continue

            result.append(item)

        return type(self)(result, cutter=self.cutter)

    def filter_condition(self, condition):
        return type(self)([
            s.element for s in self if
            condition(s)
        ], cutter=self.cutter)

    def left_of(self, selection):
        if isinstance(selection, (int, float)):
            return self.filter_condition(lambda s: s.right < selection)
        if not selection:
            return self.empty()
        return self.filter_condition(lambda s: s.right < selection.left)

    def strictly_left_of(self, selection, mid_point=False):
        if not selection:
            return self.empty()
        return self.filter_condition(
            lambda s: overlap_vertical(s, selection, mid_point=mid_point) and
            s.right < selection.left
        )

    def right_of(self, selection):
        if isinstance(selection, (int, float)):
            return self.filter_condition(lambda s: s.left > selection)
        if not selection:
            return self.empty()
        return self.filter_condition(lambda s: s.left > selection.right)

    def strictly_right_of(self, selection, mid_point=False):
        if not selection:
            return self.empty()
        return self.filter_condition(
            lambda s: overlap_vertical(s, selection, mid_point=mid_point) and
            s.left > selection.right
        )

    def below(self, selection):
        if isinstance(selection, (int, float)):
            return self.filter_condition(lambda s: s.doc_top > selection)
        if not selection:
            return self.empty()
        return self.filter_condition(
            lambda s: s.doc_top > selection.doc_bottom
        )

    def stricly_below(self, selection, mid_point=False):
        if not selection:
            return self.empty()
        return self.filter_condition(
            lambda s: overlap_horizontal(s, selection, mid_point=mid_point) and
            s.doc_top > selection.doc_bottom
        )

    def above(self, selection):
        if isinstance(selection, (int, float)):
            return self.filter_condition(lambda s: s.doc_bottom < selection)
        if not selection:
            return self.empty()
        return self.filter_condition(
            lambda s: s.doc_bottom < selection.doc_top
        )

    def stricly_above(self, selection, mid_point=False):
        if not selection:
            return self.empty()
        return self.filter_condition(
            lambda s: overlap_horizontal(s, selection, mid_point=mid_point) and
            s.doc_bottom < selection.doc_top
        )

    def empty(self):
        return type(self)([], cutter=self.cutter)

    def int_attrib(self, name, default=0):
        return [int(s.attrib.get(name, default)) for s in self.selected]

    def text(self, join_words=True):
        return ' '.join(self.text_list(join_words))

    def clean_text(self, fix_hyphens=True):
        text = self.text()
        text = remove_multispace(text)
        if fix_hyphens:
            text = remove_hyphenation(text)
        return text

    def re(self, reg):
        return re.search(reg, self.text())

    def text_list(self, join_words=True):
        texts = [etree.tostring(
            t, method="text", encoding='utf-8').decode('utf-8')
            for t in self.selected
        ]
        if join_words:
            return [t.strip().replace('- ', '-') for t in texts]
        return texts

    def get_by_line(self, threshold=8):
        current_line = []
        current_top = None
        for el in self:
            if current_top is None:
                current_top = el.doc_top
            if abs(el.doc_top - current_top) > threshold:
                yield type(self)(current_line, self.cutter)
                current_line = []
                current_top = el.doc_top
            current_line.extend(el.selected)
        yield type(self)(current_line, self.cutter)

    def get_table(self, number_of_columns=None, row_threshold=10,
                  is_garbage=lambda x: False):
        current_row_top = None
        current_row = []
        data = []
        cls = self.__class__
        for el in self.selected:
            el = cls(el)
            midrow = el.doc_top
            if current_row_top is None:
                current_row_top = midrow
            else:
                is_similar = similar(
                    current_row_top, midrow,
                    threshold=row_threshold
                )
                if not is_similar:
                    data.append(current_row)
                    current_row = []
                    current_row_top = midrow
            current_row.append(el)
        data.append(current_row)

        max_cols = number_of_columns or max([len(row) for row in data])
        col_layout = [(float('inf'), -float('inf'))] * max_cols
        # try to detect columns
        for row in data:
            if len(row) == max_cols:
                new_col_layout = []
                for lay, col in zip(col_layout, row):
                    new_col_layout.append((
                        min(lay[0], col.left),
                        max(lay[1], col.right)
                    ))
                col_layout = new_col_layout

        # close gaps in column layout
        col_layout = new_col_layout
        new_col_layout = []
        for i, lay in enumerate(col_layout):
            if i == 0:
                left = self.left
            else:
                left = (col_layout[i - 1][1] + lay[0]) / 2

            if i == len(col_layout) - 1:
                right = self.right
            else:
                right = (col_layout[i + 1][0] + lay[1]) / 2

            new_col_layout.append((left, right))
        col_layout = new_col_layout

        new_data = []

        for row in data:
            new_row = []
            for cell in row:
                matching_col = [i for i, c in enumerate(col_layout)
                                if c[0] <= cell.midx <= c[1]]
                if matching_col:
                    new_row.extend([None] * (matching_col[0] - len(new_row)))
                    new_row.append(cell.text())
            new_row.extend([None] * (len(col_layout) - len(new_row)))
            new_data.append(new_row)

        data = new_data
        new_data = []

        # Fix badly merged columns
        for row in data:
            for i, cell in enumerate(row):
                if cell is None or '  ' not in cell:
                    continue
                if i + 1 < len(row) and row[i + 1] is None:
                    row[i], row[i + 1] = cell.split('  ', 1)
                    continue
                if i - 1 > 0 and row[i - 1] is None:
                    row[i - 1], row[i] = cell.split('  ', 1)
                    continue

        # Clean rows
        for row in data:
            if not all([not t or is_garbage(t) for t in row]):
                new_data.append(row)

        data = new_data
        new_data = [[] for i in range(len(data))]

        # Clean columns
        for i in range(len(col_layout)):
            if not all([not row[i] or is_garbage(row[i]) for row in data]):
                for newrow, row in zip(new_data, data):
                    newrow.append(row[i])

        # Merge linebroken rows
        data = new_data
        new_data = []
        row_offset = 0
        if data:
            colcount = float(len(data[0]))
            for i, row in enumerate(data):
                if i > 0 and row.count(None) / colcount >= 0.3:
                    try:
                        for j, cell in enumerate(row):
                            if cell is not None:
                                ind = i - 1 - row_offset
                                if (j < len(new_data[ind]) and
                                        new_data[ind][j] is not None):
                                    if not new_data[ind][j].endswith(' '):
                                        new_data[ind][j] += ' '
                                    new_data[ind][j] += cell
                                row_offset += 1
                    except Exception:
                        new_data.append(row)
                else:
                    new_data.append(row)
        data = new_data

        return data
