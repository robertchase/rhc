import pytest

import rhc.task as rhc_task


def happy(callback):
    callback(0, 'yay')


def on_happy(task, result):
    assert result == 'yay'
    task.callback(0, result)


def happy_none(callback):
    callback(0, None)


def on_happy_none(task, result):
    assert result is None
    task.callback(0, result)


def unhappy(callback):
    callback(1, 'boo')


def on_unhappy(task, result):
    assert result == 'boo'
    task.callback(0, result)


@pytest.fixture
def _task():

    def done(rc, result):
        t.worked = True

    t = rhc_task.Task(done)
    t.worked = False
    yield t
    assert t.worked


def test_success(_task):
    _task.call(
        happy,
        on_success=on_happy,
    )


def test_none(_task):
    _task.call(
        happy_none,
        on_success=on_happy,
        on_none=on_happy_none,
    )


def test_error(_task):
    _task.call(
        unhappy,
        on_success=on_happy,
        on_none=on_happy_none,
        on_error=on_unhappy,
    )


def task_callback(task):
    assert isinstance(task, rhc_task.Task)
    task.callback(0, 'task_callback')


def test_task_callback(_task):

    def on_success(task, result):
        assert result == 'task_callback'
        task.callback(0, result)

    _task.call(
        task_callback,
        on_success=on_success,
    )


def test_task_persist(_task):
    """ show that the task object is the same throughout """

    _task.on_success = False  # start False

    def on_success(task, result):
        task.on_success = True  # change to True in success function
        task.callback(0, result)

    _task.call(
        task_callback,
        on_success=on_success,
    )

    assert _task.on_success  # still True out here (same object)
