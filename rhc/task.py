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


def wrap(cmd, *args, **kwargs):
    def _partial(callback_fn):
        cmd(Task(callback_fn), *args, **kwargs)
    return _partial
