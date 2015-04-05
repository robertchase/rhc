import json
import unittest
from rhc.resthandler import RESTRequest, content_to_json


@content_to_json()
def test1(handler):
    return handler.json['this']


@content_to_json('a')
def test2(handler, a):
    return a


@content_to_json(('a', int), 'b')
def test3(handler, a, b):
    return a + 1, b


class Handler(RESTRequest):
    def __init__(self):
        self.http_content = ''
        self.is_delayed = False


class RESTJsonTest(unittest.TestCase):

    def test_json_content(self):
        h = Handler()
        h.http_content = json.dumps(dict(this='is', a='test'))
        self.assertEqual(test1(h), 'is')
        self.assertEqual(test2(h), 'test')

    def test_json_form(self):
        h = Handler()
        h.http_content = 'this=is&a=test'
        self.assertEqual(test1(h), 'is')
        self.assertEqual(test2(h), 'test')

    def test_json_bad(self):
        h = Handler()
        r = test2(h)
        self.assertEqual(r.code, 400)

    def test_json_type(self):
        h = Handler()
        h.http_content = json.dumps(dict(a='1', b='2'))
        a, b = test3(h)
        self.assertEqual(a, 2)
        self.assertEqual(b, '2')

if __name__ == '__main__':
    unittest.main()
