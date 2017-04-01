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


class Timers(object):
    '''
    The python library threading.Timer provides a timer which runs in a separate
    thread. These classes provide a same-thread timer function which can be
    serviced periodically, using the service method.

    Using the TIMERS singleton, add new timers with an add* method. A
    timer will not start counting down until its start method is called. The
    granularity of the timing function will not exceed the frequency of the calls
    to the service method.

    A timer has five methods:

        start    - start the timer. the timer will run for a set duration after
                   which the action routine is executed.  when a timer is running,
                   you cannot call the start method again; use re_start instead.
                   after a timer has expired, it can be started again.

        re_start - re-start any timer, running or not.

        expire   - expire a running timer, causing the action routine to execute
                   on the next call to the timer service routine.

        cancel   - expire a running timer without executing the action routine.

        delete   - same as cancel (for backward compatibility)
    '''

    def __init__(self):
        self.__list = []

    def __repr__(self):
        return str(self.__list)

    def __len__(self):
        return len(self.__list)

    def service(self):
        while len(self) and self.__list[0].is_expired:
            item = heapq.heappop(self.__list)  # grabs the smallest expiration (per _timer.__lt__)
            item.is_in_heap = False  # Note: expired timers are removed from the timer list; start() will re-insert
            item.execute()

    def add(self, action, duration, onetime=None):  # onetime is ignored; present for backward compatibility
        '''
            Add a simple fixed-duration timer.

            Parameters:
                duration - time, in ms, that the timer runs
                action - code to execute when timer expires
            Return    :
                unstarted Timer instance
        '''

        # --- handle deprecated (duration, action) call signature
        if callable(duration):
            action, duration = duration, action

        return self._wrap(Timer(action, duration))

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
        return self._wrap(BackoffTimer(action, initial, maximum, multiplier))

    def add_hourly(self, action):
        '''
            Run an action once an hour on the hour

            Parameters:
                action - code to execute when timer expires
            Return    :
                unstarted Timer instance
        '''
        return self._wrap(HourlyTimer(action))

    def _wrap(self, timer):
        wrapped = _timer(timer, self._on_start)
        wrapped.is_in_heap = False
        return timer

    def _on_start(self, item):
        if item.is_in_heap:
            self.__list.sort()
        else:
            heapq.heappush(self.__list, item)
            item.is_in_heap = True


TIMERS = Timers()


class Timer(object):

    def __init__(self, action, duration):
        self.action = action
        self.duration = duration

    def get_duration(self):
        return self.duration


class BackoffTimer(object):

    def __init__(self, action, initial, maximum, multiplier):
        self.action = action
        self.__initial = initial
        self.duration = None
        self.__maximum = maximum
        self.__multiplier = multiplier

    def get_duration(self):
        if self.duration is None or self.is_restarting:
            self.duration = self.__initial
        else:
            self.duration *= self.__multiplier
            if self.duration > self.__maximum:
                self.duration = self.__maximum

        return self.duration


class HourlyTimer(object):

    def __init__(self, action):
        self.action = action
        self.duration = None

    def get_duration(self):
        now = datetime.datetime.now()
        next_hour = datetime.datetime(now.year, now.month, now.day, now.hour) + datetime.timedelta(hours=1)
        self.duration = (next_hour - now).total_seconds() * 1000
        return self.duration


class _timer(object):

    def __init__(self, timer, on_start):
        self.timer = timer
        self.on_start = on_start
        self.expiration = 0
        self.running = False

        # --- decorate the timer with some of our methods
        timer.start = self.start
        timer.re_start = self.re_start
        timer.cancel = self.cancel
        timer.delete = self.cancel
        timer.expire = self.expire

        # --- flag for differentiating between restart and start; useful in get_duration
        timer.is_restarting = False

    def __repr__(self):
        return '_timer[d=%s, r=%s]' % (self.timer.duration, (self.expiration - time.time()) * 1000)

    def __eq__(self, other):
        return self.expiration == other.expiration

    def __lt__(self, other):
        return self.expiration < other.expiration

    def start(self):
        if self.running:
            raise Exception("can't start a running timer")
        self.running = True
        self.expiration = time.time() + (self.timer.get_duration() / 1000.0)
        self.on_start(self)
        return self.timer

    @property
    def is_expired(self):
        return self.expiration < time.time()

    def re_start(self):
        self.running = False
        self.timer.is_restarting = True
        self.start()
        self.timer.is_restarting = False

    def cancel(self):
        if self.running:
            self.running = False
            self.expiration = 0

    def expire(self):
        if self.running:
            self.expiration = time.time() - 5

    def execute(self):
        if self.running:
            self.running = False
            try:
                self.timer.action()
            except Exception:
                log.exception('error running timer action')


if __name__ == '__main__':

    class action(object):

        def __init__(self, id):
            self.id = id

        def act(self):
            print 'pop %s' % self.id,
            print TIMERS

    print TIMERS
    i0 = TIMERS.add_hourly(action('H').act).start()
    print TIMERS
    i1 = TIMERS.add(action(10).act, 10000).start()
    print TIMERS
    i2 = TIMERS.add(action(7).act, 7000).start()
    print TIMERS
    i3 = TIMERS.add(action(2).act, 2000).start()
    print TIMERS
    i4 = TIMERS.add(5000, action(5).act).start()
    print TIMERS
    i2.cancel()
    print TIMERS
    while len(TIMERS):
        time.sleep(1)
        TIMERS.service()
