from importlib import import_module
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
        name='MICRO',
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
        elif rectyp == 'INIT':
            _import(recval)()
        elif rectyp == 'NAME':
            result['name'] = _import(recval)()
        elif rectyp == 'CONTEXT':
            kwargs = None
            result['context'] = _import(recval)()
        elif rectyp == 'PORT':
            kwargs = None
            result['port'] = _import(recval)()
        else:
            raise Exception("Line %d is an invalid record type: %s" % (lnum, rectyp))

    return result


class MicroRESTHandler(RESTHandler):

    NEXT_ID = 0
    NEXT_REQUEST_ID = 0

    def on_open(self):
        self.id = MicroRESTHandler.NEXT_ID = MicroRESTHandler.NEXT_ID + 1
        logmsg(902, self.id, self.full_address())

    def on_close(self):
        logmsg(903, self.id, self.full_address())

    def on_rest_data(self, request, *groups):
        request.id = MicroRESTHandler.NEXT_REQUEST_ID = MicroRESTHandler.NEXT_REQUEST_ID + 1
        logmsg(904, self.id, request.id, request.http_method, request.http_resource, request.http_query_string, groups)
        logmsg(906, self.id, request.id, request.http_headers)
        logmsg(907, self.id, request.id, request.http_content[:100] if request.http_content else '')

    def on_rest_send(self, code, message, content, headers):
        logmsg(908, self.id, code, message, headers)
        logmsg(909, self.id, '' if not content else (content[:100] + '...') if len(content) > 100 else content)

    def on_rest_no_match(self):
        logmsg(910, self.id, self.http_method, self.http_resource)

    def on_rest_exception(self, exception_type, value, trace):
        data = traceback.format_exc(trace)
        logmsg(905, data)
        return data


if __name__ == '__main__':
    import argparse
    from StringIO import StringIO
    from rhc.log import LOG

    parser = argparse.ArgumentParser()
    parser.add_argument('control_file', type=open)
    parser.add_argument('-m', '--messagefile')
    parser.add_argument('-s', '--stdout', action='store_true', default=False)
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    args = parser.parse_args()

    config = _load(args.control_file)

    messages = StringIO('''
        MESSAGE 900
        LOG     INFO
        DISPLAY ALWAYS
        TEXT Server listening on port %s

        MESSAGE 901
        LOG     INFO
        DISPLAY ALWAYS
        TEXT Received shutdown command from keyboard

        MESSAGE 902
        LOG     INFO
        DISPLAY ALWAYS
        TEXT open: cid=%d, %s

        MESSAGE 903
        LOG     INFO
        DISPLAY ALWAYS
        TEXT close: cid=%d, %s

        MESSAGE 904
        LOG     INFO
        DISPLAY ALWAYS
        TEXT request cid=%d, rid=%d, method=%s, resource=%s, query=%s, groups=%s

        MESSAGE 905
        LOG     WARNING
        DISPLAY ALWAYS
        TEXT exception encountered: %s

        MESSAGE 906
        LOG     DEBUG
        DISPLAY VERBOSE
        TEXT request cid=%d, rid=%d, headers=%s

        MESSAGE 907
        LOG     DEBUG
        DISPLAY VERBOSE
        TEXT request cid=%d, rid=%d, content=%s

        MESSAGE 908
        LOG     DEBUG
        DISPLAY VERBOSE
        TEXT response cid=%d, code=%d, message=%s, headers=%s

        MESSAGE 909
        LOG     DEBUG
        DISPLAY VERBOSE
        TEXT response cid=%d, content=%s

        MESSAGE 910
        LOG     WARNING
        DISPLAY ALWAYS
        TEXT no match cid=%d, method=%s, resource=%s

    ''')
    if args.messagefile:
        messages = (messages, args.messagefile)
    LOG.setup(messages, name=config['name'], stdout=args.stdout, verbose=args.verbose)

    m = RESTMapper(context=config['context'])
    for pattern, kwargs in config['routes']:
        m.add(pattern, **kwargs)

    SERVER.add_server(config['port'], MicroRESTHandler, m)
    logmsg(900, config['port'])
    try:
        while True:
            SERVER.service(.1)
    except KeyboardInterrupt:
        logmsg(901)
