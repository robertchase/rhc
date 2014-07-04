import json
import unittest
from rhc.resthandler import content_to_json


@content_to_json()
def test1(handler):
    return handler.json['this']


@content_to_json('a')
def test2(handler, a):
    return a


class Handler(object):
    pass


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
        r = test1(h)
        self.assertEqual(r.code, 400)
        r = test2(h)
        self.assertEqual(r.code, 400)

if __name__ == '__main__':
    unittest.main()
