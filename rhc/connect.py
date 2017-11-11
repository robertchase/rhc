import json
from socket import gethostbyname
from urllib import urlencode
import urlparse

from rhc.httphandler import HTTPHandler
from rhc.tcpsocket import SERVER
from rhc.timer import TIMERS


import logging
log = logging.getLogger(__name__)


def connect(
            callback,
            url,
            method='GET',
            body=None,
            headers=None,
            is_json=True,
            is_form=False,
            timeout=5.0,
            wrapper=None,
            handler=None,
            evaluate=None,
            **kwargs
        ):
    """ Make an async http connection, executing callback on completion

        Parameters:

            callback - a callable expecting (rc, result), where rc=0 on success
            url      - full url of the resource being referenced
            method   - http method (default=GET)
            body     - http content (default=None) (see Note 1)
            headers  - http headers as dict (default=None)
            is_json  - if True, successful result is json.loads-ed
                       (default=True)
            is_form  - send content as applicaton/x-www-form-urlencoded
            timeout  - tolerable period of network inactivity in seconds
                       (default=5.0)
                       on timeout, callback is invoked with (1, 'timeout')
            wrapper  - callable for wrapping successful result
                       called with result before callback
                       (default=None)
            handler  - handler class for connection (default=None)
                       subclass of ConnectHandler
            evaluate - callable for http response evaluation (default=None)
                       returns result or raises Exception
                       (see ConnectHandler.evaluate)
            kwargs   - additional keyword args that might be useful in a
                       ConnectHandler subclass

        Return:

            ConnectHandler instance (See Note 2)

        Notes:

            1. If body is a dict and method is GET, then the contents of dict
               are added to the query string and body is cleared.

            2. The returned ConnectHandler object has an is_done attribute
               which will remain False until the connect operation is complete
               (success or failure); this allows sync operation using
               connect.run. Typically, completion is indicated through use
               of the callback.

    """
    p = URLParser(url)
    return connect_parsed(callback, url, p.host, p.address, p.port, p.path,
                          p.query, p.is_ssl, method, headers, body, is_json,
                          is_form, timeout, wrapper, handler, evaluate,
                          **kwargs)


def connect_parsed(
            callback,
            url,
            host,
            address,
            port,
            path,
            query,
            is_ssl,
            method,
            headers,
            body,
            is_json,
            is_form,
            timeout,
            wrapper,
            handler,
            evaluate,
            **kwargs
        ):
    c = ConnectContext(callback, url, method, path, query, host, headers, body,
                       is_json, is_form, timeout, wrapper, evaluate, kwargs)
    return SERVER.add_connection((address, port), handler or ConnectHandler,
                                 context=c, ssl=is_ssl)


class ConnectContext(object):

    def __init__(
                self,
                callback,
                url,
                method,
                path,
                query,
                host,
                headers,
                body,
                is_json,
                is_form,
                timeout,
                wrapper,
                evaluate,
                kwargs
            ):
        self.callback = callback
        self.url = url
        self.method = method
        self.path = path
        self.query = query
        self.host = host
        self.headers = headers
        self.body = body
        self.is_json = is_json
        self.is_form = is_form
        self.is_verbose = False
        self.timeout = timeout
        self.wrapper = wrapper
        self.evaluate = evaluate
        self.kwargs = kwargs


class ConnectHandler(HTTPHandler):
    """ Manage outgoing http request as defined by context """

    def on_init(self):
        self.is_done = False
        self.is_timeout = False
        self.setup()
        self.after_init()

    def after_init(self):
        kwargs = self.context.kwargs
        if len(kwargs) > 0:
            raise TypeError(
                'connect() received unexpected keyword argument(s): %s' %
                str(tuple(kwargs.keys()))
            )

    def _form(self, context):
        if context.is_form:
            if not context.headers:
                context.headers = {}
            context.headers['Content-Type'] = \
                'application/x-www-form-urlencoded'

    def setup(self):
        context = self.context

        self._form(context)

        if isinstance(context.body, dict):
            context_type = None
            if context.headers:
                context_type = context.headers.get('Content-Type')

            if context_type == 'application/x-www-form-urlencoded':
                context.body = urlencode(context.body)
            elif context.method == 'GET':
                query = urlparse.parse_qs(context.query)
                query.update(context.body)
                context.query = urlencode(context.body)
                context.body = None

        if context.path == '':
            context.path = '/'

        if context.query:
            context.path = context.path + '?' + context.query

        if isinstance(context.body, (dict, list, tuple, float, bool, int)):
            try:
                context.body = json.dumps(context.body)
            except Exception:
                context.body = str(context.body)
            else:
                if context.headers is None:
                    context.headers = {}
                context.headers['Content-Type'] = \
                    'application/json; charset=utf-8'

        if context.body is None:
            context.body = ''
        self.timer = TIMERS.add(self.on_timeout, self.context.timeout * 1000)
        self.timer.start()

    def done(self, result, rc=0):
        if self.is_done:
            return
        self.is_done = True
        self.timer.cancel()
        self.context.callback(rc, result)
        self.close('transaction complete')

    def on_close(self):
        self.done(None)

    def on_failed_handshake(self, reason):
        log.warning('ssl error cid=%s: %s', self.id, reason)
        self.done(reason, 1)

    def on_ready(self):
        """' send http request to peer using values from context """
        self.timer.re_start()
        context = self.context
        self.send(
            method=context.method,
            host=context.host,
            resource=context.path,
            headers=context.headers,
            content=context.body,
            close=True,
        )

    def on_data(self, data):
        self.timer.re_start()
        super(ConnectHandler, self).on_data(data)

    def evaluate(self):
        """ evaluate http response document

            examines http status code, raising an Exception if not in
            the 200-299 range.

            Return:

                if method is HEAD, http_headers
                otherwise http_content

            Notes:

                1. can be overridden by a subclass, or by specifying the
                   evaluate argument to the connect function.
        """
        if self.context.method == 'HEAD':
            result = self.http_headers
        else:
            result = self.http_content
        status = self.http_status_code
        if status < 200 or status > 299:
            raise Exception(result or self.http_status_message)
        return result

    def on_http_data(self):

        try:
            evaluate = self.context.evaluate or self.evaluate
            result = evaluate()
        except Exception as e:
            return self.done(str(e), 1)

        if self.context.is_json and result is not None and len(result):
            try:
                result = json.loads(result)
            except Exception as e:
                return self.done(str(e), 1)

        if self.context.wrapper and result is not None:
            try:
                result = self.context.wrapper(result)
            except Exception as e:
                self.done(str(e), 1)

        self.done(result)

    def on_fail(self):
        self.done(self.close_reason, 1)

    def on_http_error(self):
        self.done('http error', 1)

    def on_timeout(self):
        self.is_timeout = True
        self.done('timeout', 1)


def run(command, delay=.01, loop=0):
    """ service SERVER/TIMER until command.is_done is True """
    while not command.is_done:
        SERVER.service(delay=delay, max_iterations=loop)
        TIMERS.service()


class URLParser(object):
    """ parse a url into components

        the following object attributes are set:

            self.is_ssl   - True if scheme is https
            self.host
            self.port     - if not supplied, 80 or http, 443 for https
            self.address  - ip address of host
            self.path
            self.query
            self.resource - path?query
    """
    def __init__(self, url):
        u = urlparse.urlparse(url)
        self.is_ssl = u.scheme == 'https'
        if ':' in u.netloc:
            self.host, self.port = u.netloc.split(':', 1)
            self.port = int(self.port)
        else:
            self.host = u.netloc
            self.port = 443 if self.is_ssl else 80
        self.address = gethostbyname(self.host)
        self.resource = u.path + ('?%s' % u.query if u.query else '')
        self.path = u.path
        self.query = u.query
