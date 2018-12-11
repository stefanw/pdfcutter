import re


PDF_HYPHEN = re.compile('(\\w)([\u00AD-]\\s)')
MULTI_SPACE = re.compile(r' +')


def remove_multispace(text):
    return MULTI_SPACE.sub(' ', text)


def remove_hyphenation(text):
    return PDF_HYPHEN.sub('\\1', text)


def repr_ascii(obj):
    return str(obj.encode("ASCII", "backslashreplace"), "ASCII")


def cmp_to_key(mycmp):
    'Convert a cmp= function into a key= function'
    class K(object):
        def __init__(self, obj, *args):
            self.obj = obj

        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0

        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0

        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0

        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0

        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0

        def __ne__(self, other):
            return mycmp(self.obj, other.obj) != 0
    return K


def similar(a, b, threshold=None, epsilon=0.005):
    if threshold is None:
        return abs(a - b) / ((a + b) / 2) < epsilon
    else:
        return abs(a - b) < threshold


def overlap_horizontal(a, b, mid_point=False):
    b_min = b.left
    b_max = b.right
    if mid_point:
        b_min = b_max = (b_min + b_max) / 2
    return not (a.left > b_max or a.right < b_min)


def overlap_vertical(a, b, mid_point=False):
    b_min = b.doc_top
    b_max = b.doc_bottom
    if mid_point:
        b_min = b_max = (b_min + b_max) / 2
    return not (a.doc_top > b_max or a.doc_bottom < b_min)


def obj_to_coord(x):
    return (int(x.attrib['top']), int(x.attrib['left']))


@cmp_to_key
def fuzzy_compare(a, b):
    a = obj_to_coord(a)
    b = obj_to_coord(b)
    if similar(a[0], b[0], 4):
        if similar(a[1], b[1], 4):
            return 0
        return 1 if a[1] > b[1] else -1
    return 1 if a[0] > b[0] else -1


def get_compare(comp_func, attr, value):
    def compare(item):
        return comp_func(getattr(item, attr), value)
    return compare
