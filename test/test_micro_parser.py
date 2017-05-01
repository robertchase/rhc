from rhc.micro_fsm.parser import Parser


def test_server():
    p = Parser.parse(['SERVER test 12345'])
    assert p
    assert len(p.servers) == 1
    assert p.servers[12345].name == 'test'

    config = p.config.server.test
    assert config.port == 12345
    assert config.is_active is True
    assert config.ssl.is_active is False
    assert config.ssl.keyfile is None
    assert config.ssl.certfile is None


def test_route():
    p = Parser.parse([
        'SERVER test 12345',
        'ROUTE /foo/bar$',
    ])
    s = p.servers[12345]
    assert len(s.routes) == 1
    r = s.routes[0]
    assert r.pattern == '/foo/bar$'


def test_crud():
    p = Parser.parse([
        'SERVER test 12345',
        'ROUTE /foo/bar$',
        'GET a',
        'PUT a.b',
        'POST a.b.c',
        'DELETE a.b.c.d',
    ])
    s = p.servers[12345]
    r = s.routes[0]
    assert r.methods['get'] == 'a'
    assert r.methods['put'] == 'a.b'
    assert r.methods['post'] == 'a.b.c'
    assert r.methods['delete'] == 'a.b.c.d'


def test_connection():
    p = Parser.parse([
        'CONNECTION foo http://foo.com:10101',
    ])
    assert p
    c = p.connections['foo']
    assert c
    assert c.url == 'http://foo.com:10101'
    assert c.is_json is True
    assert c.is_debug is False
    assert c.timeout == 5.0
    assert c.handler is None
    assert c.wrapper is None

    config = p.config.connection.foo
    assert config.url == 'http://foo.com:10101'
    assert config.is_active is True
    assert config.is_debug is False
    assert config.timeout == 5.0

    p = Parser.parse([
        'CONNECTION bar http://bar.com:11101 is_json=false is_debug=true timeout=10.5 handler=the.handler wrapper=the.wrapper',
    ])
    assert p
    c = p.connections['bar']
    assert c
    assert c.url == 'http://bar.com:11101'
    assert c.is_json is False
    assert c.is_debug is True
    assert c.timeout == 10.5
    assert c.handler == 'the.handler'
    assert c.wrapper == 'the.wrapper'

    config = p.config.connection.bar
    assert config.url == 'http://bar.com:11101'
    assert config.is_active is True
    assert config.is_debug is True
    assert config.timeout == 10.5


def test_header():
    p = Parser.parse([
        'CONNECTION foo http://foo.com:10101',
        'HEADER the-header default=whatever',
    ])
    assert p
    c = p.connections['foo']
    h = c.headers['the-header']
    assert h
    assert h.key == 'the-header'
    assert h.default == 'whatever'
    assert h.config is None

    try:
        p.config.connection.foo.header
        assert False
    except AttributeError:
        pass

    p = Parser.parse([
        'CONNECTION foo http://foo.com:10101',
        'HEADER the-header config=yeah',
    ])
    assert p
    c = p.connections['foo']
    h = c.headers['the-header']
    assert h
    assert h.key == 'the-header'
    assert h.default is None
    assert h.config == 'yeah'

    config = p.config.connection.foo.header
    assert config.yeah is None

    p = Parser.parse([
        'CONNECTION foo http://foo.com:10101',
        'HEADER the-header default=akk config=yeah',
    ])
    assert p
    c = p.connections['foo']
    h = c.headers['the-header']
    assert h
    assert h.key == 'the-header'
    assert h.default == 'akk'
    assert h.config == 'yeah'

    config = p.config.connection.foo.header
    assert config.yeah == 'akk'

    try:
        p = Parser.parse([
            'CONNECTION foo http://foo.com:10101',
            'HEADER the-header',
        ])
        assert False
    except Exception as e:
        assert str(e).startswith('header must have a default, config or code setting')


def test_resource():
    p = Parser.parse([
        'CONNECTION foo http://foo.com:10101',
        'RESOURCE bar /the/bar'
    ])
    assert p
    c = p.connections['foo']
    r = c.resources['bar']
    assert r
    assert r.path == '/the/bar'
    assert r.method == 'GET'
    assert r.is_json is None
    assert r.is_debug is None
    assert r.timeout is None
    assert r.handler is None
    assert r.wrapper is None

    config = p.config.connection.foo.resource.bar
    assert config.is_debug is None

    p = Parser.parse([
        'CONNECTION foo http://foo.com:10101',
        'RESOURCE akk /the/eek method=POST is_json=True is_debug=True timeout=6.3 handler=a.handler wrapper=a.wrapper',
    ])
    assert p
    c = p.connections['foo']
    r = c.resources['akk']
    assert r
    assert r.path == '/the/eek'
    assert r.method == 'POST'
    assert r.is_json is True
    assert r.is_debug is True
    assert r.timeout == 6.3
    assert r.handler == 'a.handler'
    assert r.wrapper == 'a.wrapper'

    config = p.config.connection.foo.resource.akk
    assert config.is_debug is True


def test_required():
    p = Parser.parse([
        'CONNECTION foo http://foo.com:10101',
        'RESOURCE bar /the/bar',
        'REQUIRED one',
        'REQUIRED two',
    ])
    assert p
    c = p.connections['foo']
    r = c.resources['bar']
    q = r.required
    assert q
    assert len(q) == 2
    assert q[0] == 'one'
    assert q[1] == 'two'


def test_optional():
    p = Parser.parse([
        'CONNECTION foo http://foo.com:10101',
        'RESOURCE bar /the/bar',
        'OPTIONAL one default=whatever',
        'OPTIONAL two config=yeah',
        'OPTIONAL three default=foo config=bar',
    ])
    assert p
    c = p.connections['foo']
    r = c.resources['bar']
    o = r.optional
    assert o
    oo = o['one']
    assert oo.default == 'whatever'
    oo = o['two']
    assert oo.default is None
    oo = o['three']
    assert oo.default == 'foo'
    assert oo.config == 'bar'

    config = p.config.connection.foo.resource.bar
    assert config.yeah is None
    assert config.bar == 'foo'
