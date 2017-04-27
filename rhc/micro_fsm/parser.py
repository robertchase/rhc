import imp
import os

import rhc.config as config_file
from rhc.micro_fsm.fsm_micro import create as create_machine

import logging
log = logging.getLogger(__name__)


def to_args(line):
    args = []
    kwargs = {}
    for tok in line.split():
        if '=' in tok:
            n, v = tok.split('=', 1)
            kwargs[n] = v
        else:
            args.append(tok)
    return args, kwargs


def _prepare_import(import_fname):
    if '.' in import_fname and os.path.sep not in import_fname:  # path is dot separated
        parts = import_fname.split('.')
        extension = ''
        if parts[-1] == 'micro':
            parts = parts[:-1]  # save '.micro' extension if exists
            extension = '.micro'
        sink, path, sink = imp.find_module(parts[0])  # use module-based location
        import_fname = os.path.join(path, *parts[1:]) + extension
    elif not import_fname.startswith(os.path.sep):  # path is relative
        import_fname = os.path.join(os.getcwd(), import_fname)
    return import_fname


def load(micro='micro', files=None, lines=None):

    if files is None:
        files = []
    if lines is None:
        lines = []

    if isinstance(micro, str):
        if micro in files:
            raise Exception('a micro file (in this case, %s) cannot be recursively imported' % micro)
        files.append(micro)
        micro = open(micro).readlines()
    elif isinstance(micro, list):
        files.append('dict')
    else:
        raise Exception('Invalid micro file type %s' % type(micro))

    fname = files[-1]

    for num, line in enumerate(micro, start=1):
        line = line.split('#', 1)[0].strip()
        if len(line):
            line = line.split(' ', 1)
            if len(line) == 1:
                raise Exception('too few tokens, file=%s, line=%d' % (fname, num))
            if line[0].lower() == 'import':
                import_fname = _prepare_import(line[1])
                load(import_fname, files, lines)
            else:
                lines.append((fname, num, line[0], line[1]))
    return lines


class Parser(object):

    def __init__(self):
        self.fsm = create_machine(
            add_config=self.act_add_config,
            add_config_server=self.act_add_config_server,
            add_connection=self.act_add_connection,
            add_header=self.act_add_header,
            add_method=self.act_add_method,
            add_old_server=self.act_add_old_server,
            add_optional=self.act_add_optional,
            add_required=self.act_add_required,
            add_resource=self.act_add_resource,
            add_route=self.act_add_route,
            add_server=self.act_add_server,
            add_setup=self.act_add_setup,
            add_teardown=self.act_add_teardown,
        )
        self.error = None
        self.fsm.state = 'init'
        self.config = config_file.Config()
        self.setup = None
        self.teardown = None
        self.connections = {}
        self._config_servers = {}
        self.servers = {}

    @property
    def is_new(self):
        return len(self._config_servers) == 0

    @classmethod
    def parse(cls, micro='micro'):
        parser = cls()
        for fname, num, parser.event, parser.line in load(micro):
            parser.args, parser.kwargs = to_args(parser.line)
            if not parser.fsm.handle(parser.event.lower()):
                raise Exception("Unexpected directive '%s', file=%s, line=%d" % (parser.event, fname, num))
            if parser.error:
                raise Exception('%s, line=%d' % (parser.error, num))
        return parser

    def _add_config(self, name, **kwargs):
        self.config._define(name, **kwargs)

    def act_add_config(self):
        if self.kwargs.get('validate') is not None:
            try:
                self.kwargs['validate'] = {
                    'int': config_file.validate_int,
                    'bool': config_file.validate_bool,
                    'file': config_file.validate_file,
                }[self.kwargs['validate']]
            except KeyError:
                raise Exception("validate must be one of 'int', 'bool', 'file'")
        config = Config(*self.args, **self.kwargs)
        self._add_config(config.name, **config.kwargs)

    def act_add_config_server(self):
        name, port = self.args
        self._config_servers[name] = port

    def act_add_connection(self):
        connection = Connection(*self.args, **self.kwargs)
        if connection.name in self.connections:
            self.error = 'duplicate CONNECTION name: %s' % connection.name
        else:
            self.connections[connection.name] = connection
            self.connection = connection
            self._add_config('connection.%s.url' % connection.name, value=connection.url)
            self._add_config('connection.%s.is_active' % connection.name, value=True, validator=config_file.validate_bool)
            self._add_config('connection.%s.is_debug' % connection.name, value=connection.is_debug, validator=config_file.validate_bool)
            self._add_config('connection.%s.timeout' % connection.name, value=connection.timeout, validator=float)

    def act_add_header(self):
        header = Header(*self.args, **self.kwargs)
        if header.key in self.connection.headers:
            self.error = 'duplicate connection header: %s' % header.key
        elif header.default is None and header.config is None and header.code is None:
            self.error = 'header must have a default, config or code setting: %s' % header.key
        else:
            self.connection.add_header(header)
            if header.config:
                self._add_config('connection.%s.header.%s' % (self.connection.name, header.config), value=header.default)

    def act_add_method(self):
        self.server.add_method(Method(self.event, *self.args, **self.kwargs))

    def act_add_required(self):
        self.connection.add_required(*self.args, **self.kwargs)

    def act_add_optional(self):
        optional = Optional(*self.args, **self.kwargs)
        resource = self.connection.add_optional(optional)
        if optional.config:
            self._add_config('connection.%s.resource.%s.%s' % (self.connection.name, resource.name, optional.config), value=optional.default)

    def act_add_resource(self):
        resource = Resource(*self.args, **self.kwargs)
        if resource.name in self.connection:
            self.error = 'duplicate connection resource: %s' % resource.name
        else:
            self.connection.add_resource(resource)
            self._add_config(
                'connection.%s.resource.%s.is_debug' % (self.connection.name, resource.name),
                value=config_file.validate_bool(resource.is_debug) if resource.is_debug is not None else None,
                validator=config_file.validate_bool,
            )

    def act_add_route(self):
        self.server.add_route(Route(*self.args, **self.kwargs))

    def act_add_server(self):
        server = Server(*self.args, **self.kwargs)
        if server.port in self.servers:
            self.error = 'duplicate SERVER port: %s' % server.port
        else:
            self.servers[server.port] = server
            self.server = server
            self._add_config('server.%s.port' % server.name, value=server.port, validator=config_file.validate_int)
            self._add_config('server.%s.is_active' % server.name, value=True, validator=config_file.validate_bool)
            self._add_config('server.%s.ssl.is_active' % server.name, value=False, validator=config_file.validate_bool)
            self._add_config('server.%s.ssl.keyfile' % server.name, validator=config_file.validate_file)
            self._add_config('server.%s.ssl.certfile' % server.name, validator=config_file.validate_file)

    def act_add_old_server(self):
        name = self.args[0]
        server = Server(name, self._config_servers.get(name), **self.kwargs)
        if server.port in self.servers:
            self.error = 'duplicate SERVER port: %s' % server.port
        else:
            self.servers[server.port] = server
            self.server = server
            self._add_config('%s.port' % server.name, value=server.port, validator=config_file.validate_int)
            self._add_config('%s.is_active' % server.name, value=True, validator=config_file.validate_bool)
            self._add_config('%s.ssl.is_active' % server.name, value=False, validator=config_file.validate_bool)
            self._add_config('%s.ssl.keyfile' % server.name, validator=config_file.validate_file)
            self._add_config('%s.ssl.certfile' % server.name, validator=config_file.validate_file)

    def act_add_setup(self):
        if len(self.args) > 1:
            raise Exception('too many tokens specified')
        self.setup = self.args[0]

    def act_add_teardown(self):
        if len(self.args) > 1:
            raise Exception('too many tokens specified')
        self.teardown = self.args[0]


class Config(object):

    def __init__(self, name, default=None, validate=None, env=None):
        self.name = name
        self.default = default
        self.validate = validate
        self.env = env

    @property
    def kwargs(self):
        return {'value': self.default, 'validator': self.validate, 'env': self.env}


class Server(object):

    def __init__(self, name, port):
        self.name = name
        self.port = int(port)
        self.routes = []

    def __repr__(self):
        return 'Server[name=%s, port=%s, routes=%s]' % (self.name, self.port, self.routes)

    def add_route(self, route):
        self.routes.append(route)
        self.route = route

    def add_method(self, method):
        self.route.methods[method.method] = method.path


class Route(object):

    def __init__(self, pattern):
        self.pattern = pattern
        self.methods = {}

    def __repr__(self):
        return 'Route[pattern=%s, methods=%s]' % (self.pattern, self.methods)


class Method(object):

    def __init__(self, method, path):
        self.method = method.lower()
        self.path = path

    def __repr__(self):
        return 'Method[method=%s, path=%s]' % (self.method, self.path)


class Connection(object):

    def __init__(self, name, url, is_json=True, is_debug=False, timeout=5.0, handler=None, wrapper=None, setup=None):
        self.name = name
        self.url = url
        self.is_json = config_file.validate_bool(is_json)
        self.is_debug = config_file.validate_bool(is_debug)
        self.timeout = float(timeout)
        self.handler = handler
        self.wrapper = wrapper
        self.setup = setup

        self.headers = {}
        self.resources = {}
        self._resource = None

    def __repr__(self):
        return 'Connection[name=%s, url=%s, hdr=%s, res=%s]' % (self.name, self.url, self.headers, self.resources)

    def __contains__(self, name):
        return name in self.resources

    def add_header(self, header):
        self.headers[header.key] = header

    def add_resource(self, resource):
        self._resource = resource
        self.resources[resource.name] = resource

    def add_required(self, parameter_name):
        self._resource.add_required(parameter_name)

    def add_optional(self, optional):
        self._resource.add_optional(optional)
        return self._resource


class Header(object):

    def __init__(self, key, default=None, config=None, code=None):
        self.key = key
        self.default = default
        self.config = config
        self.code = code

    def __repr__(self):
        return 'Header[key=%s, dft=%s, cfg=%s, cod=%s]' % (self.key, self.default, self.config, self.code)


class Resource(object):

    def __init__(self, name, path, method='GET', is_json=None, is_debug=None, trace=None, timeout=None, handler=None, wrapper=None, setup=None):
        self.name = name
        self.path = path
        self.method = method
        self.is_json = config_file.validate_bool(is_json) if is_json is not None else None
        self.is_debug = config_file.validate_bool(is_debug) if is_debug is not None else None
        self.trace = config_file.validate_bool(trace) if trace is not None else None
        self.timeout = float(timeout) if timeout is not None else None
        self.handler = handler
        self.wrapper = wrapper
        self.setup = setup

        self.required = []
        self.optional = {}

    def __repr__(self):
        return 'Resource[name=%s, url=%s, req=%s, opt=%s' % (self.name, self.path, self.required, self.optional)

    def add_required(self, parameter_name):
        self.required.append(parameter_name)

    def add_optional(self, optional):
        self.optional[optional.name] = optional


class Optional(object):

    def __init__(self, name, default=None, config=None):
        self.name = name
        self.default = default
        self.config = config

    def __repr__(self):
        return 'Optional[name=%s, dft=%s, cfg=%s]' % (self.name, self.default, self.config)


if __name__ == '__main__':
    import argparse
    import logging
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(
        description='parse a micro file',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('--config', default='config', help='configuration file')
    parser.add_argument('--no-config', dest='no_config', default=False, action='store_true', help="don't use a config file")
    parser.add_argument('--micro', default='micro', help='micro description file')
    parser.add_argument('-c', '--config-only', dest='config_only', action='store_true', default=False, help='parse micro and config files and display config values')
    args = parser.parse_args()

    parser = Parser.parse()
    # print parser.servers
    # print parser.connections
    print parser.config
    print('setup', parser.setup)
    print('teardown', parser.teardown)
    '''
    micro.load(micro=args.micro, config=args.config if args.no_config is False else None)

    if args.config_only:
        print(micro.config)
    else:
        micro.start()
        while True:
            try:
                micro.service()
            except KeyboardInterrupt:
                log.info('Received shutdown command from keyboard')
                break
            except Exception:
                log.exception('exception encountered')
    '''
