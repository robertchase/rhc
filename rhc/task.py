'''
The MIT License (MIT)

Copyright (c) 2013-2017 Robert H Chase

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

        return self

    def error(self, message):
        self.respond(message, 1)

    def respond(self, result, rc=0):
        if self.is_done:
            return
        self.is_done = True
        self.callback(rc, result)


def wrap(callback_cmd, *args, **kwargs):
    ''' helper function callback_cmd -> partially executed partial '''
    return partial(callback_cmd)(*args, **kwargs)


def from_callback(task_cmd):
    ''' helper function callback_cmd -> executing partial

        if the caller invokes the wrapped or decorated task_cmd
        using a standard callback syntax:

            task_cmd(callback, *args, **kwargs)

        then a task is generated from the callback, and a partial
        is immediately started.
    '''
    def _wrap(callback, *args, **kwargs):
        return partial(task_cmd)(*args, **kwargs)(callback)
    return _wrap


def partial(fn):
    def _args(*args, **kwargs):
        def _callback(callback_fn):
            task = Task(callback_fn)
            fn(task, *args, **kwargs)
            return task
        return _callback
    return _args
