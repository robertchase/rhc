'''
The MIT License (MIT)

Copyright (c) 2013-2016 Robert H Chase

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
from collections import namedtuple
from importlib import import_module
import traceback
import uuid

from rhc.resthandler import LoggingRESTHandler, RESTMapper
from rhc.tcpsocket import SERVER, SSLParam
from rhc.timer import TIMERS

import logging
log = logging.getLogger(__name__)

'''
    Micro-service launcher

    Use a configuration file (named 'micro' in the current directory) to set up and run a REST
    service.

    The configuration file is composed of single-line directives with parameters that define the
    service. A simple example is this:

        PORT 12345
        ROUTE /ping?
            GET handle.ping

    This will listen on port 12345 for HTTP connections and route a GET on the exact url '/ping'
    to the ping function inside handle.py. The server operates an rhc.resthandler.RESTHandler.

    Directives:

        Directives can be any case and can be preceeded by white space, if desired. Any time a
        '#' is encoutered, it starts a comment, which is ignored.

        CONFIG <path>

            Specifiy the path to an rhc.config implementation. This is needed for the SERVER
            directive.

            If specified, the following configuration parameters control the operation of the
            main loop:

                loop.sleep - max number of milliseconds to sleep on socket poll, default 100
                loop.max_iterations - max polls per service loop, default 100

        SETUP <path>

            Specify the path to a function to be run before entering the main loop.

        TEARDOWN <path>

            Specify the path to a function to be run after exiting the main loop.

        PORT <port>

            Specify a port on which to listen for HTTP connections. In order to to have more
            control over the listening port (for instance, HTTPS) use the SERVER directive.

            Multiple PORT directives can be specified.

        SERVER <name>

            Specify the section of a config file (see CONFIG) that defines a listening port's
            attributes.

            The following config attributes can be specified:

                port - port to listen on, required
                is_active - flag that enables/disables port, default=True
                handler - path to socket handler, default=rhc.micro.MicroRESTHandler
                          extend this handler, or one of the rhc.resthandlers for best results

                ssl.is_active - flag that enables/disables ssl, default=False
                ssl.keyfile - path to ssl keyfile
                ssl.certfile - path to ssl certfile

                http_max_content_length - self explanatory, default None (no enforced limit)
                http_max_line_length - max header line length, default 10000 bytes
                http_max_header_count - self explanatory, default 100
                hide_stack_trace - don't send stack trace to caller, default True

            Multiple SERVER directives can be specified.

        ROUTE <pattern>

           Specify a url pattern. This follows the rules of rhc.resthandler.RESTMapper.

        GET <path>
        POST <path>
        PUT <path>
        DELETE <path>

            Specify the path to a function to handle an HTTP method.
'''


def _import(item_path, is_module=False):
    if is_module:
        return import_module(item_path)
    path, function = item_path.rsplit('.', 1)
    module = import_module(path)
    return getattr(module, function)


class MicroContext(object):

    def __init__(self, http_max_content_length, http_max_line_length, http_max_header_count, hide_stack_trace):
        self.http_max_content_length = http_max_content_length
        self.http_max_line_length = http_max_line_length
        self.http_max_header_count = http_max_header_count
        self.hide_stack_trace = hide_stack_trace


class MicroRESTHandler(LoggingRESTHandler):

    def __init__(self, socket, context):
        super(MicroRESTHandler, self).__init__(socket, context)
        context = context.context
        self.http_max_content_length = context.http_max_content_length
        self.http_max_line_length = context.http_max_line_length
        self.http_max_header_count = context.http_max_header_count
        self.hide_stack_trace = context.hide_stack_trace

    def on_rest_exception(self, exception_type, value, trace):
        code = uuid.uuid4().hex
        log.exception('exception encountered, code: %s', code)
        if self.hide_stack_trace:
            return 'oh, no! something broke. sorry about that.\nplease report this problem using the following id: %s\n' % code
        return traceback.format_exc(trace)


class Route(object):

    def __init__(self, pattern):
        self.pattern = pattern
        self.method = dict()

    def add(self, method, path):
        self.method[method] = _import(path)


class Server(object):

    def __init__(self, name, config):
        self.name = name
        context = MicroContext(
            config.http_max_content_length if hasattr(config, 'http_max_content_length') else None,
            config.http_max_line_length if hasattr(config, 'http_max_line_length') else 10000,
            config.http_max_header_count if hasattr(config, 'http_max_header_count') else 100,
            config.hide_stack_trace if hasattr(config, 'hide_stack_trace') else True,
        )
        self.mapper = RESTMapper(context)
        self.is_active = config.is_active if hasattr(config, 'is_active') else True
        self.port = int(config.port)
        self.handler = _import(config.handler, is_module=True) if hasattr(config, 'handler') else MicroRESTHandler
        self.ssl = None
        if hasattr(config, 'ssl') and config.ssl.is_active:
            self.ssl = SSLParam(
                server_side=True,
                keyfile=config.ssl.keyfile,
                certfile=config.ssl.certfile,
            )

    def add_route(self, pattern):
        if hasattr(self, 'route'):
            self.mapper.add(self.route.pattern, **self.route.method)
        self.route = Route(pattern)

    def add_method(self, method, path):
        self.route.add(method, path)

    def done(self):
        if self.is_active:
            if hasattr(self, 'route'):
                self.mapper.add(self.route.pattern, **self.route.method)
            try:
                SERVER.add_server(self.port, self.handler, self.mapper, ssl=self.ssl)
            except Exception:
                log.error('unable to add %s server on port %d', self.name, self.port)
                raise
            log.info('listening on %s port %d', self.name, self.port)


class FSM(object):

    def __init__(self):
        self.state = self.state_init
        self.teardown = lambda *x: None

    def handle(self, event, data, linenum):
        self.data = data
        try:
            self.state(event)
        except Exception as e:
            raise Exception('%s, line=%d' % (e, linenum))

    def state_init(self, event):
        if event == 'config':
            self.config = _import(self.data)
        elif event == 'setup':
            _import(self.data)()
        elif event == 'teardown':
            self.teardown = _import(self.data)
        elif event == 'server':
            self.server = Server(self.data, getattr(self.config, self.data))
            self.state = self.state_server
        elif event == 'port':
            self.server = Server('default', namedtuple('config', 'port')(int(self.data)))
            self.state = self.state_server
        elif event == 'done':
            self.state = self.state_done
        else:
            raise Exception('invalid record ' + event)

    def state_server(self, event):
        if event == 'route':
            self.server.add_route(self.data)
            self.state = self.state_route
        elif event == 'done':
            self.server.done()
            self.state = self.state_done
        else:
            raise Exception('invalid record ' + event)

    def state_route(self, event):
        if event in ('get', 'post', 'put', 'delete'):
            self.server.add_method(event, self.data)
        elif event == 'route':
            self.server.add_route(self.data)
        elif event == 'server':
            self.server.done()
            self.server = Server(self.data, getattr(self.config, self.data))
            self.state = self.state_server
        elif event == 'port':
            self.server.done()
            self.server = Server('default', namedtuple('config', 'port')(int(self.data)))
            self.state = self.state_server
        elif event == 'done':
            self.server.done()
            self.state = self.state_done
        else:
            raise Exception('invalid record ' + event)

    def state_done(self, event):
        raise Exception('unexpected event ' + event)


def parse(s):

    fsm = FSM()

    for lnum, l in enumerate(s.readlines(), start=1):
        l = l.split('#', 1)[0].strip()
        if not l:
            continue
        try:
            n, v = l.split(' ', 1)
            n = n.lower()
        except ValueError as e:
            log.warning('parse error on line %d: %s', lnum, e.message)
            raise
        fsm.handle(n, v, lnum)
    fsm.handle('done', None, lnum + 1)

    sleep = 100
    max_iterations = 100
    if hasattr(fsm, 'config'):
        if hasattr(fsm.config, 'loop'):
            sleep = fsm.config.loop.sleep
            max_iterations = fsm.config.loop.max_iterations

    return namedtuple('control', 'sleep, max_iterations, teardown')(sleep, max_iterations, fsm.teardown)


def run(sleep, max_iterations):
    while True:
        try:
            SERVER.service(delay=sleep/1000.0, max_iterations=max_iterations)
            TIMERS.service()
        except KeyboardInterrupt:
            log.info('Received shutdown command from keyboard')
            break
        except Exception:
            log.exception('exception encountered')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    control = parse(open('micro'))

    run(control.sleep, control.max_iterations)
    control.teardown()
