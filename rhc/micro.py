from importlib import import_module
import sys
import traceback

from rhc.log import logmsg
from rhc.tcpsocket import Server
from rhc.resthandler import RESTMapper, RESTHandler


SERVER = Server()


def _import(item_path):
    path, function = item_path.rsplit('.', 1)
    module = import_module(path)
    return getattr(module, function)


def _load(f):

    result = dict(
        routes=[],
        context=None,
        port=None,
    )

    kwargs = None
    for lnum, l in enumerate((ll for ll in (l.split('#', 1)[0].strip() for l in f.readlines()) if len(ll)), start=1):
        if l.find(' ') == -1:
            raise Exception("Line %d doesn't contain a space" % lnum)
        rectyp, recval = l.split(' ', 1)
        rectyp = rectyp.upper()
        recval = recval.strip()

        if rectyp == 'ROUTE':
            kwargs = {}
            result['routes'].append((recval.strip(), kwargs))
        elif rectyp in ('GET', 'PUT', 'POST', 'DELETE'):
            if kwargs is None:
                raise Exception("Line %d contains a %s that doesn't belong to a ROUTE" % (lnum, rectyp))
            kwargs[rectyp.lower()] = _import(recval)
        elif rectyp == 'CONTEXT':
            kwargs = None
            # result['context'] = type('context', (object,), _import(recval)())()  # import recval, evaluate as function returning dict, wrap in object
            result['context'] = _import(recval)()
        elif rectyp == 'PORT':
            kwargs = None
            result['port'] = int(recval)
        else:
            raise Exception("Line %d is an invalid record type: %s" % (lnum, rectyp))

    return result


class MicroRESTHandler(RESTHandler):

    def on_open(self):
        logmsg(102, self.on_full_address())

    def on_close(self):
        logmsg(103, self.on_full_address())

    def on_rest_data(self, request, *groups):
        print 'rest:', self.http_method, self.http_resource, groups

    def on_rest_exception(self, exception_type, value, trace):
        data = traceback.format_exe(trace)
        print data
        return data


if __name__ == '__main__':
    from StringIO import StringIO
    from rhc.log import LOG

    LOG.setup(StringIO('''
        MESSAGE 100
        LOG     INFO
        DISPLAY ALWAYS
        TEXT Server listening on port %s

        MESSAGE 101
        LOG     INFO
        DISPLAY ALWAYS
        TEXT Received shutdown command from keyboard

        MESSAGE 102
        LOG     INFO
        DISPLAY ALWAYS
        TEXT open: %s

        MESSAGE 103
        LOG     INFO
        DISPLAY ALWAYS
        TEXT close: %s

        MESSAGE 104
        LOG     INFO
        DISPLAY ALWAYS
        TEXT request method=%s, resource=%s, query=%s, groups=%s

    '''))

    f = sys.stdin if len(sys.argv) < 2 else open(sys.argv[1])
    config = _load(f)

    m = RESTMapper(context=config['context'])
    for pattern, kwargs in config['routes']:
        m.add(pattern, **kwargs)

    SERVER.add_server(config['port'], MicroRESTHandler, m)
    try:
        while True:
            SERVER.service(.1)
    except KeyboardInterrupt:
        print 'done'
