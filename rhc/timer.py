'''
The MIT License (MIT)

Copyright (c) 2013-2015 Robert H Chase

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
import time
'''
  The python library threading.Timer provides a timer which runs in a separate
  thread. These classes provide a same-thread timer function which is
  serviced in a loop.

  To use, create a Timers instance, adding new timers with the add method. A
  timer will not start until its start method is called. The granularity of
  the timing function will not exceed the frequency of the service method calls.
'''


class Timer (object):

    def __init__(self, duration, action, is_onetime=False):
        self._duration = duration
        self.__action = action
        self.__is_onetime = is_onetime
        self.__expire = None
        self.is_running = False
        self.is_deleted = False

    def start(self):
        if self.is_deleted:
            raise Exception('timer is deleted')
        if self.is_running:
            raise Exception('timer is already running')
        self.is_running = True
        self.__expire = time.time() + (self._duration / 1000.0)
        return self

    def re_start(self):
        self.is_running = False
        self.start()

    def cancel(self):
        if self.is_running:
            elapsed = self.__expire - time.time()
        else:
            elapsed = 0
        self.is_running = False
        if self.__is_onetime:
            self.is_deleted = True
        return elapsed

    def expire(self):
        if self.is_running:
            self.__expire = time.time() - 5

    def delete(self):
        self.is_running = False
        self.is_deleted = True

    def test(self, current):
        if self.is_running:
            if current > self.__expire:
                self.cancel()
                self.__action()


class BackoffTimer (Timer):

    '''
      This is a variable duration timer which starts at an initial value and
      increases with each call to start by multiplying the current duration by
      a constant multiplier (default=2) until a maximum is reached. The timer
      can be reset to the inital value by calling re_start.
    '''
    def __init__(self, action, initial, maximum, multiplier=2):
        Timer.__init__(self, initial, action)
        self.__initial = initial
        self.__maximum = maximum
        self.__multiplier = multiplier

    def start(self):
        Timer.start(self)
        if self._duration < self.__maximum:
            self._duration *= self.__multiplier
            if self._duration > self.__maximum:
                self._duration = self.__maximum
        return self

    def re_start(self):
        self._duration = self.__initial
        Timer.re_start(self)


class HourlyTimer(Timer):

    def __init__(self, action):
        Timer.__init__(self, 0, action)

    @staticmethod
    def next_hour():
        now = datetime.datetime.now()
        next_hour = datetime.datetime(now.year, now.month, now.day, now.hour) + datetime.timedelta(hours=1)
        return (next_hour - now).total_seconds()

    def start(self):
        self._duration = self.next_hour() * 1000
        return Timer.start(self)

    def re_start(self):
        self._duration = self.next_hour() * 1000
        Timer.re_start(self)


class Timers(object):

    def __init__(self):
        self.__timers = []

    def service(self):
        current = time.time()
        for timer in self.__timers[::-1]:  # reverse allows safe removal
            timer.test(current)
            if timer.is_deleted:
                self.__timers.remove(timer)

    def add(self, duration, action, onetime=False):
        '''
          Parameters: duration - time, in ms, that the timer runs
                      action - code to execute when timer expires
                      is_onetime - see below
          Return    : unstarted Timer instance

          A onetime timer will be purged when it is canceled or expired; otherwise,
          the timer will remain in the timer list until explicitly deleted.
        '''
        timer = Timer(duration, action, onetime)
        self.__timers.append(timer)
        return timer

    def add_backoff(self, action, initial, maximum, multiplier=2):
        ''' see description of BackoffTimer '''
        timer = BackoffTimer(action, initial, maximum, multiplier)
        self.__timers.append(timer)
        return timer

    def add_hourly(self, action):
        '''
            Run an action once an hour on the hour

            Parameters:
                action - code to execute when timer expires
            Return    :
                unstarted Timer instance
        '''
        timer = HourlyTimer(action)
        self.__timers.append(timer)
        return timer

TIMERS = Timers()
