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
import functools
import json
import string
import time
import types

from socket import gethostbyname
from urllib import urlencode
from urlparse import urlparse

from httphandler import HTTPHandler
from tcpsocket import SERVER, SSLParam
from timer import TIMERS


import logging
log = logging.getLogger(__name__)


def connect(callback, url, method='GET', body=None, headers=None, is_json=True, is_debug=False, timeout=5.0, wrapper=None, handler=None, **kwargs):
    '''
        Make an async rest connection, executing callback on completion

        Parameters:

            callback - a callable expecting (rc, result), where rc=0 on success
            url - full url of the resource being referenced
            method - http method (default=GET)
            body - http content (default=None)
            headers - http headers (default=None)
            is_json - if True, successful result is json.loads-ed (default=True)
            is_debug - if True, log.debug message are printed at key points: (default=False)
                           connection init
                           connection open
                           connection close
            timeout - tolerable period of network inactivity in seconds (default=5.0)
            wrapper - if successful, wrap result in wrapper before callback (default=None)
            handler - handler class for connection (default=None)
                      a subclass of ConnectionHandler with special logic in setup or evaluate
            kwargs - see notes about automatic generation of document body

        Notes:

            1. If body is None and no additional kwargs are supplied, then body is empty. If body
               is None and additional kwargs are supplied they are json.dumps-ed into a the
               body and a:
                   'Content-Type': 'application/json; charset=utf-8'
               header is added.
    '''
    p = _URLParser(url)
    _connect(callback, url, p.host, p.address, p.port, p.resource, p.is_ssl, method, body, headers, is_json, is_debug, timeout, wrapper, handler, kwargs)


def immediate(fn):
    ''' prepare a function as a RESTRequest.defer immediate function

        the function must accept a callback followed by zero or
        more parameters. the callback accepts two arguments, the
        first being 0 for success, or anything else for failure,
        the second being a result value.

        the function is wrapped so that it will not run until it is
        called twice. the first call assigns arguments and returns
        a new function. the new function accepts a callback and
        calls the original function with the callback and arguments.

        works as a decorator or function.
    '''
    def _immediate(*args, **kwargs):
        def _call(callback):
            fn(callback, *args, **kwargs)
        return _call
    return _immediate


class Connection(object):
    '''
        Wrapper for managing setup data for the connection function.

        Having url data floating all around the source code is a maintenance
        problem. This class can be instantiated at startup with default values
        for a connection, allowing fewer required values at connection start.

        A simple example:

            con = Connection('https://somewhere:12345')
            ...
            con.get(on_ping, '/ping')

        Parameters:

            url - base url for connection destination
            is_json - if True, successful result is json.loads-ed
            is_debug - if True, log.debug message are printed at key points
            timeout - tolerable period of network inactivity in seconds
            wrapper - if successful, wrap result in wrapper before callback
            handler - handler class for connection
                      a subclass of ConnectionHandler with special logic in setup or evaluate

        Notes:

            1.  The url is parsed and resolved once, preventing dns problems
                from breaking connection setup after a program is initialized.

            2.  Convenience CRUD methods are available for get, post, put and
                delete.

            3.  Calls to the connect method or to one of the convenience methods
                act just like the module-level connect function, with url (and
                method) automatically supplied.  Any parameters specified to
                these methods will override default values specified at
                Connection init.
    '''

    def __init__(self, url, is_json=True, is_debug=False, timeout=5.0, wrapper=None, handler=None):
        self.url = url
        p = _URLParser(url)
        self.host = p.host
        self.address = p.address
        self.port = p.port
        self.is_ssl = p.is_ssl
        self.is_json = is_json
        self.is_debug = is_debug
        self.timeout = timeout
        self.wrapper = wrapper
        self.handler = handler

    def __getattr__(self, name):
        if name.lower() in ('get', 'post', 'put', 'delete'):
            return functools.partial(self.connect, name.upper())
        raise AttributeError(name)

    def add_resource(self, name, path, method='GET', required=[], optional=[], **kwargs):
        ''' bind a path + method to a name on the Connection

            name - unique attribute name on Connection
            path - path to resource on connection (see Note 2)
            method - CRUD method name (default=GET)
            required - list of required positional arguments
                       required arguments will be coerced into a dict and supplied as body
            optional - list of optional positional arguments
                       optional arguments will be coerced into a dict along with required

            Notes:

                1. the bound attribute is an async.immediate.

                2. the path can have substitution variables which are a subset of the
                   string.format syntax, for example '/mypath/{my_variable}'. this will
                   consume the first positional argument (which is automatically
                   required) to replace the bracketed value in the string. multiple
                   substitutions are allowed.

                   a bracketed variable name must be specified, and must not be an
                   integer. this is a subset of what is allowed with string.format.
        '''
        if name in self.__dict__:
            raise Exception("resource '%s' already defined in Connection instance" % name)

        substitution = [t[1] for t in string.Formatter().parse(path) if t[1] is not None]  # grab substitution names

        def _resource(callback, *args, **_kwargs):
            if len(args) < len(substitution + required) or len(args) > len(substitution + required + optional):
                raise Exception('Incorrect number of arguments supplied, expecting: sub=%s, req=%s, opt=%s' % (str(substitution), str(required), str(optional)))
            if len(substitution):
                sub, _args = args[:len(substitution)], args[len(substitution):]
                _path = path.format(**dict(zip(substitution, sub)))
            else:
                req = required
                _path = path
            kwargs.update(_kwargs)
            if len(_args):
                kwargs['body'] = dict(zip(req + optional, _args))
            return self.connect(method, callback, self.url + _path, **kwargs)
        setattr(self, name, immediate(_resource))

    def connect(self, method, callback, path, *args, **kwargs):
        is_json = kwargs.pop('is_json', self.is_json)
        is_debug = kwargs.pop('is_debug', self.is_debug)
        timeout = kwargs.pop('timeout', self.timeout)
        wrapper = kwargs.pop('wrapper', self.wrapper)
        handler = kwargs.pop('handler', self.handler)

        url = self.url + path
        body = kwargs.pop('body', None)
        headers = kwargs.pop('headers', None)
        _connect(callback, url, self.host, self.address, self.port, path, self.is_ssl, method, body, headers, is_json, is_debug, timeout, wrapper, handler, kwargs)


def _connect(callback, url, host, address, port, path, is_ssl, method, body, headers, is_json, is_debug, timeout, wrapper, handler, kwargs):
    c = ConnectContext(callback, url, method, path, host, headers, body, is_json, is_debug, timeout, wrapper, kwargs)
    SERVER.add_connection((address, port), ConnectHandler if handler is None else handler, c, ssl=is_ssl)


class ConnectContext(object):

    def __init__(self, callback, url, method, path, host, headers, body, is_json, is_debug, timeout, wrapper, kwargs):
        self.callback = callback
        self.url = url
        self.method = method
        self.path = path
        self.host = host
        self.headers = headers
        self.body = body
        self.is_json = is_json
        self.is_debug = is_debug
        self.timeout = timeout
        self.wrapper = wrapper
        self.kwargs = kwargs


class ConnectHandler(HTTPHandler):

    def on_init(self):
        self.is_done = False
        self.setup()
        self.timer = TIMERS.add(self.context.timeout * 1000, self.on_timeout).start()

    def after_init(self):
        if self.context.is_debug:
            log.debug('starting outbound connection, oid=%s: %s %s', self.id, self.context.method, self.context.url)

    def setup(self):
        context = self.context

        if context.body is None:
            if len(context.kwargs) == 0:
                context.body = ''
            else:
                context.body = context.kwargs

        if isinstance(context.body, (dict, list, tuple, float, bool, int)):
            try:
                context.body = json.dumps(context.body)
            except Exception:
                context.body = str(context.body)
            else:
                if context.headers is None:
                    context.headers = {}
                context.headers['Content-Type'] = 'application/json; charset=utf-8'

        context.send = {'method': context.method, 'host': context.host, 'resource': context.path, 'headers': context.headers, 'content': context.body}

    def done(self, result, rc=0):
        if self.is_done:
            return
        self.is_done = True
        self.timer.cancel()
        self.context.callback(rc, result)
        self.close_reason = 'transaction complete'
        self.close()

    def on_open(self):
        if self.context.is_debug:
            log.debug('open oid=%s: %s', self.id, self.full_address())

    def on_close(self):
        reason = self.close_reason
        if self.context.is_debug:
            now = time.time()
            msg = 'close oid=%s, reason=%s, opn=%.4f,' % (
                self.id,
                reason,
                (self.t_open - self.t_init) if self.t_open else 0,
            )
            if self.is_ssl:
                msg += ' rdy=%.4f,' % (
                    (self.t_ready - self.t_init) if self.t_ready else 0,
                )
            msg += ' dat=%.4f, tot=%.4f, rx=%d, tx=%d' % (
                (self.t_http_data - self.t_init) if self.t_http_data else 0,
                now - self.t_init,
                self.rxByteCount,
                self.txByteCount,
            )
            if self.is_ssl:
                msg += ', ssl handshake=%s' % (
                    'success' if self.t_ready else 'fail',
                )
            log.debug(msg)
        self.done(reason)

    def on_failed_handshake(self, reason):
        log.warning('ssl error cid=%s: %s', self.id, reason)

    def on_ready(self):
        self.timer.re_start()
        self.send(**self.context.send)

    def on_data(self, data):
        self.timer.re_start()
        super(ConnectHandler, self).on_data(data)

    def evaluate(self):
        status = self.http_status_code
        result = self.http_content
        if status < 200 or status >= 300:
            return self.done(self.http_status_message if result == '' else result, 1)
        return result

    def on_http_data(self):
        result = self.evaluate()
        if self.is_done:
            return

        if self.context.is_json and result is not None and len(result):
            try:
                result = json.loads(result)
            except Exception as e:
                return self.done(str(e), 1)

        if self.context.wrapper and result is not None:
            result = self.context.wrapper(result)

        self.done(result)

    def on_timeout(self):
        self.done('timeout', 1)


def request(url, callback, content='', headers=None, method='GET', timeout=5.0, close=True, ssl_args=None, compress=False, recv_len=None, event=None):
    ''' make an async http request

        When operating a tcpserver.SERVER, use this method to make async HTTP requests that eventually
        finish with a success or error call to a RequestCallback instance. The timeout feature will not
        work unless TIMERS.service is being called with appropriate frequency.

        Parameters:
            url     : resource url
            callback: a type of RequestCallback to which asynchronous results are reported
            content : http content to send
            headers : dictionary of http headers
            method  : http method
            timeout : max time, in seconds, allowed for network inactivity
            close   : close socket after request complete, boolean
            ssl_args: dict of kwargs for SSLParam
            recv_len: read buffer size (default = BasicHandler.RECV_LEN)
            event   : dictionary of Handler event callback routines

                      on_init(handler)
                      on_open(handler)
                      on_close(handler)
                      on_handshake(handler, cert): bool, True means keep going
                      on_ready(handler)
                      on_http_headers(handler): (rc, result), (0, None) means keep going
                      on_http_send(handler, headers, content)
                      on_data(handler, data)

    '''
    url = _URLParser(url)
    context = _Context(host=url.host, resource=url.resource, callback=callback, content=content, headers=headers, method=method, timeout=timeout, close=close, compress=compress, recv_len=recv_len, event=event)
    if url.is_ssl:
        ssl = SSLParam(**(ssl_args if ssl_args else {}))
    else:
        ssl = None
    SERVER.add_connection((url.address, url.port), _Handler, context, ssl=ssl)


class RequestCallback(object):

    def success(self, handler):
        '''
            called when the request completes
            handler is a type of httphandler.HTTPHandler
        '''
        pass

    def error(self, handler, reason):
        ''' called when there is some kind of problem
            reason is one of:
                failed to connect
                http error
                premature close
                timeout
        '''
        pass


class _Context(object):

    def __init__(self, host, resource, callback, content, headers, method, timeout, close, compress, recv_len, event):

        if headers is None:
            headers = {}
        if headers.get('Content-Type') == 'application/x-www-form-urlencoded' and isinstance(content, types.DictType):
            content = urlencode(content)

        if type(content) in (types.DictType, types.ListType, types.FloatType, types.BooleanType):
            content = json.dumps(content)
            if 'Content-Type' not in headers:
                headers['Content-Type'] = 'application/json'

        self.done = False
        self.host = host
        self.resource = resource
        self.callback = callback
        self.content = content
        self.headers = headers
        self.method = method
        self.timeout = timeout
        self.close = close
        self.compress = compress
        self.recv_len = recv_len
        self.event = {} if event is None else event


class _Handler(HTTPHandler):

    def __init__(self, socket, context):
        context.timer = TIMERS.add(context.timeout * 1000.0, self.on_timeout, onetime=True).start()
        super(_Handler, self).__init__(socket, context)
        if context.recv_len is not None:
            self.RECV_LEN = context.recv_len

    @property
    def callback(self):
        return self.context.callback

    def _error(self, reason):
        if not self.context.done:
            self.callback.error(self, reason)
            self.context.done = True
        self.context.timer.delete()

    def on_timeout(self):
        self._error('timeout')
        self.close()

    def on_init(self):
        e_handler = self.context.event.get('on_init')
        if e_handler:
            e_handler(self)

    def on_open(self):
        self.context.timer.re_start()
        e_handler = self.context.event.get('on_open')
        if e_handler:
            e_handler(self)

    def on_handshake(self, cert):
        self.context.timer.re_start()
        e_handler = self.context.event.get('on_handshake')
        if e_handler:
            return e_handler(self, cert)
        return True

    def on_fail(self):
        self._error('failed to connect')

    def on_http_error(self):
        self._error('http error')

    def on_close(self):
        e_handler = self.context.event.get('on_close')
        if e_handler:
            e_handler(self)
        if not self.context.done:
            self._error('premature close')

    def on_ready(self):
        ctx = self.context
        e_handler = ctx.event.get('on_ready')
        if e_handler:
            e_handler(self)
        self.send(method=ctx.method, host=ctx.host, resource=ctx.resource, headers=ctx.headers, content=ctx.content, close=ctx.close, compress=ctx.compress)

    def on_http_headers(self):
        e_handler = self.context.event.get('on_http_headers')
        if e_handler:
            return e_handler(self)
        return 0, None

    def on_http_send(self, headers, content):
        e_handler = self.context.event.get('on_http_send')
        if e_handler:
            return e_handler(self, headers, content)

    def on_data(self, data):
        self.context.timer.re_start()
        e_handler = self.context.event.get('on_data')
        if e_handler:
            e_handler(self, data)
        super(_Handler, self).on_data(data)

    def on_http_data(self):
        self.context.timer.delete()
        self.callback.success(self)
        self.context.done = True


class _URLParser(object):

    def __init__(self, url):

        u = urlparse(url)
        self.is_ssl = u.scheme == 'https'
        if ':' in u.netloc:
            self.host, self.port = u.netloc.split(':', 1)
            self.port = int(self.port)
        else:
            self.host = u.netloc
            self.port = 443 if self.is_ssl else 80
        self.address = gethostbyname(self.host)
        self.resource = u.path + ('?%s' % u.query if u.query else '')


def run(command, delay=.01, loop=0):
    ''' helper function: loop through SERVER/TIMER until command.is_done is True '''

    while not command.is_done:
        SERVER.service(delay=delay, max_iterations=loop)
        TIMERS.service()


if __name__ == '__main__':

    class command(object):

        def __init__(self):
            self.complete = 0
            request('https://www.google.com', self)
            request('https://www.google.com/?gws_rd=ssl', self)

        @property
        def is_done(self):
            return self.complete == 2

        def error(self, handler, reason):
            self.complete += 1
            print 'error: %s' % reason
            print handler.error
            print handler.http_message

        def success(self, handler):
            self.complete += 1
            print 'worked, rc=%s' % handler.http_status_code
            print handler.http_content

    run(command())
