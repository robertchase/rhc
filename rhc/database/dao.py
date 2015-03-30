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
from datetime import datetime, date
from itertools import chain
import json

from db import DB
from query import Query


class DAO(object):

    # TABLE = ''
    # FIELDS = ()
    CALCULATED_FIELDS = {}
    DEFAULT = {}
    JSON_FIELDS = ()
    FOREIGN = {}  # name: 'class path'
    CHILDREN = {}  # name: 'class path'

    def __init__(self, **kwargs):
        self._tables = {}
        self._children = {}
        self._foreign(kwargs)
        self._validate(kwargs)
        self._normalize(kwargs)
        self.on_init(kwargs)
        if 'id' in kwargs:
            self.on_load(kwargs)
            self._jsonify(kwargs)
        else:
            self.on_new(kwargs)
        for n, v in kwargs.items():
            self.__dict__[n] = v
        # self._join_foreign()
        self.after_init()

    def on_new(self, kwargs):
        pass

    def on_init(self, kwargs):
        pass

    def on_load(self, kwargs):
        pass

    def after_init(self):
        pass

    def _foreign(self, kwargs):
        ''' identify and translate foreign key relations

            kwargs that match table names specified in FOREIGN are translated from
            objects to ids using a "table_name + '_id' = object.id" pattern.

            foreign objects are cached in self with the join method.
        '''
        for table in self.FOREIGN.keys():
            t = kwargs.get(table)
            if t:
                kwargs[table + '_id'] = t.id
                del kwargs[table]
                self.join(t)

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

    def _jsonify(self, kwargs):
        for f in self.JSON_FIELDS:
            if kwargs[f]:
                kwargs[f] = json.loads(kwargs[f])

    @staticmethod
    def _import(target):
        modnam, clsnam = target.rsplit('.', 1)
        mod = __import__(modnam)
        for part in modnam.split('.')[1:]:
            mod = getattr(mod, part)
        return getattr(mod, clsnam)

    def __getattr__(self, name):
        if name in self._tables:
            result = self._tables[name]  # cached foreign or Query.join added object
        elif name in self.FOREIGN:
            result = self.foreign(self._import(self.FOREIGN[name]))  # foreign lookup
        elif name in self._children:
            result = self._children[name]  # cached children
        elif name in self.CHILDREN:
            result = self.children(self._import(self.CHILDREN[name]))  # children lookup
        else:
            raise AttributeError("'%s' object has no attribute '%s'" % (self.__class__.__name__, name))
        return result

    def __getitem__(self, name):
        ''' allow access to other tables using DAO['other_table'] syntax '''
        return self.__getattr__(name)

    def __setattr__(self, name, value):
        if name.startswith('_') or name in self.FIELDS:
            self.__dict__[name] = value
        else:
            raise AttributeError('%s is not a valid field name' % name)

    def _json(self, value):
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return value

    def json(self):
        return self.on_json({n: self._json(getattr(self, n)) for n in chain(self.FIELDS, self.CALCULATED_FIELDS.keys()) if hasattr(self, n)})

    def on_json(self, json):
        return json

    def save(self):
        if 'id' not in self.FIELDS:
            raise Exception('DAO.save() requireds that an "id" field be defined')
        cache = {}
        for n in self.JSON_FIELDS:
            v = cache[n] = getattr(self, n)
            if v:
                setattr(self, n, json.dumps(self.on_json_save(n, v)))
        self.before_save()
        if not hasattr(self, 'id'):
            self.before_insert()
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
            self.after_insert()
        self.after_save()
        for n in self.JSON_FIELDS:
            setattr(self, n, cache[n])
        return self

    def on_json_save(self, name, obj):
        return obj

    def before_save(self):
        pass

    def before_insert(self):
        pass

    def after_insert(self):
        pass

    def after_save(self):
        pass

    def delete(self):
        with DB as cur:
            cur.execute('DELETE from `%s` where `id`=%%s' % self.TABLE, self.id)

    def children(self, cls):
        '''
            return the members of cls with a foreign_key reference to self.

            the query is constructed as 'WHERE <cls.TABLE>.<self.TABLE>_id = <self.id>'
            and self is joined (using the join method) to each child

            a lazy cache is maintained (query is done at most one time).
        '''
        child = cls.TABLE
        if child not in self._children:
            self._children[child] = [c.join(self) for c in cls.query().where('%s.%s_id = %%s' % (child, self.TABLE)).execute(self.id)]
        return self._children[child]

    def foreign(self, cls):
        '''
            return the instance of cls to which self has a foreign_key reference.

            the query is constructed as 'WHERE <cls.TABLE>.id = <self.<cls.TABLE>_id>'

            a lazy cache is maintained (query is done at most one time) using the join method.
        '''
        foreign = cls.TABLE
        if foreign not in self._tables:
            foreign_id = getattr(self, '%s_id' % foreign)
            self.join(cls.query().where('%s.id = %%s' % foreign).execute(foreign_id, one=True))
        return self._tables[foreign]

    @classmethod
    def load(cls, id):
        return cls.query().by_id().execute(id, one=True)

    @classmethod
    def list(cls, where=None, args=None):
        return cls.query().where(where).execute(tuple() if not args else args)

    @classmethod
    def query(cls):
        return Query(cls)

    def join(self, obj):
        '''add a DAO to the list of tables to which this object is joined

        Allows the DAO.table_name or DAO[table_name] syntax to work for
        the specified object.

        Parameters:
            obj - object to 'join' to self, if None then pass

        Returns:
            self
        '''
        if obj:
            self._tables[obj.TABLE] = obj
            obj._tables = self._tables
        return self
