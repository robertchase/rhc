from importlib import import_module
import sys

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

if __name__ == '__main__':

    f = sys.stdin if len(sys.argv) < 2 else open(sys.argv[1])
    config = _load(f)

    m = RESTMapper(context=config['context'])
    for pattern, kwargs in config['routes']:
        m.add(pattern, **kwargs)

    SERVER.add_server(config['port'], RESTHandler, m)
    try:
        while True:
            SERVER.service(.1)
    except KeyboardInterrupt:
        print 'done'
