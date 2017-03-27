class Task(object):

    def __init__(self, callback):
        self.callback = callback
        self.is_done = False

    def defer(self, task_cmd, partial_callback):
        def on_defer(rc, result):
            if rc == 0:
                task_cmd(self, result)
            else:
                self.error(result)
        try:
            partial_callback(on_defer)
        except Exception as e:
            self.error(str(e))

    def error(self, message):
        self.respond(message, 1)

    def respond(self, result, rc=0):
        if self.is_done:
            return
        self.is_done = True
        self.callback(rc, result)


def partial(fn):
    def _args(*args, **kwargs):
        def _callback(callback_fn):
            task = Task(callback_fn)
            fn(task, *args, **kwargs)
            return task
        return _callback
    return _args


def wrap(cmd, *args, **kwargs):
    return partial(cmd)(*args, **kwargs)
