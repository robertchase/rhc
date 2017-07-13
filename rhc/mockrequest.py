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
import logging

import rhc.httphandler as httphandler
import rhc.resthandler as resthandler


log = logging.getLogger(__name__)


class Context(object):
    def __init__(self):
        self.context = None


class MockHandler(httphandler.HTTPHandler):
    ''' fake http document for creating a MockRequest

        initialize with values that you want to mock in an incoming HTTP document
    '''

    def __init__(self, **kwargs):
        self._setup()
        self.id = -1
        self.context = Context()
        self.__dict__.update(kwargs)


class MockRequest(resthandler.RESTRequest):

    def respond(self, *args, **kwargs):
        self.r_args = args
        self.r_kwargs = kwargs
