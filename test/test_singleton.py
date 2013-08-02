import unittest
from rhc.singleton import Singleton

class Test(Singleton):
    pass

class SingletonTest(unittest.TestCase):

    def test_basic(self):
       t = Test()
       t.foo = 1

       tt = Test()
       self.assertEqual(tt.foo, 1)
