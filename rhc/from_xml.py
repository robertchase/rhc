'''
The MIT License (MIT)

Copyright (c) 2013-2017 Robert H Chase

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''
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
