from rhc.micro_fsm.parser import Parser


def test_server():
    p = Parser.parse(['SERVER test 12345'])
    assert p
    assert len(p.servers) == 1
    assert p.servers[12345].name == 'test'

    assert p.config.server.test.port == 12345
    assert p.config.server.test.is_active is True
    assert p.config.server.test.ssl.is_active is False
    assert p.config.server.test.ssl.keyfile is None
    assert p.config.server.test.ssl.certfile is None


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
