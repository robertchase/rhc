from datetime import datetime
from itertools import chain

from db import DB
from query import Query


class DAO(object):

    # TABLE = ''
    # FIELDS = ()
    CALCULATED_FIELDS = {}
    DEFAULT = {}

    def __init__(self, **kwargs):
        self._tables = {}
        self._validate(kwargs)
        self._normalize(kwargs)
        self.on_init(kwargs)
        for n, v in kwargs.items():
            self.__dict__[n] = v
        self.after_init()

    def on_init(self, kwargs):
        pass

    def after_init(self):
        pass

    def autoload(self, table):
        ''' dynamically load data from a related table

        When a reference is made to an attribute which is not one of the specified
        FIELDS or CALCULATED_FIELDS, or if a lookup is done using the [...] syntax,
        it is treated as a reference to a DAO object joined with this object during
        query processing. If that object is not found, a call is made to this
        method so that the data can be loaded on-demand.

        This method can return None, which will result in an AttributeError,
        or dynamically load a DAO object and return it.
        '''
        return None

    def _validate(self, kwargs):
        ''' make sure field names are valid '''
        for f in kwargs:
            if f not in self.FIELDS:
                if f not in self.CALCULATED_FIELDS:
                    raise TypeError("Unexpected parameter: %s" % f)

    def _normalize(self, kwargs):
        ''' establish default or empty values for all fields '''
        for f in chain(self.FIELDS, self.CALCULATED_FIELDS):
            if f != 'id':
                if f not in kwargs:
                    if f in self.DEFAULT:
                        kwargs[f] = self.DEFAULT[f]
                    else:
                        kwargs[f] = None

    def __getattr__(self, name):
        ''' see if name refers to some other table added during query.join operation '''
        if name in self._tables:
            table = self._tables[name]
        else:
            table = self.autoload(name)
            if table:
                self._tables[name] = table
                table._tables = self._tables
            else:
                raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, name))
        return table

    def __getitem__(self, name):
        ''' allow access to other tables using DAO['other_table'] syntax '''
        return self.__getattr__(name)

    def __setattr__(self, name, value):
        if name.startswith('_') or name in self.FIELDS:
            self.__dict__[name] = value
        else:
            raise AttributeError('%s is not a valid field name' % name)

    def _json(self, value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def json(self):
        return self.on_json({n: self._json(getattr(self, n)) for n in chain(self.FIELDS, self.CALCULATED_FIELDS.keys()) if hasattr(self, n)})

    def on_json(self, json):
        return json

    def save(self):
        self.before_save()
        if 'id' not in self.FIELDS:
            raise Exception('DAO.save() requireds that an "id" field be defined')
        fields = [f for f in self.FIELDS if f != 'id']
        args = [self.__dict__[f] for f in fields]
        if not hasattr(self, 'id'):
            new = True
            stmt = 'INSERT INTO `' + self.TABLE + '` (' + ','.join('`' + f + '`' for f in fields) + ') VALUES (' + ','.join('%s' for n in range(len(fields))) + ')'
        else:
            new = False
            stmt = 'UPDATE `' + self.TABLE + '` SET ' + ','.join(['`%s`=%%s' % n for n in fields]) + ' WHERE id=%s'
            args.append(self.id)
        with DB as cur:
            self._stmt = stmt
            self._executed_stmt = None
            cur.execute(stmt, args)
            self._executed_stmt = cur._executed
        if new:
            setattr(self, 'id', cur.lastrowid)
        self.after_save()

    def before_save(self):
        pass

    def after_save(self):
        pass

    def delete(self):
        with DB as cur:
            cur.execute('DELETE from `%s` where `id`=%%s' % self.TABLE, self.id)

    @classmethod
    def load(cls, id):
        return cls.query().by_id().execute(id, one=True)

    @classmethod
    def list(cls, where=None, args=None):
        return cls.query().where(where).execute(tuple() if not args else args)

    @classmethod
    def query(cls):
        return Query(cls)
