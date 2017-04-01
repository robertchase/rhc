import json
import pytest
from rhc.resthandler import RESTRequest, content_to_json


@pytest.fixture
def request():

    class Request(RESTRequest):
        def __init__(self):
            self.http_content = ''
            self.http_query = {}

        def respond(self, result):
            self.result = result

    return Request()


@content_to_json()
def rest1(handler):
    return handler.json['this']


@content_to_json('a')
def rest2(handler, a):
    return a


@content_to_json(('a', int), 'b')
def rest3(handler, a, b):
    return a + 1, b


def test_json_content(request):
    request.http_content = json.dumps(dict(this='is', a='test'))
    assert rest1(request) == 'is'
    assert rest2(request) == 'test'


def test_json_form(request):
    request.http_content = 'this=is&a=test'
    assert rest1(request) == 'is'
    assert rest2(request) == 'test'


def test_json_bad(request):
    assert rest2(request) is None
    assert request.result.code == 400
    assert request.result.content == "Missing required key: 'a'"


def test_json_type(request):
    request.http_content = json.dumps(dict(a='1', b='2'))
    a, b = rest3(request)
    assert a == 2
    assert b == '2'
