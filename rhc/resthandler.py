'''
The MIT License (MIT)

Copyright (c) 2013-2014 Robert H Chase

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
import sys
import types
import urlparse

from httphandler import HTTPHandler


class RESTResult(object):
    def __init__(self, code=200, content='', headers=None, message=None, content_type=None):
        self.code = code

        if type(content) in (types.DictType, types.ListType):
            try:
                content = json.dumps(content)
                content_type = 'application/json'
            except Exception:
                content = str(content)

        if content_type:
            if not headers:
                headers = {}
            headers['Content-Type'] = content_type

        if not message:
            message = {
                200: 'OK',
                201: 'Created',
                302: 'Found',
                400: 'Bad Request',
                401: 'Unauthorized',
                404: 'Not Found',
            }.get(code, '')
        self.message = message
        self.content = content
        self.headers = headers


class RESTHandler(HTTPHandler):
    '''
        Identify and execute REST handler functions.

        The RESTHandler context is a RESTMapper instance, with mappings defined
        for each URI. When an http request URI matches a mapping regex and
        method, the respective rest_handler is called with this object as the
        first parameter, followed by any regex groups.

        A rest_handler function returns a RESTResult object.

        Callback methods:
            on_rest_data(self, *groups)
            on_rest_exception(self, exc_type, exc_value, exc_traceback)
            on_rest_send(self, code, message, content, headers)
    '''

    def on_http_data(self):
        handler, groups = self.context._match(self.http_resource, self.http_method)
        if handler:
            try:
                self.on_rest_data(*groups)
                result = handler(self, *groups)
                self._rest_send(result.content, result.code, result.message, result.headers)
            except Exception:
                content = self.on_rest_exception(*sys.exc_info())
                kwargs = dict(code=501, message='Internal Server Error')
                if content:
                    kwargs['content'] = str(content)
                self._rest_send(**kwargs)
        else:
            self._rest_send(code=404, message='Not Found')

    def on_rest_data(self, *groups):
        ''' called on rest_handler match '''
        pass

    def on_rest_exception(self, exception_type, exception_value, exception_traceback):
        ''' handle Exception raised during REST processing

        If a REST handler raises an Exception, this method is called with the sys.exc_info
        tuple to allow for logging or any other special handling.

        If a value is returned, it will be sent as the content in the
        "501 Internal Server Error" response.

        To return a traceback string in the 501 message:
            import traceback
            return traceback.format_exc(exception_traceback)
        '''
        return None

    def _rest_send(self, content=None, code=200, message='OK', headers=None):
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

        The on_http_data method of the RESTHandler calls the _match method
        on this object to resolve a URI to a previously defined pattern.
        Patterns are added with the add method.
    '''

    def __init__(self):
        self.__mapping = []
        self.map()

    def map(self):
        '''convenience function for initialization '''
        pass

    def add(self, pattern, get=None, post=None, put=None, delete=None):
        '''
            Add a mapping between a URI and a CRUD method.

            The pattern is a regex string which can include groups. If
            groups are included in the regex, they will be passed as
            parameters to the matching method.

            The _match method will evaluate each mapping in the order
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
        self.__mapping.append(RESTMapping(pattern, get, post, put, delete))

    def _match(self, resource, method):
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
                handler = mapping.method.get(method.lower())
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


def content_to_json(*fields):
    '''rest_handler decorator that converts handler.html_content to handler.json

    The content must be a valid json document or a valid URI query string (as
    produced by a POSTed HTML form). If the content starts with a '[' or '{',
    it is treated as json; else it is treated as a URI. The URI only expects
    one value per key.

    Arguments:
        fields - an optional list of field names. If specified, the names will
                 be used to look up values in the json dictionary which are
                 appended, in order, to the rest_handler's argument list. The
                 specified fields must be present in the content.

    Errors:
        400 - json conversion fails or specified fields not present in json
    '''
    def __content_to_json(rest_handler):
        def inner(handler, *args):
            try:
                if handler.http_content.lstrip()[0] in '[{':
                    handler.json = json.loads(handler.http_content)
                else:
                    handler.json = {n: v for n, v in urlparse.parse_qsl(handler.http_content)}
                if fields:
                    args = list(args)
                    args.extend(handler.json[n] for n in fields)
            except Exception as e:
                return RESTResult(400, e.message)
            return rest_handler(handler, *args)
        return inner
    return __content_to_json
