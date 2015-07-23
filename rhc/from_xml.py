import types
from StringIO import StringIO
from xml.sax import make_parser
from xml.sax.handler import ContentHandler


class XmlToDict(ContentHandler):

    def __init__(self, groupby=None):
        self.data = ''
        self.stack = [(None, {})]

    def startElement(self, name, attrs):
        self.stack.append((name, {n: v for n, v in attrs.items()}))

    def endElement(self, name):
        value = self.data.strip()
        self.data = ''

        name, collection = self.stack.pop()
        p_name, p_collection = self.stack[-1]

        if not value:
            value = collection

        if name in p_collection:
            p_value = p_collection[name]
            if not isinstance(p_value, types.ListType):
                p_value = p_collection[name] = [p_value]
            p_value.append(value)
        else:
            p_collection[name] = value

    def characters(self, ch):
        self.data += ch.encode('ascii')


def from_xml(data, handler_class=XmlToDict):
    handler = handler_class()
    p = make_parser()
    p.setContentHandler(handler)
    p.parse(StringIO(data))
    return handler.stack[0][1]
