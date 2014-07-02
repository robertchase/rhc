from itertools import izip

from db import DB


class Query(object):

    def __init__(self, table_class):
        self._classes = [table_class]
        self._join = '`%s`' % table_class.TABLE

        self._columns = ['`%s`.`%s`' % (table_class.TABLE, c) for c in table_class.FIELDS]
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
        self.where('`%s`.`id`=%%s' % self._classes[0].TABLE)
        return self

    def join(self, table_class1, column1=None, table_class2=None, column2='id', outer=False):
        ''' add a table to the query

        Parameters:
            table_class1 - DAO class of the table to add to the query
            column1 - join column on table1, default = table2.name + '_id'
            table_class2 - DAO class of existing table to join, default is most recently added to query
            column2 - join column of table2, default = 'id'
            outer - OUTER join indicator, default = False
        '''
        if not table_class2:
            table_class2 = self._classes[-1]
        if not column1:
            column1 = '%s_id' % table_class2.TABLE
        self._classes.append(table_class1)
        if outer:
            self._join += ' OUTER'
        self._join += ' JOIN `%s` ON `%s`.`%s` = `%s`.`%s`' % (table_class1.TABLE, table_class1.TABLE, column1, table_class2.TABLE, column2)

        self._columns.extend('`%s`.`%s`' % (table_class1.TABLE, c) for c in table_class1.FIELDS)
        self._columns.extend('%s AS %s' % (c, n) for n, c in table_class1.CALCULATED_FIELDS.items())

        self._column_names.extend(table_class1.FIELDS)
        self._column_names.extend(table_class1.CALCULATED_FIELDS.keys())

        return self

    def _build(self, arg, one, for_update):
        stmt = 'SELECT '
        stmt += ','.join(self._columns)
        stmt += ' FROM ' + self._join
        if self._where:
            stmt += ' WHERE ' + self._where
        if self._order:
            stmt += ' ORDER BY ' + self._order
        if one:
            stmt += ' LIMIT 1'
        if for_update:
            stmt += ' FOR UPDATE'
        self._stmt = stmt % arg if arg else stmt
        self._executed_stmt = None
        return stmt

    def execute(self, arg=None, one=False, for_update=False, test=False):

        stmt = self._build(arg, one, for_update)
        if test:
            result = self._stmt
        else:
            result = []
            cur = DB.cursor()
            cur.execute(stmt, arg)
            self._executed_stmt = cur._executed
            for rs in cur:
                s = {}
                row = [(n, v) for n, v in izip(self._column_names, rs)]
                main_obj = None
                for c in self._classes:
                    l = len(c.FIELDS) + len(c.CALCULATED_FIELDS)
                    val, row = row[:l], row[l:]
                    o = c(**{n: v for n, v in val})
                    s[c.TABLE] = o
                    o._tables = s
                    if main_obj is None:
                        main_obj = o
                result.append(main_obj)
            if one:
                result = result[0] if len(result) else None

        return result
