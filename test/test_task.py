import pytest

import rhc.task as task


@pytest.fixture
def happy():
    def cb(rc, result):
        assert rc == 0
    return task.Task(cb)


@pytest.fixture
def not_happy():
    def cb(rc, result):
        assert rc != 0
    return task.Task(cb)


def test_simple(happy):
    happy.respond('yay')


def test_error(not_happy):
    not_happy.error('boo')


def task_cmd(task, result):
    task.worked = True


def partial_happy(cb):
    cb(0, 'yay')


def partial_not_happy(cb):
    cb(1, 'boo')


def test_defer(happy):
    happy.worked = False
    happy.defer(task_cmd, partial_happy)
    assert happy.worked


def test_final(happy):
    final = {'answer': False}
    def f():
        final['answer'] = True
    happy.defer(task_cmd, partial_happy)
    assert final['answer'] is False
    happy.defer(task_cmd, partial_happy, final_fn=f)
    assert final['answer'] is True
