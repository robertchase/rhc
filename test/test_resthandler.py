import unittest
from rhc.resthandler import RESTMapper


class RESTHandlerTest(unittest.TestCase):

    def setUp(self):
        self.c = RESTMapper()
        self.c.add('/test$', 1, 2, 3, 4)

        self.c.add('/foo$', 1, 2)
        self.c.add('/foo$', put=5)

    def test_basic(self):
        h, g = self.c._match('/test', 'GET')
        self.assertEqual(h, 1)
        self.assertEqual(g, ())

    def test_nomatch(self):
        h, g = self.c._match('/testt', 'GET')
        self.assertIsNone(h)
        self.assertIsNone(g)

    def test_multiple(self):
        h, g = self.c._match('/foo', 'post')
        self.assertEqual(h, 2)
        h, g = self.c._match('/foo', 'put')
        self.assertEqual(h, 5)
