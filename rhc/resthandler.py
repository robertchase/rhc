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
import time
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

    @property
    def id(self):
        return self.handler.id

    def defer(self, deferred_fn, immediate_fn, *args, **kwargs):
        '''
            defer the request until immediate_fn completes; then call deferred_fn

            if immediate_fn does not complete succesfully, then deferred_fn is not called;
            instead, the error is handled by responding on the request. the default error
            response parameters are (400, result), which can be overridden in several ways
            with the optional kwargs described below.

            Parameters:
                deferred_fn(request, result) - called when immediate_fn succesfully completes (rc==0)
                immediate_fn - async function which terminates with (rc, result)
                args & kwargs - arguments for immediate_fn, less optional kwargs below

            Optional kwargs to override default error handling:

                error_fn - called with (request, result) if immediate_fn fails (rc != 0)
                           must respond on the request or risk hanging the connection
                error_msg - used in lieu of result if immediate_fn fails (rc != 0)
                            result is logged as a warning
                error_200 - if True, respond with (200, {"error": result}

            Notes:

                1. deferred_fn is for the happy-path. it is not called with the (rc, result)
                   pattern, but is instead called with (request, result). the idea is that
                   the handing of the request is what is deferred by this method, and that
                   if everthing is working, we keep going sequentially through the logic.
                   the deferred_fn is meant to mirror a rest handler's signature.

                2. the immediate_fn is called with a callback as the first parameter and
                   is expected to invoke that callback with the (rc, result) pattern upon
                   completion. rc is 0 (zero) for successful completion; otherwise non-zero.

                3. immediate_fn is expected to perform an async operation, although it
                   doesn't have to. if immediate_fn is not async, it makes more sense to
                   call it inline.
        '''

        # we have to do this since we don't know how many args immediate_fn will have (if any)
        error_fn = kwargs.pop('error_fn', None)
        error_msg = kwargs.pop('error_msg', None)
        error_200 = kwargs.pop('error_200', False)

        def on_defer(rc, result):
            if rc == 0:
                return deferred_fn(self, result)  # happy path
            if error_fn:
                return error_fn(self, result)
            if error_msg:
                log.warning('error cid=%s: %s', self.handler.id, result)
                result = error_msg
            if error_200:
                return self.respond({'error': result})
            self.respond(400, result)

        self.delay()
        immediate_fn(on_defer, *args, **kwargs)

    def respond(self, *args, **kwargs):
        '''
            the args/kwargs usually match the RESTResult __init__ method

            in the case of a single argument, the RESTResult coerce method is called to deal with some
            legacy ways of using this method.
        '''
        if len(kwargs) == 0 and len(args) == 1:
            result = RESTResult.coerce(args[0])
        else:
            result = RESTResult(*args, **kwargs)
        result.close = self.http_headers.get('Connection') == 'close'  # grab Connection from cached headers in case they have been cleared on the HTTPHandler
        self.is_delayed = True  # treat as delayed to stop on_http_data from responding a second time in the non-delay case
        self.handler.rest_response(result)

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

        self.code = code
        self.close = False

        if isinstance(content, (types.DictType, types.ListType, types.FloatType, types.BooleanType, types.IntType)):
            try:
                content = json.dumps(content)
                content_type = 'application/json; charset=utf-8'
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
                403: 'Forbidden',
                404: 'Not Found',
                500: 'Internal Server Error',
            }.get(code, '')
        self.message = message
        self.content = content
        self.headers = headers

    @classmethod
    def coerce(cls, result):
        if isinstance(result, cls):
            return result           # already a RESTResult
        if isinstance(result, int):
            return cls(result)      # integer: treat as status code
        if isinstance(result, tuple):
            return cls(*result)     # tuple: treat as *args
        return cls(content=result)  # otherwise, assume status code 200 with result being the content


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
        request object; the socket will remain open and set the
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
                if not request.is_delayed:
                    self.rest_response(RESTResult.coerce(result))
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
        result = RESTResult.coerce(result)
        self._rest_send(result.content, result.code, result.message, result.headers, result.close)

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

    def _rest_send(self, content=None, code=200, message='OK', headers=None, close=False):
        args = dict(code=code, message=message, close=close)
        if content:
            args['content'] = content
        if headers:
            args['headers'] = headers
        self.on_rest_send(code, message, content, headers)
        self.send_server(**args)

    def on_rest_send(self, code, message, content, headers):
        pass


class LoggingRESTHandler(RESTHandler):

    def on_open(self):
        log.info('open: cid=%d, %s', self.id, self.name)

    def on_close(self):
        log.info('close: cid=%s, reason=%s, t=%.4f, rx=%d, tx=%d', getattr(self, 'id', '.'), self.close_reason, time.time() - self.start, self.rxByteCount, self.txByteCount)

    def on_rest_data(self, request, *groups):
        log.info('request cid=%d, method=%s, resource=%s, query=%s, groups=%s', self.id, request.http_method, request.http_resource, request.http_query_string, groups)

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


def content_to_json(*fields, **kwargs):
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

                 if field name is a tuple with three elements, then the third
                 element is a default value.
        as_args - if true, append fields as described above, else add to decorated
                  call as kwargs.

    Errors:
        400 - json conversion fails or specified fields not present in json
    Notes:
         1. This is responsive to the is_delayed flag on the request.
    '''
    as_args = kwargs.setdefault('as_args', True)

    def __content_to_json(rest_handler):
        def inner(request, *args):
            kwargs = dict()
            try:
                if fields:
                    args = list(args)
                    for field in fields:
                        if isinstance(field, tuple):
                            if len(field) == 3:
                                fname, ftype, fdflt = field
                                value = request.json.get(fname, fdflt)
                            else:
                                fname, ftype = field
                                value = request.json[fname]
                            if ftype:
                                value = ftype(value)
                        else:
                            fname = field
                            value = request.json[fname]
                        if as_args:
                            args.append(value)
                        else:
                            kwargs[fname] = value
            except KeyError as e:
                return request.respond(RESTResult(400, 'Missing required key: %s' % str(e)))
            except Exception as e:
                return request.respond(RESTResult(400, "Unable to read field '%s': %s" % (fname, e.message)))
            return rest_handler(request, *args, **kwargs)
        return inner
    return __content_to_json
