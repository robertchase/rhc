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

import inspect
import logging
log = logging.getLogger(__name__)


class Task(object):

    def __init__(self, callback, cid=None):
        self._callback = [callback]
        self.cid = cid
        self.final = None  # callable executed before callback (error or success)

    @property
    def callback(self):
        if len(self._callback) == 1:
            self.on_done()
        return self._callback.pop()

    @property
    def is_done(self):
        return len(self._callback) == 0

    def on_done(self):
        if self.final:
            try:
                self.final()
            except Exception as e:
                log.warning('cid=%s, failure running task final: %s', self.cid,
                            str(e))

    def call(self, fn, args=None, kwargs=None, on_success=None, on_none=None,
             on_error=None, on_timeout=None):
        """ Call an async function.

        Allows for flexible handling of the return states of async function
        calls.

        Parameters:
            fn - callable async function (See Note 1)

            args - None, scalar, tuple or list
                Positional argments to be passed to fn.

            kwargs - None or dict
                Keyword argments to be passed to fn.

            on_success - callable
                called if specified and rc == 0 and
                if none of on_success_code, on_none and on_none_404 apply
                    on_success(task, result)

            on_error - callable
                called if specified and rc != 0
                    on_error(task, result)

            on_none - callable
                called if specified and rc == 0 and result is None
                    on_none(task, None)

        Notes:

            1.  An async function is structured like this:

                    fn(callback, *args, **kwargs)

                When the function is complete, it calls callback with two
                parameters:

                    rc - 0 for success, non-zero for error
                    result - function response on success, message on error

            2. If the first parameter of fn (from inspection) is named 'task',
               then an rhc.Task object is passed instead of a callable.

        Example:

            def on_load(task, result):
                pass

            task.call(
                load,
                args=id,
                on_success=on_load,
            )

            This will call the load function, followed by on_load if the load
            function completes sucessfully.
        """

        def cb(rc, result):
            if rc == 0:
                _callback(self, fn, result, on_success, on_none)
            else:
                _callback_error(self, fn, result, on_error, on_timeout)

        if args is None:
            args = ()
        elif not isinstance(args, (tuple, list)):
            args = (args,)

        if kwargs is None:
            kwargs = {}

        has_task = inspect_parameters(fn, kwargs)
        if has_task:
            self._callback.append(cb)
            callback = self
        else:
            callback = cb

        log.debug('task.call cid=%s fn=%s %s', self.cid, fn,
                  'as task' if has_task else '')
        fn(callback, *args, **kwargs)
        return self

    def defer(self, task_cmd, partial_callback, final_fn=None):
        # DEPRECATED: use call
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
        # DEPRECATED
        self.respond(message, 1)

    def respond(self, result, rc=0):
        # DEPRECATED: use callback
        if self.is_done:
            return
        if self.final:
            try:
                self.final()
            except Exception as e:
                log.warning('failure running task final: %s', str(e))
        self.callback(rc, result)


def unpartial(partial):
    """ turn a partial into a callback_fn

        undo the badness
    """
    def _unpartial(cb, *args, **kwargs):
        return partial(*args, **kwargs)(cb)

    return _unpartial


def inspect_parameters(fn, kwargs):

    task = False

    # get a list of function parameters
    args = inspect.getargspec(fn).args

    # is the first parameter named 'task'
    if len(args) and args[0] == 'task':
        task = True

    return task


def catch_exceptions(message):
    def _catch_exceptions(task_handler):
        def inner(task, *args, **kwargs):
            try:
                return task_handler(task, *args, **kwargs)
            except Exception:
                log.exception(message)
        return inner
    return _catch_exceptions


def _callback(task, fn, result, on_success, on_none):
    if on_none and result is None:
        try:
            log.debug('task.callback, cid=%s, on_none fn=%s', task.cid, on_none)
            return on_none(task, result)
        except Exception as e:
            return task.callback(1, 'exception during on_none: %s' % e)
    if on_success:
        try:
            log.debug('task.callback, cid=%s, on_success fn=%s', task.cid, on_success)
            return on_success(task, result)
        except Exception as e:
            return task.callback(1, 'exception during on_success: %s' % e)
    log.debug('task.callback, cid=%s, default success callback', task.cid)
    task.callback(0, result)


def _callback_error(task, fn, result, on_error, on_timeout):
    if on_timeout and result == 'timeout':
        try:
            log.debug('task.callback, cid=%s, on_timeout fn=%s', task.cid, on_timeout)
            return on_timeout(task, result)
        except Exception as e:
            return task.callback(1, 'exception during on_timeout: %s' % e)
    if on_error:
        try:
            log.debug('task.callback, cid=%s, on_error fn=%s', task.cid, on_error)
            return on_error(task, result)
        except Exception as e:
            return task.callback(1, 'exception during on_error: %s' % e)
    log.debug('task.callback, cid=%s, default error callback', task.cid)
    task.callback(1, result)


#
# STOP USING THIS defer-able STUFF
#


def wrap(callback_cmd, *args, **kwargs):
    # DEPRECATED yucky complexity
    ''' helper function callback_cmd -> partially executed partial '''
    return partial(callback_cmd)(*args, **kwargs)


def from_callback(task_cmd):
    # DEPRECATED yucky complexity
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
    # DEPRECATED yucky complexity
    def _args(*args, **kwargs):
        def _callback(callback_fn):
            task = Task(callback_fn)
            fn(task, *args, **kwargs)
            return task
        return _callback
    return _args
