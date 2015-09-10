import inspect
import os
import unittest
from rhc.config import Config, validate_int, validate_file


class ConfigText(unittest.TestCase):

    def test_default(self):
        cfg = Config()
        cfg._define('foo', 'bar')
        self.assertEqual(cfg.foo, 'bar')

    def test_reset(self):
        cfg = Config()
        cfg._define('a.b.c', 'nothing')
        self.assertEqual(cfg.a.b.c, 'nothing')
        cfg._set('a.b.c', 'something')
        self.assertEqual(cfg.a.b.c, 'something')

    def test_int(self):
        cfg = Config()
        cfg._define('test', 0, validate_int)
        cfg._set('test', '100')
        self.assertEqual(cfg.test, 100)

    def test_empty_int(self):
        cfg = Config()
        cfg._define('test', validator=validate_int)
        self.assertRaises(ValueError, cfg._set, 'test', '')

    def test_file(self):
        cfg = Config()
        cfg._define('test', validator=validate_file)
        data = os.path.splitext(inspect.getfile(self.__class__))[0] + '.txt'
        cfg._set('test', data)
        self.assertEqual(cfg.test, data)

    def test_missing_file(self):
        cfg = Config()
        cfg._define('test', validator=validate_file)
        data = os.path.splitext(inspect.getfile(self.__class__))[0] + '.txtt'
        self.assertRaises(Exception, cfg._set, 'test', data)

    def test_load(self):
        cfg = Config()
        cfg._define('server.host', 'localhost')
        cfg._define('server.url')
        cfg._define('server.port', 100, validate_int)
        data = os.path.splitext(inspect.getfile(self.__class__))[0] + '.txt'
        cfg._load(data)
        self.assertEqual(cfg.server.host, 'local=host')
        self.assertEqual(cfg.server.port, 1000)
        self.assertEqual(cfg.server.url, 'one#two')

    def test_count_default(self):
        cfg = Config()
        cfg._define('a.b.count', 0, validate_int)
        cfg._define('a.b.c', 'bar', counter='a.b.count')
        cfg._set('a.b.count', '2')
        self.assertEqual(cfg.a.b.c[2], 'bar')
        cfg._set('a.b.c.2', 'foo')
        self.assertEqual(cfg.a.b.c[2], 'foo')

    def test_special_variables(self):
        cfg = Config()
        cfg._define('a.b.default', 100)
        self.assertEqual(cfg.a.b.default, 100)
        cfg._define('a.b.counter', 101)
        self.assertEqual(cfg.a.b.counter, 101)
        cfg._define('a.b.validator', 102)
        self.assertEqual(cfg.a.b.validator, 102)
        cfg._define('a.b.value', 103)
        self.assertEqual(cfg.a.b.value, 103)

if __name__ == '__main__':
    unittest.main()
