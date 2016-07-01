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
from db import DB


class Query(object):

    def __init__(self, table_class):
        self._classes = [table_class]
        self._join = table_class.FULL_TABLE_NAME()

        self._columns = ['%s.`%s`' % (table_class.FULL_TABLE_NAME(), c) for c in table_class.FIELDS]
        self._columns.extend('%s AS %s' % (c, n) for n, c in table_class.CALCULATED_FIELDS.items())

        self._column_names = [f for f in table_class.FIELDS]
        self._column_names.extend(table_class.CALCULATED_FIELDS.keys())

        self._where = None
        self._order = None

    def where(self, where=None):
        self._where = where
        return self

    def order(self, order):
        self._order = order
        return self

    def by_id(self):
        self.where('%s.`id`=%%s' % self._classes[0].FULL_TABLE_NAME())
        return self

    def join(self, table_class1, column1=None, table_class2=None, column2='id', outer=False):
        ''' add a table to the query

        Parameters:
            table_class1 - DAO class of the table to add to the query
            column1 - join column on table1, default = table2.name + '_id'
            table_class2 - DAO class of existing table to join, default is most recently added to query
            column2 - join column of table2, default = 'id'
            outer - OUTER join indicator, if True or 'LEFT' then LEFT OUTER JOIN, if 'RIGHT' then RIGHT OUTER JOIN; default = False

        Hint: joining from parent to children is the default direction
        '''
        if not table_class2:
            table_class2 = self._classes[-1]
        if not column1:
            column1 = '%s_id' % table_class2.TABLE
        self._classes.append(table_class1)
        if outer:
            direction = 'LEFT' if outer is True else outer
            self._join += ' %s OUTER' % direction
        self._join += ' JOIN %s ON %s.`%s` = %s.`%s`' % (table_class1.FULL_TABLE_NAME(), table_class1.FULL_TABLE_NAME(), column1, table_class2.FULL_TABLE_NAME(), column2)

        self._columns.extend('%s.`%s`' % (table_class1.FULL_TABLE_NAME(), c) for c in table_class1.FIELDS)
        self._columns.extend('%s AS %s' % (c, n) for n, c in table_class1.CALCULATED_FIELDS.items())

        self._column_names.extend(table_class1.FIELDS)
        self._column_names.extend(table_class1.CALCULATED_FIELDS.keys())

        return self

    def _build(self, one, limit, offset, for_update):
        if one and limit:
            raise Exception('one and limit parameters are mutually exclusive')
        if one:
            limit = 1
        stmt = 'SELECT '
        stmt += ','.join(self._columns)
        stmt += ' FROM ' + self._join
        if self._where:
            stmt += ' WHERE ' + self._where
        if self._order:
            stmt += ' ORDER BY ' + self._order
        if limit:
            stmt += ' LIMIT %d' % int(limit)
        if offset:
            stmt += ' OFFSET %d' % int(offset)
        if for_update:
            stmt += ' FOR UPDATE'
        return stmt

    def execute(self, arg=None, one=False, limit=None, offset=None, for_update=False, generator=False, before_execute=None, after_execute=None):
        self._stmt = self._build(one, limit, offset, for_update)
        self._executed_stmt = None
        if before_execute:
            before_execute(self)
        g = self._execute(self._stmt, arg, after_execute)
        if generator:
            return g
        result = [o for o in g]
        if one:
            result = result[0] if len(result) else None
        return result

    def _execute(self, stmt, arg, after_execute):
        cur = DB.cursor()
        cur.execute(stmt, arg)
        self._executed_stmt = cur._executed
        if after_execute:
            after_execute(self)
        primary_table = self._classes[0].TABLE
        for rs in cur:
            s = {}
            row = zip(self._column_names, rs)
            for c in self._classes:
                l = len(c.FIELDS) + len(c.CALCULATED_FIELDS)
                val, row = row[:l], row[l:]
                o = c(**dict(val))
                s[c.TABLE] = o
                o._tables = s
            yield s[primary_table]
        return
