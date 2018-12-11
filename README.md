# PDFCutter

There are better ways than storing data in a PDF.
**pdfcutter** is for when you need to get it out again.

Works on XML output of `pdftohtml` which belongs to `poppler-utils`.


```python

import pdfcutter

cutter = pdfcutter.PDFCutter(filename='./some.pdf')

name_label = cutter.filter(page=1, search='Name:')
name = cutter.filter(page=1).strictly_right_of(name_label).text()
```

