'''
The MIT License (MIT)

Copyright (c) 2013 Robert H Chase

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
import json
import re

import traceback

from httphandler import HTTPHandler


class RESTHandler(HTTPHandler):

    '''
        Identify and execute REST handler functions.

        The RESTHandler context is a RESTMapper instance, with mappings defined
        for each URI.

        A handler function calls rest_send(...) to send a response.

        Callback

            on_rest_send(code, message, content)

        To send response:

            rest_send(content, code, message)
    '''

    def on_http_data(self):
        handler, groups = self.context.match(
            self.http_resource, self.http_method)
        if handler:
            try:
                handler(self, *groups)
            except Exception, e:
                traceback.format_exc()
                self.rest_send(str(
                    e), code=501, message='Internal Server Error')
        else:
            self.rest_not_found()

    def rest_send(self, content=None, code=200, message='OK'):
        args = {'code': code, 'message': message}
        if content:
            args['content'] = content
        self.on_rest_send(code, message, content)
        self.send_server(**args)

    def on_rest_send(self, code, message, content):
        pass


class RESTMapper(object):

    def __init__(self):
        self.__mapping = []
        self.setup()

    def setup(self):
        pass

    def add(self, pattern, get=None, post=None, put=None, delete=None):
        self.__mapping.append(
            RESTMapping(pattern, get, post, put, delete)
        )

    def match(self, resource, method):
        for mapping in self.__mapping:
            m = mapping.pattern.match(resource)
            if m:
                handler = mapping.method.get(method.lower(), None)
                if handler:
                    return handler, m.groups()
        return None, None


class RESTMapping(object):

    def __init__(self, pattern, get, post, put, delete):
        self.pattern = re.compile(pattern)
        self.method = {
            'get': get,
            'post': post,
            'put': put,
            'delete': delete
        }
