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
import datetime
import heapq
import time


import logging
log = logging.getLogger(__name__)


class Timer(object):
    '''
    The python library threading.Timer provides a timer which runs in a separate
    thread. This class provides a same-thread timer function which can be
    serviced periodically, using the service method.

    Add new timers with an add* method. A timer will not start running until its
    start method is called. The granularity of the timing function will not
    exceed the frequency of the calls to the service method.

    A timer has four methods:

        start    - start the timer. the timer will run for a set duration after
                   which the action routine is executed.  when a timer is running,
                   you cannot call the start method again; use re_start instead.
                   after a timer has expired or is canceled, it can be started
                   again.

                   the start method returns self, allowing constructs like:

                       my_timer = t.add(act, dur).start()

        re_start - re-start any timer, running or not.

        expire   - expire a running timer, causing the action routine to execute
                   on the next call to the timer service routine.

        cancel   - expire a running timer without executing the action routine.

        delete   - same as cancel (for backward compatablity)
    '''

    def __init__(self):
        self._list = []  # manage list with heapq so that first timer is always the smallest

    def __repr__(self):
        return str(self._list)

    def __len__(self):
        return len(self._list)

    def service(self):
        while len(self) and self._list[0].is_expired:  # handle all expired timers
            item = heapq.heappop(self._list)  # grabs the smallest expiration (per SimpleTimer.__lt__)
            item._is_in_heap = False  # Note: expired timers are removed from the timer list; start() will re-insert
            item.execute()

    def add(self, action, duration, **kwargs):
        '''
            Add a simple fixed-duration timer.

            Parameters:
                duration - time, in ms, that the timer runs
                action - code to execute when timer expires
                kwargs - ignored (for backward compatability)
            Return    :
                unstarted Timer instance

            This method can be called with action and duration
            flipped in order to support the old-style signature.
        '''
        if isinstance(action, (int, float)):
            action, duration = duration, action
        return SimpleTimer(self._list, action, duration)

    def add_backoff(self, action, initial, maximum, multiplier=2):
        '''
            Create a timer that increases in duration with each start.

            Parameters:
                action - code to execute when timer expires
                initial - initial timer duraction, in ms
                maximum - maximum timer duration
                multiplier - factor by which duration increases
                             with each call to the start method.
            Return    :
                unstarted Timer instance

            The re_start method will cause the duration to return to
            the initial value.
        '''
        return BackoffTimer(self._list, action, initial, maximum, multiplier)

    def add_hourly(self, action):
        '''
            Run an action once an hour on the hour

            Parameters:
                action - code to execute when timer expires
            Return    :
                unstarted Timer instance
        '''
        return HourlyTimer(self._list, action)


class SimpleTimer(object):

    def __init__(self, timer_list, action, duration):
        self._timer_list = timer_list
        self._action = action
        self._duration = duration

        self._is_in_heap = False
        self._is_restarting = False
        self._expiration = 0
        self.is_running = False

    def __repr__(self):
        return 'Simple[d=%s, r=%s]' % (self._duration, (self._expiration - time.time()) * 1000.0)

    def __eq__(self, other):
        return self._expiration == other._expiration

    def __lt__(self, other):
        return self._expiration < other._expiration

    def _calc_expiration(self):
        return time.time() + (self._duration / 1000.0)

    @property
    def is_expired(self):
        return self._expiration < time.time()

    def set_action(self, action):
        self._action = action

    def start(self):
        if self.is_running:
            raise Exception("can't start a running timer")
        self._expiration = self._calc_expiration()
        self.is_running = True
        if self._is_in_heap:
            heapq.heapify(self._timer_list)
        else:
            heapq.heappush(self._timer_list, self)
            self._is_in_heap = True
        return self

    def re_start(self):
        if self.is_running:
            self.is_running = False
        self._is_restarting = True
        self.start()
        self._is_restarting = False

    def cancel(self):
        if self.is_running:
            self.is_running = False
            self._expiration = 0

    def expire(self):
        if self.is_running:
            self._expiration = time.time() - 5
            heapq.heapify(self._timer_list)

    def delete(self):  # for backward compatibility
        self.cancel()

    def execute(self):
        if self.is_running:
            self.is_running = False
            try:
                self._action()
            except Exception:
                log.exception('error running timer action')


class BackoffTimer(SimpleTimer):

    def __init__(self, timer_list, action, initial, maximum, multiplier):
        super(BackoffTimer, self).__init__(timer_list, action, initial)
        self._backoff_duration = None
        self._maximum = maximum
        self._multiplier = multiplier

    def __repr__(self):
        return 'Backoff[d=%s, r=%s]' % (self._backoff_duration, (self._expiration - time.time()) * 1000.0)

    def _calc_expiration(self):
        if self._backoff_duration is None or self._is_restarting:
            self._backoff_duration = self._duration
        else:
            self._backoff_duration *= self._multiplier
            if self._backoff_duration > self._maximum:
                self._backoff_duration = self._maximum
        return time.time() + (self._backoff_duration / 1000.0)


class HourlyTimer(SimpleTimer):

    def __init__(self, timer_list, action):
        super(HourlyTimer, self).__init__(timer_list, action, None)

    def __repr__(self):
        r = self._expiration - time.time()
        rm = int(r / 60)
        rs = int((r - rm * 60) * 1000.0) / 1000.0
        return 'Hourly[r=%s:%06.3f]' % (rm, rs)

    def _calc_expiration(self):
        now = datetime.datetime.now()
        next_hour = datetime.datetime(now.year, now.month, now.day, now.hour) + datetime.timedelta(hours=1)
        self._duration = (next_hour - now).total_seconds() * 1000.0
        return time.time() + (self._duration / 1000.0)


TIMERS = Timer()
