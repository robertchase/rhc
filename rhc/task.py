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

import logging
log = logging.getLogger(__name__)


class Task(object):

    def __init__(self, callback):
        self.callback = callback
        self.final = None  # callable executed before callback (error or success)
        self.is_done = False

    def defer(self, task_cmd, partial_callback, final_fn=None):
        ''' defer the task until partial_callback completes; then call task_cmd

            if partial_callback does not complete successfully, then task_cmd is not called;
            instead, the error is handled by calling error on the task. final_fn, if
            specified, is always called.

            Parameters:
                task_cmd         - called with result of partial_callback on success
                                   task_cmd(task, result)
                partial_callback - function that takes a callback_fn
                                   callback_fn is eventually called with (rc, result)
                                   if rc != 0, partial_callback failed
                final_fn         - a function that is called once after the partial_callback
                                   is complete. it takes no parameters.
        '''
        def on_defer(rc, result):
            if final_fn:
                try:
                    final_fn()
                except Exception as e:
                    log.warning('failure running final_fn: %s', str(e))
            if rc == 0:
                task_cmd(self, result)
            else:
                self.error(result)
        partial_callback(on_defer)
        return self

    def error(self, message):
        self.respond(message, 1)

    def respond(self, result, rc=0):
        if self.is_done:
            return
        if self.final:
            try:
                self.final()
            except Exception as e:
                log.warning('failure running task final: %s', str(e))
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


def catch_exceptions(message):
    def _catch_exceptions(task_handler):
        def inner(task, *args, **kwargs):
            try:
                return task_handler(task, *args, **kwargs)
            except Exception:
                log.exception(message)
        return inner
    return _catch_exceptions
