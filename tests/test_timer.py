import time

import rhc.timer as timer


class Action(object):

    def __init__(self):
        self.t1 = False
        self.t2 = False

    def a1(self):
        self.t1 = True

    def a2(self):
        self.t2 = True


def test_no_start():
    t = timer.Timer()
    a = Action()
    t.add(a.a1, 15)
    t.add(a.a2, 10)
    assert len(t) == 0
    time.sleep(.02)
    t.service()
    assert a.t1 is False
    assert a.t2 is False


def test_start_one():
    t = timer.Timer()
    a = Action()
    t.add(a.a1, 15).start()
    t.add(a.a2, 10)
    assert len(t) == 1
    time.sleep(.02)
    t.service()
    assert a.t1 is True
    assert a.t2 is False


def test_start_all():
    t = timer.Timer()
    a = Action()
    t.add(a.a1, 15).start()
    t.add(a.a2, 10).start()
    assert len(t) == 2
    time.sleep(.02)
    t.service()
    assert a.t1 is True
    assert a.t2 is True


def test_start_restart():
    t = timer.Timer()
    a = Action()
    t.add(a.a1, 10).start()
    t2 = t.add(a.a2, 20).start()
    time.sleep(.015)
    t.service()
    assert a.t1 is True
    assert a.t2 is False
    t2.re_start()
    time.sleep(.015)
    t.service()
    assert a.t1 is True
    assert a.t2 is False


def test_start_cancel():
    t = timer.Timer()
    a = Action()
    t.add(a.a1, 10).start()
    t2 = t.add(a.a2, 20).start()
    time.sleep(.015)
    t.service()
    assert a.t1 is True
    assert a.t2 is False
    t2.cancel()
    assert len(t) == 1
    time.sleep(.01)
    t.service()
    assert len(t) == 0
    assert a.t1 is True
    assert a.t2 is False


class ActionBackoff(object):

    def __init__(self):
        self.c1 = 0

    def a1(self):
        self.c1 += 1


def test_backoff():
    t = timer.Timer()
    a = ActionBackoff()
    t1 = t.add_backoff(a.a1, 10, 30, 2).start()
    time.sleep(.015)
    t.service()
    assert a.c1 == 1
    t1.start()
    time.sleep(.01)
    t.service()
    assert a.c1 == 1
    time.sleep(.02)
    t.service()
    assert a.c1 == 2
    t1.start()
    time.sleep(.021)
    t.service()
    assert a.c1 == 2
    time.sleep(.01)
    t.service()
    assert a.c1 == 3
