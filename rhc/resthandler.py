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

        To send response:

            rest_send(content, code, message)

        Callback

            on_rest_send(code, message, content)
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
            self.rest_send(code=404, message='Not Found')

    def rest_send(self, content=None, code=200, message='OK', headers=None):
        args = {'code': code, 'message': message}
        if content:
            args['content'] = content
        if headers:
            args['headers'] = headers
        self.on_rest_send(code, message, content, headers)
        self.send_server(**args)

    def on_rest_send(self, code, message, content, headers):
        pass


class RESTMapper(object):

    '''
        A URI-to-executable mapper that is passed as the context for a
        RESTHandler.

        The on_http_data method of the RESTHandler calls the match method
        on this object to resolve a URI to a previously defined pattern.
        Patterns are added with the add method.
    '''

    def __init__(self):
        self.__mapping = []

    def add(self, pattern, get=None, post=None, put=None, delete=None):
        '''
            Add a mapping between a URI and a CRUD method.

            The pattern is a regex string which can include groups. If
            groups are included in the regex, they will be passed as
            parameters to the matching method.

            The match method will evaluate each mapping in the order
            that they are added. The first match wins.

            For example:

                add('/foo/(\d+)/bar', get=my_func)

                will match:

                    GET /foo/123/bar HTTP/1.1

                resulting in the call:

                    my_func(123)

                in this case, my_func must be defined to take the
                parameter.
        '''
        self.__mapping.append(
            RESTMapping(pattern, get, post, put, delete)
        )

    def match(self, resource, method):
        '''
            Match a resource + method to a RESTMapping

            The resource parameter is the resource string from the
            http call. The method parameter is the method from
            the http call. The user shouldn't call this method, it
            is called by the on_http_data method of the
            RESTHandler.

            Step through the mappings in the order they were defined
            and look for a match on the regex which also has a method
            defined.
        '''
        for mapping in self.__mapping:
            m = mapping.pattern.match(resource)
            if m:
                handler = mapping.method.get(method.lower(), None)
                if handler:
                    return handler, m.groups()
        return None, None


class RESTMapping(object):

    ''' container for one mapping definition '''

    def __init__(self, pattern, get, post, put, delete):
        self.pattern = re.compile(pattern)
        self.method = {
            'get': get,
            'post': post,
            'put': put,
            'delete': delete
        }
