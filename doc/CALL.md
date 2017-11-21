# CALL
## Using the *call* method for async operation

The `rhc.resthandler.RESTRequest` object
and the `rhc.task.Task` object
both support asynchronous operation
with a built-in `call` method.
This document describes `call` usage.

## request and task

A `request` is the first parameter supplied to a rest handler.
It carries all the data associated with the incoming http document, as well as
a number of methods for inspecting the data and responding to the
peer.
A `request` is always created by the framework.

A `task` is a decorated callback used to maintain continuity
through one or more asynchronous operations without carrying the notion
of `HTTP` or `REST` into the business logic.
A `task` is usually created by a `request.call` method, but
can be constructed manually.

A `request` should remain in the rest handler function, and a `task` should
be used in lower level logic for proper separation of responsibility.

## the callback function

A *callback function* has the following signature:
```
callback(rc, result)
```

where `rc` is the *return code* and `result` is the *response*.
On success, `rc` is set to zero; on failure, `rc` is non-zero and `result`
contains an error message.

Following this simple callback pattern allows for the implementation of
consistent logic around handing async activity.

## the async invocation

An *async callable function* has the following signature:
```
async_fn(callback, *args, **kwargs)
```

where `callback` is a *callback function*.

Upon completion,
usually after waiting for one or more non-blocking operations,
`async_fn` will call `callback` with the appropriate `rc` and `result`.

Following this simple invocation pattern allows for the implementation of
consistent logic around handing async activity.

## an example

Let's bring these ideas together in a brief example:

```
def my_handler(request, my_param):

    def on_done(rc, result):
        if rc == 0:
            request.respond(200, result)
        else:
            log.warning(result)
            request.respond(500)

    my_logic(on_done, my_param)
```

`my_logic` is an *async callable* function, taking `on_done` as its `callback`.
The result of this pattern is a whole lot of boilerplate code, checking `rc` and responding in one of a few ways.
Some of the management code can be swept away by using the `call` method on the
`request` object.
The purpose of the `call` method is to simplify this process by supplying a set of default actions for
typical situations. In this case, the use of `call` eliminates the `callback` entirely:

```
def my_handler(request, my_param):
    request.call(
        my_logic,
        args=my_param,
    )
```

The `call` method's default success action is to respond with the `result`;
the `call` method's default error action is to `log.warning` the `result` along with the request's
connection id and respond with a 500.

Here is one more example:

```
def my_handler(request, my_param):

    def my_success(request, result):
        request.respond({"data": result['my_field']})

    def request.call(
        my_logic,
        args=my_param,
        on_success=my_success,
    )
```

This shows an `on_success` parameter being specified. The `my_success` callable, and other
functions like it, take two parameters: `request` and `result`.
`request` is the same request object passed to `my_handler`, and `result` is the
return value from the `my_logic` callable.
The `call` method can pass control to a number of callables like `on_success`. Here is
the full signature:

## request call signature

```
call(
    async_callable,
    args=args,
    kwargs=kwargs,
    on_success=on_success_callable,
    on_success_code=status code to respond with on success,
    on_error=on_error_callable,
    on_none=on_none_callable,
    on_none_404=boolean (default=False),
)
```

##### parameters

`async_callable` - a callable taking a `callback` as the first parameter (required)

`args` - an argument or list of arguments to `async_callable`

`kwargs` - a dict of keyword arguments to `async_callable`

`on_success` - an `async callback` function called when `rc`==0 [Note 1]

`on_success_code` - the HTTP status code to use when `rc`==0

`on_error` - an `async callback` function called when `rc`!=0 [Note 2]

`on_none` - an `async callback` function called when `rc`==0 and `result` is None

`on_none_404` - if True, respond with HTTP status code 404 if `rc`==0 and `result` is None

##### notes

1. an `async callback` function takes two arguments: `request` and `result`

2. the `on_error` `result` is an error message

##### task handling

This is magic.

If the first parameter of an `async_callable`
method is *named* `task`, then an instance of
`rhc.task.Task` is passed to the callable.
Think of the `task` as a lightweight `request`, or as a heavyweight `callback`,
which isolates lower-level logic from any awareness of the HTTP `request`.

*For the curious*: the `call` method provides its own `callback function` that handles all the
special cases (like `on_success`, `on_error`, etc.).
If the first parameter is named `task`, by inspection, then `call`'s `callback function`
is wrapped in a `rhc.task.Task`.


### delay

The `delay` method signals to the framework not to respond immediately
after the rest handler completes.

Simple rest handlers will return a value, which is then
sent as a response.
During async handling, the response to the connection's peer is
delayed until all async activity is complete.

 The `call` method
automatically calls `delay`.

## task call signature

The `task`'s call signature is similar to that of `request`.

```
call(
    async_callable,
    args=args,
    kwargs=kwargs,
    on_success=on_success_callable,
    on_none=on_none_callable,
    on_error=on_error_callable,
    on_timeout=on_timeout_callable,
)
```

##### parameters

`async_callable` - a callable taking a `callback` as the first parameter (required)

`args` - an argument or list of arguments to `async_callable`

`kwargs` - a dict of keyword arguments to `async_callable`

`on_success` - an `async callback` function called when `rc`==0 [Note 1]

`on_none` - an `async callback` function called when `rc`==0 and `result` is None

`on_error` - an `async callback` function called when `rc`!=0 [Note 2]

`on_timeout` - an `async callback` function called with `rc`==` and `result` == 'timeout' [Note 4]


##### notes

1. an `async callback` function takes two arguments: `request` and `result`

2. the `on_error` `result` is an error message

3. the `task` instance used to make a call will be passed to each async_callable
which has *task* as the first parameter. Attributes can be assigned to the `task`
instance along the way to ease in the accumulation of response data.

4. `on_timeout` depends upon a a well-behaved and consistent `async_callable`.
Any operation using `rhc.connect` will fit this pattern.

##### task handling

See the `task handling` section for `request`.
