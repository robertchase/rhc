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
import json
import types

from socket import gethostbyname
from urlparse import urlparse

from httphandler import HTTPHandler
from tcpsocket import SERVER, SSLParam
from timer import TIMERS


def request(url, callback, content='', headers=None, method='GET', timeout=5.0, close=True, recv_len=None, event=None):
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
            recv_len: read buffer size (default = BasicHandler.RECV_LEN)
            event   : dictionary of Handler event callback routines

                      on_open(handler)
                      on_close(handler)
                      on_handshake(handler, cert): bool, True means keep going
                      on_ready(handler)
                      on_http_headers(handler): (rc, result), (0, None) means keep going
                      on_http_send(handler, headers, content)
                      on_data(handler, data)

    '''
    url = _URLParser(url)
    context = _Context(host=url.host, resource=url.resource, callback=callback, content=content, headers=headers, method=method, timeout=timeout, close=close, recv_len=recv_len, event=event)
    ssl = SSLParam() if url.is_ssl else None
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

    def __init__(self, host, resource, callback, content, headers, method, timeout, close, recv_len, event):

        if type(content) in (types.DictType, types.ListType, types.FloatType, types.BooleanType):
            content = json.dumps(content)
            if headers is None:
                headers = {}
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
        self.send(method=ctx.method, host=ctx.host, resource=ctx.resource, headers=ctx.headers, content=ctx.content, close=ctx.close)

    def on_http_headers(self):
        e_handler = self.context.event.get('on_http_headers')
        if e_handler:
            return e_handler(self)
        return 0, None

    def on_http_send(self, headers, content):
        e_handler = self.context.event.get('on_http_handler')
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


if __name__ == '__main__':

    class MyCallback(RequestCallback):

        def __init__(self):
            self.complete = 0

        def error(self, handler, reason):
            self.complete += 1
            print 'error: %s' % reason
            print handler.error
            print handler.http_message

        def success(self, handler):
            self.complete += 1
            print 'worked, rc=%s' % handler.http_status_code
            print handler.http_content

    callback = MyCallback()

    request('https://www.google.com', callback)
    request('https://www.google.com/?gws_rd=ssl', callback)

    while callback.complete != 2:
        SERVER.service(1)
        TIMERS.service()
        print 'tick...'
