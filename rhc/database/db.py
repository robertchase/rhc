'''
The MIT License (MIT)

Copyright (c) 2013-2015 Robert H Chase

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
import pymysql
import threading


class _DB(object):

    def __init__(self):
        self.__kwargs = None
        self.__transaction = 0
        self.__local = threading.local()

    def __enter__(self):
        self.start_transaction()
        return self.cursor()

    def __exit__(self, exception_type, exception_value, trace):
        if exception_type:
            self.stop_transaction(commit=False)
        else:
            self.stop_transaction()

    def setup(self, **kwargs):
        kwargs['autocommit'] = False
        kwargs['init_command'] = 'SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED'
        if kwargs.pop('dirty', False):
            kwargs['init_command'] = 'SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED'
        self.__commit = kwargs.pop('commit', True)
        self.__close = kwargs.pop('close', False)
        self.__kwargs = kwargs
        return self

    def _connection(self):
        connection = getattr(self.__local, 'connection', None)
        if connection:
            connection.ping()
        else:
            if not self.__kwargs:
                raise Exception('must call setup before using DB')
            connection = pymysql.connect(**self.__kwargs)
            self.__local.connection = connection
        return connection

    def close(self):
        self._connection().close()

    def cursor(self):
        return self._connection().cursor()

    def _commit(self):
        self._connection().commit()

    def _rollback(self):
        self._connection().rollback()

    def start_transaction(self):
        self.__transaction += 1

    def stop_transaction(self, commit=True):
        if self.__transaction == 0:
            raise Exception('attempting to stop transaction when none is started')
        self.__transaction -= 1
        if self.__transaction == 0:
            if commit and self.__commit:
                self._commit()
            else:
                self._rollback()
            if self.__close:
                self.close()

DB = _DB()

if __name__ == '__main__':
    import time
    DB.setup(user='test', db='test')
    cur = DB.cursor()
    cur.execute('select "foo"')
    for row in cur:
        print row
    time.sleep(5)
    cur = DB.cursor()
    cur.execute('select "foo"')
    for row in cur:
        print row
    print DB.cursor()
    print DB.cursor()
