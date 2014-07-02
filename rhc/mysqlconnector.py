'''
The MIT License (MIT)

Copyright (c) 2013-2014 Robert H Chase

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''
import MySQLdb
import time


class LoginException (Exception):
    pass


class MySQLConnector (object):

    def __init__(self, user, password=None, database=None, host=None,
                 reconnect=3600):
        self.__db = None
        args = {'user': user}
        if password:
            args['passwd'] = password
        if database:
            args['db'] = database
        if host:
            args['host'] = host
        self.__args = args
        self.__reconnect = reconnect

        try:
            self.__raw_connect()
        except MySQLdb.OperationalError, e:
            self.on_initial_connect_failure(str(e))
            raise LoginException(e)

    def on_initial_connect_failure(self, msg):
        pass

    def on_connect_failure(self, msg):
        pass

    def on_connect(self):
        pass

    def on_reconnect(self):
        pass

    def on_failure(self):
        pass

    def on_close(self):
        pass

    def reconnect(self):
        self.close(quiet=True)
        self.__connect(reconnect=True)

    def __connect(self, reconnect=False):
        try:
            self.__raw_connect(reconnect=reconnect)
        except Exception, e:
            self.on_connect_failure(str(e))

    def __raw_connect(self, reconnect=False):
        self.__db = MySQLdb.connect(**self.__args)
        if reconnect:
            self.on_reconnect()
        else:
            self.on_connect()
        self.time = time.time()

    def cursor(self):
        '''
          return a cursor (or None if not connected)
        '''
        if None == self.__db:
            return None

        # --- refresh database connection after 'reconnect' seconds
        if self.__reconnect < time.time() - self.time:
            self.reconnect()
            if None == self.__db:
                return None

        try:
            return self.__db.cursor()
        except Exception:
            self.close()
            self.on_failure()
            return None

    def close(self, quiet=False):
        '''
          close the database connection
        '''
        self.__db = None
        if not quiet:
            self.on_close()

    def commit(self):
        if self.__db:
            self.__db.commit()

    def rollback(self):
        if self.__db:
            self.__db.rollback()

if __name__ == "__main__":

    db = MySQLConnector('test', 'test', 'test')
    print db.cursor()
