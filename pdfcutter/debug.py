import base64
import html

from wand.image import Image
from wand.drawing import Drawing
from wand.color import Color

DATA_URL_PNG = 'data:image/png;base64,'


class VisualDebugger():
    def __init__(self, filename, resolution=72):
        self.filename = filename
        self.resolution = resolution

    def get_image(self, page_no):
        filename = "{}[{}]".format(self.filename, page_no - 1)
        img = Image(
                filename=filename,
                resolution=self.resolution,
                background=Color('#fff'))
        img.alpha_channel = False
        return img

    def debug(self, selection, page=None):
        if page is not None:
            selection = selection.filter(page=page)

        if not selection:
            return DebugFragment({}, selection)

        page_images = {}
        for page in selection.pages:
            page_images[page.number] = self.get_image(page.number)
            scale = page_images[page.number].width / page.width

        return DebugFragment(page_images, selection, scale=scale)


def style_attr(styles):
    return ';'.join('{}:{}'.format(k, v) for k, v in styles.items())


class DebugFragment():
    def __init__(self, page_images, selection, scale=1.0):
        self.page_images = page_images
        self.selection = selection
        self.scale = scale

    def get_base64image(self, page_number):
        png_bytes = self.page_images[page_number].make_blob('png')
        b64_string = base64.b64encode(png_bytes).decode('utf-8')
        return DATA_URL_PNG + b64_string

    def draw(self, page_number):
        f = self.scale
        image = self.page_images[page_number]
        for item in self.selection:
            with Drawing() as draw:
                draw.fill_color = Color('transparent')
                draw.stroke_width = 2
                draw.stroke_color = Color('red')
                draw.rectangle(left=item.left * f, top=item.top * f,
                               right=item.right * f, bottom=item.bottom * f)
                draw(image)
        return image

    def _repr_html_(self):
        if not self.page_images:
            return '<p>Empty selection</p>'
        return ''.join(
            self.get_page_as_html(pn) for pn in sorted(self.page_images)
        )

    def get_page_as_html(self, page_number):
        image = self.page_images[page_number]
        style = {
            'position': 'relative',
            'width': '{}px'.format(image.width),
            'height': '{}px'.format(image.height),
            'background-image': "url('{}')".format(
                self.get_base64image(page_number)
            )
        }
        return '''<div class="pdfcutter-page"><h5>Page {page_number}</h5>
                  <div style="{style}">{items}</div></div>'''.format(
            page_number=page_number,
            style=style_attr(style),
            items=''.join(self.get_items_as_html(page_number))
        )

    def display(self):
        from IPython.display import display, HTML
        display(HTML(self._repr_html_()))

    def get_items_as_html(self, page_number=None):
        selection = self.selection
        if page_number is not None:
            selection = selection.filter(page=page_number)
        for item in selection:
            style = {
                'position': 'absolute',
                'left': '{}px'.format(item.left * self.scale),
                'top': '{}px'.format(item.top * self.scale),
                'width': '{}px'.format(item.width * self.scale),
                'height': '{}px'.format(item.height * self.scale),
                'outline': '2px solid #f00',
            }

            yield '''<div style="{style}" title="{title}">
                     </div>'''.format(
                style=style_attr(style),
                title=html.escape(str(item))
            )
