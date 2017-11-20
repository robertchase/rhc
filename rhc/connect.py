import json
from socket import gethostbyname
import time
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
            query=None,
            method='GET',
            body=None,
            headers=None,
            is_json=True,
            is_form=False,
            timeout=5.0,
            wrapper=None,
            handler=None,
            evaluate=None,
            debug=False,
            trace=False,
            **kwargs
        ):
    """ Make an async http connection, executing callback on completion

        Parameters:

            callback - a callable expecting (rc, result), where rc=0 on success
            url      - full url of the resource being referenced
                       can include query string
            query    - optional query string
                       if dict, urlencoded to string
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
            debug    - log debug messages on start/open/close
            trace    - log debug sent and recv'd http data
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
    if query is not None:
        if isinstance(query, dict):
            query = urlencode(query)
        url = '{}?{}'.format(url, query)
    p = URLParser(url)
    return connect_parsed(callback, url, p.host, p.address, p.port, p.path,
                          p.query, p.is_ssl, method, headers, body, is_json,
                          is_form, timeout, wrapper, handler, evaluate, debug,
                          trace, **kwargs)


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
            debug,
            trace,
            **kwargs
        ):
    c = ConnectContext(callback, url, method, path, query, host, headers, body,
                       is_json, is_form, timeout, wrapper, evaluate, debug,
                       trace, kwargs)
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
                is_debug,
                is_trace,
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
        self.is_debug = is_debug
        self.is_trace = is_trace
        self.kwargs = kwargs


class ConnectHandler(HTTPHandler):
    """ Manage outgoing http request as defined by context """

    def on_init(self):
        self.is_done = False
        self.is_timeout = False
        self.setup()
        self.check_kwargs()

    def check_kwargs(self):
        """ Check additional keyword args

            In a ConnectHandler subclass, additional keyword arguments can be
            handled by overriding this method.

            The default behavior is to accept none.
        """
        kwargs = self.context.kwargs
        if len(kwargs) > 0:
            raise TypeError(
                'connect() received unexpected keyword argument(s): %s' %
                str(tuple(kwargs.keys()))
            )

    def after_init(self):
        if self.context.is_debug:
            log.debug(
                'starting outbound connection, oid=%s: %s %s',
                self.id,
                self.context.method,
                self.context.url + self.context.path
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
            if self.is_ssl():
                msg += ' rdy=%.4f,' % (
                    (self.t_ready - self.t_init) if self.t_ready else 0,
                )
            msg += ' dat=%.4f, tot=%.4f, rx=%d, tx=%d' % (
                (self.t_http_data - self.t_init) if self.t_http_data else 0,
                now - self.t_init,
                self.rxByteCount,
                self.txByteCount,
            )
            if self.is_ssl():
                msg += ', ssl handshake=%s' % (
                    'success' if self.t_ready else 'fail',
                )
            log.debug(msg)
        self.done(reason)

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

        if self.context.is_trace:
            log.debug('recv: %s', self.http_message)

        try:
            evaluate = self.context.evaluate or self.__class__.evaluate
            result = evaluate(self)
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

    def on_http_send(self, headers, content):
        if self.context.is_trace:
            log.debug('send: %s', headers)
            if len(content):
                log.debug('send: %s', content)


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
