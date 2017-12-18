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
        cfg._define('server.akk')
        cfg._define('server.eek')
        cfg._define('server.comment1')
        cfg._define('server.comment2')
        cfg._define('server.comment3')
        cfg._define('server.port', 100, validate_int)
        data = os.path.splitext(inspect.getfile(self.__class__))[0] + '.txt'
        cfg._load(data)
        self.assertEqual(cfg.server.host, 'local=host')
        self.assertEqual(cfg.server.port, 1000)
        self.assertEqual(cfg.server.url, 'one#two')
        self.assertEqual(cfg.server.akk, 'one#asdf')
        self.assertEqual(cfg.server.eek, 'one#')
        self.assertIsNone(cfg.server.comment1)
        self.assertEqual(cfg.server.comment2, 'ab')
        self.assertEqual(cfg.server.comment3, 'ab#c')

if __name__ == '__main__':
    unittest.main()
