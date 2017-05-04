from importlib import import_module
import logging
import uuid

import rhc.async as async
from rhc.connections import connection
import rhc.file_util as file_util
from rhc.micro_fsm.parser import Parser as parser
from rhc.resthandler import LoggingRESTHandler, RESTMapper
from rhc.tcpsocket import SERVER
from rhc.timer import TIMERS


log = logging.getLogger(__name__)


class MicroContext(object):

    def __init__(self, http_max_content_length, http_max_line_length, http_max_header_count):
        self.http_max_content_length = http_max_content_length
        self.http_max_line_length = http_max_line_length
        self.http_max_header_count = http_max_header_count


class MicroRESTHandler(LoggingRESTHandler):

    def __init__(self, socket, context):
        super(MicroRESTHandler, self).__init__(socket, context)
        context = context.context
        self.http_max_content_length = context.http_max_content_length
        self.http_max_line_length = context.http_max_line_length
        self.http_max_header_count = context.http_max_header_count

    def on_rest_exception(self, exception_type, value, trace):
        code = uuid.uuid4().hex
        log.exception('exception encountered, code: %s', code)
        return 'oh, no! something broke. sorry about that.\nplease report this problem using the following id: %s\n' % code


def _import(item_path, is_module=False):
    if is_module:
        return import_module(item_path)
    path, function = item_path.rsplit('.', 1)
    module = import_module(path)
    return getattr(module, function)


def _load(filename):
    if isinstance(filename, str):
        filename = file_util.normalize_path(filename, filetype='micro')
    p = parser.parse(filename)
    return p


def load_server(filename):
    p = _load(filename)
    SERVER.close()
    setup_servers(p.config, p.servers, p.is_new)
    return p


def load_connection(filename):
    p = _load(filename)
    setup_connections(p.config, p.connections)
    return p


def re_start(p):
    SERVER.close()
    setup_servers(p.config, p.servers, p.is_new)


def load_config():
    p = parser.parse()
    p.config_load()
    return p.config


def setup_servers(config, servers, is_new):
    for server in servers.values():
        if is_new:
            conf = config._get('server.%s' % server.name)
        else:
            conf = config._get('%s' % server.name)
        if conf.is_active is False:
            continue
        context = MicroContext(
            conf.http_max_content_length if hasattr(conf, 'http_max_content_length') else None,
            conf.http_max_line_length if hasattr(conf, 'http_max_line_length') else 10000,
            conf.http_max_header_count if hasattr(conf, 'http_max_header_count') else 100,
        )
        mapper = RESTMapper(context)
        for route in server.routes:
            methods = {}
            for method, path in route.methods.items():
                methods[method] = _import(path)
            mapper.add(route.pattern, **methods)
        handler = _import(conf.handler, is_module=True) if hasattr(conf, 'handler') else MicroRESTHandler
        SERVER.add_server(
            conf.port,
            handler,
            mapper,
            conf.ssl.is_active,
            conf.ssl.certfile,
            conf.ssl.keyfile,
        )
        log.info('listening on %s port %d', server.name, conf.port)


def setup_connections(config, connections):
    for c in connections.values():
        conf = config._get('connection.%s' % c.name)
        headers = {}
        for header in c.headers.values():
            headers[header.key] = config._get('connection.%s.header.%s' % (c.name, header.config)) if header.config else _import(header.code) if header.code else header.default
        conn = async.Connection(
           conf.url,
           c.is_json,
           conf.is_debug,
           conf.timeout,
           _import(c.wrapper) if c.wrapper else None,
           _import(c.handler) if c.handler else None,
           _import(c.setup) if c.setup else None,
           headers,
        )
        for resource in c.resources.values():
            optional = {}
            for option in resource.optional.values():
                optional[option.name] = config._get('connection.%s.resource.%s.%s' % (c.name, resource.name, option.config)) if option.config else option.default
            conn.add_resource(
                resource.name,
                resource.path,
                resource.method,
                resource.required,
                optional,
                None,
                resource.is_json,
                resource.is_debug,
                resource.trace,
                resource.timeout,
                _import(resource.handler) if resource.handler else None,
                _import(resource.wrapper) if resource.wrapper else None,
                _import(resource.setup) if resource.setup else None,
            )
        setattr(connection, c.name, conn)


def start(config, setup):
    if setup:
        _import(setup)(config)


def run(sleep=100, max_iterations=100):
    while True:
        try:
            SERVER.service(delay=sleep/1000.0, max_iterations=max_iterations)
            TIMERS.service()
        except KeyboardInterrupt:
            log.info('Received shutdown command from keyboard')
            break
        except Exception:
            log.exception('exception encountered')


def stop(teardown):
    if teardown:
        _import(teardown)()


def launch(micro):
    p = parser.parse(micro)
    setup_servers(p.config, p.servers)
    setup_connections(p.config, p.connections)
    run()


if __name__ == '__main__':
    import argparse
    import logging

    logging.basicConfig(level=logging.DEBUG)

    aparser = argparse.ArgumentParser(
        description='start a micro service',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    aparser.add_argument('--config', default='config', help='configuration file')
    aparser.add_argument('--no-config', dest='no_config', default=False, action='store_true', help="don't use a config file")
    aparser.add_argument('--micro', default='micro', help='micro description file')
    aparser.add_argument('-c', '--config-only', dest='config_only', action='store_true', default=False, help='parse micro and config files and display config values')

    aparser.add_argument('-v', '--verbose', action='store_true', default=False, help='display debug level messages')
    aparser.add_argument('-s', '--stdout', action='store_true', default=False, help='display messages to stdout')
    args = aparser.parse_args()

    p = parser.parse(args.micro)
    if args.no_config is False:
        p.config._load(args.config)
    if args.config_only is True:
        print p.config
    else:
        setup_servers(p.config, p.servers, p.is_new)
        if p.is_new:
            setup_connections(p.config, p.connections)
        start(p.config, p.setup)
        run()
        stop(p.teardown)
