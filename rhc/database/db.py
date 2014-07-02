import pymysql


class _DB(object):

    def __init__(self):
        self.__kwargs = None
        self.__connection = None
        self.__transaction = 0

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
        self.__commit = kwargs.pop('commit', True)
        self.__close = kwargs.pop('close', False)
        self.__kwargs = kwargs
        self.__connection = None
        return self

    def _connection(self):
        if self.__connection:
            self.__connection.ping()
        else:
            if not self.__kwargs:
                raise Exception('must call setup before using DB')
            self.__connection = pymysql.connect(**self.__kwargs)
        return self.__connection

    def close(self):
        self.__connection.close()

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
