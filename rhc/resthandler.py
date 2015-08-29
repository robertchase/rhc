'''
The MIT License (MIT)

Copyright (c) 2013-2015 Robert H Chase

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
import datetime
import json
import re
import sys
import traceback
import types
import urlparse

from httphandler import HTTPHandler

import logging
log = logging.getLogger(__name__)


class RESTRequest(object):

    def __init__(self, handler):
        self.handler = handler
        self.context = handler.context.context  # context from RESTMapper
        self.http_message = handler.http_message
        self.http_headers = handler.http_headers
        self.http_content = handler.http_content
        self.http_method = handler.http_method
        self.http_multipart = handler.http_multipart
        self.http_resource = handler.http_resource
        self.http_query_string = handler.http_query_string
        self.http_query = handler.http_query
        self.timestamp = datetime.datetime.now()
        self.is_delayed = False

    def delay(self):
        self.is_delayed = True

    def respond(self, result):
        if self.is_delayed:
            self.handler.rest_response(result)
        else:
            return result

    @property
    def json(self):
        if not hasattr(self, '_json'):
            if self.http_content and self.http_content.lstrip()[0] in '[{':
                try:
                    self._json = json.loads(self.http_content)
                except Exception:
                    raise Exception('Unable to parse json content')
            elif len(self.http_query) > 0:
                self._json = self.http_query
            else:
                self._json = {n: v for n, v in urlparse.parse_qsl(self.http_content)}
        return self._json


class RESTResult(object):
    def __init__(self, code=200, content='', headers=None, message=None, content_type=None):

        # coerce arguments (note that rest_response sets content)
        if isinstance(content, int):
            code, content = content, ''
        elif isinstance(content, tuple) and len(content) == 2:
            code, content = content
        self.code = code

        if type(content) in (types.DictType, types.ListType, types.FloatType, types.BooleanType):
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
                204: 'No Content',
                302: 'Found',
                400: 'Bad Request',
                401: 'Unauthorized',
                404: 'Not Found',
            }.get(code, '')
        self.message = message
        self.content = content
        self.headers = headers


class RESTDelay(object):
    ''' Indicate delayed response: see RESTHandler '''
    pass


class RESTHandler(HTTPHandler):
    '''
        Identify and execute REST handler functions.

        The RESTHandler context is a RESTMapper instance, with mappings defined
        for each URI. When an http request URI matches a mapping regex and
        method, the respective rest_handler is called with this object as the
        first parameter, followed by any regex groups.

        A rest_handler function returns a RESTResult object, or something which
        is coerced to a RESTResult by the rest_response method, when an immediate
        response is available. In order to delay a response (to prevent
        blocking the server) a rest_handler can call the delay() function on the
        request object or return a RESTDelay, followed by a future call to
        rest_response. A RESTDelay will keep the socket open and set the
        is_delayed flag on the RESTRequest.

        Callback methods:
            on_rest_data(self, *groups)
            on_rest_exception(self, exc_type, exc_value, exc_traceback)
            on_rest_send(self, code, message, content, headers)
    '''

    def on_http_data(self):
        handler, groups = self.context._match(self.http_resource, self.http_method)
        if handler:
            try:
                request = RESTRequest(self)
                self.on_rest_data(request, *groups)
                result = handler(request, *groups)
                if isinstance(result, RESTDelay):
                    request.is_delayed = True
                if request.is_delayed:
                    # rest_response() will be called later; remove Connection:close to keep connection around
                    if 'Connection' in self.http_headers:
                        del self.http_headers['Connection']
                else:
                    self.rest_response(result)
            except Exception:
                content = self.on_rest_exception(*sys.exc_info())
                kwargs = dict(code=501, message='Internal Server Error')
                if content:
                    kwargs['content'] = str(content)
                self._rest_send(**kwargs)
        else:
            self.on_rest_no_match()
            self._rest_send(code=404, message='Not Found')

    def on_rest_data(self, request, *groups):
        ''' called on rest_handler match '''
        pass

    def on_rest_no_match(self):
        pass

    def rest_response(self, result):
        if not isinstance(result, RESTResult):
            result = RESTResult(content=result)
        self._rest_send(result.content, result.code, result.message, result.headers)

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


class LoggingRESTHandler(RESTHandler):

    NEXT_ID = 0
    NEXT_REQUEST_ID = 0

    def on_open(self):
        self.id = LoggingRESTHandler.NEXT_ID = LoggingRESTHandler.NEXT_ID + 1
        log.info('open: cid=%d, %s', self.id, self.name)

    def on_close(self):
        log.info('close: cid=%s, %s: reason=%s', getattr(self, 'id', '.'), self.name, self.close_reason)

    def on_rest_data(self, request, *groups):
        request.id = LoggingRESTHandler.NEXT_REQUEST_ID = LoggingRESTHandler.NEXT_REQUEST_ID + 1
        log.info('request cid=%d, rid=%d, method=%s, resource=%s, query=%s, groups=%s', self.id, request.id, request.http_method, request.http_resource, request.http_query_string, groups)

    def on_rest_send(self, code, message, content, headers):
        log.debug('response cid=%d, code=%d, message=%s, headers=%s', self.id, code, message, headers)

    def on_rest_no_match(self):
        log.warning('no match cid=%d, method=%s, resource=%s', self.id, self.http_method, self.http_resource)

    def on_http_error(self):
        log.warning('http error cid=%d: %s', self.id, self.error)

    def on_rest_exception(self, exception_type, value, trace):
        log.exception('exception encountered:')
        return traceback.format_exc(trace)


class RESTMapper(object):
    '''
        A URI-to-executable mapper that is passed as the context for a
        RESTHandler.

        If a context is specified, it is included in each request as
        request.context. If the requests are handled in separate threads
        it is important to serialize access to this variable since it
        is shared.

        The on_http_data method of the RESTHandler calls the _match method
        on this object to resolve a URI to a previously defined pattern.
        Patterns are added with the add method.
    '''

    def __init__(self, context=None):
        self.context = context
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


def import_by_pathname(target):
    if isinstance(target, str):
        modnam, clsnam = target.rsplit('.', 1)
        mod = __import__(modnam)
        for part in modnam.split('.')[1:]:
            mod = getattr(mod, part)
        return getattr(mod, clsnam)
    return target


class RESTMapping(object):

    ''' container for one mapping definition '''

    def __init__(self, pattern, get, post, put, delete):
        self.pattern = re.compile(pattern)
        self.method = {
            'get': import_by_pathname(get),
            'post': import_by_pathname(post),
            'put': import_by_pathname(put),
            'delete': import_by_pathname(delete),
        }


def content_to_json(*fields):
    '''rest_handler decorator that converts handler.html_content to handler.json

    The content must be a valid json document or a valid URI query string (as
    produced by a POSTed HTML form). If the content starts with a '[' or '{',
    it is treated as json; else it is treated as a URI. The URI only expects
    one value per key.

    Arguments:
        fields - a list of field names. the names will be used to look up
                 values in the json dictionary which are appended, in order,
                 to the rest_handler's argument list. The specified fields
                 must be present in the content.

                 if a field name is a tuple, then the first element is the name,
                 which is treated as stated above, and the second element is
                 a type conversion function which accepts the value and returns
                 a new value. for instance ('a', int) will look up the value
                 for 'a', and convert it to an int (or fail trying).

    Errors:
        400 - json conversion fails or specified fields not present in json
    Notes:
         1. This is responsive to the is_delayed flag on the request.
    '''
    def __content_to_json(rest_handler):
        def inner(request, *args):
            try:
                if fields:
                    args = list(args)
                    for field in fields:
                        fname, ftype = field if isinstance(field, tuple) else (field, None)
                        value = request.json[fname]
                        if ftype:
                            value = ftype(value)
                        args.append(value)
            except KeyError as e:
                return request.respond(RESTResult(400, 'Missing required key: %s' % str(e)))
            except Exception as e:
                return request.respond(RESTResult(400, e.message))
            return rest_handler(request, *args)
        return inner
    return __content_to_json
