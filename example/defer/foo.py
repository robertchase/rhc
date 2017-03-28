import rhc.async as async
import rhc.task as task


foo = async.Connection('http://rhc:12345')
foo.add_resource('hello', '/hello/{name}')


def ping(request):
    request.defer(on_ping, logic_hello('whirled'))


def on_ping(request, result):
    request.respond(dict(on_ping=result))


def hello(request, name):
    return dict(hello=name)


# logic


@task.partial
def logic_hello(task, name):
    task.defer(on_logic_hello, foo.hello(name))


def on_logic_hello(task, result):
    task.respond(dict(on_logic_hello=result))


'''
@async.partial
class logic_hello(object):

    def __init__(self, callback, name):
        self.callback = callback
        foo.hello(name)(self.on_hello)

    def on_hello(self, rc, result):
        if rc == 0:
            self.callback(0, dict(on_hello=result))
        else:
            self.callback(1, result)
'''
