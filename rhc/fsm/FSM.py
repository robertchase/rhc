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
class STATE (object):

    def __init__(self, name, enter=None, exit=None):
        self.name = name
        self.events = {}
        self.enter = enter
        self.exit = exit

    def set_events(self, events):
        for event in events:
            self.events[event.name] = event


class EVENT (object):

    def __init__(self, name, actions, next_state=None):
        self.name = name
        self.actions = actions
        self.next_state = next_state


class FSM (object):

    def __init__(self, states):
        self.states = {}
        for state in states:
            self.states[state.name] = state
        self._state = None
        self.on_state_change = None
        self.trace = None
        self.undefined = None

    @property
    def state(self):
        return self._state.name

    @state.setter
    def state(self, state):
        self._state = self.states[state]

    def _handle(self, event):
        next_event = None

        for action in event.actions:
            next_event = action()

        if event.next_state:
            if self._state.exit:
                next_event = self._state.exit()

            if self.on_state_change:
                self.on_state_change(event.next_state.name, self._state.name)
            self._state = event.next_state

            if self._state.enter:
                next_event = self._state.enter()

        return next_event

    def handle(self, event):
        is_internal = False

        while event:
            is_default = False

            # --- locate event handler
            if event in self._state.events:
                state_event = self._state.events[event]

            # --- or default event handler
            elif 'default' in self._state.events:
                is_default = True
                state_event = self._state.events['default']

            # --- or oops
            else:
                state_event = None

            # --- trace
            if self.trace:
                self.trace(self._state.name, event, is_default, is_internal)

            # --- no event handler
            if not state_event:
                if self.undefined:
                    self.undefined(self._state.name, event, False, is_internal)
                return False  # event not handled!

            # --- handle, if non-null event is returned, keep going
            event = self._handle(state_event)
            is_internal = True  # every event after the first event is internal

        return True  # OK


if '__main__' == __name__:
    s_a = STATE('A')
    s_b = STATE('B')

    def a_1():
        print 'act 1'

    def a_2():
        print 'act 2'

    def trace(s, e, d, i):
        print 's=%s,e=%s,is_default=%s,is_internal=%s' % (s, e, d, i)

    def on_state_change(new, old):
        print 'state change from %s to %s' % (new, old)

    s_a.set_events([EVENT('A', [a_1], s_b)])
    s_b.set_events([EVENT('B', [a_2], s_a)])
    f = FSM([s_a, s_b])
    f.trace = trace
    f.on_state_change = on_state_change
    f.state = 'A'
    f.handle('A')
    f.handle('B')
