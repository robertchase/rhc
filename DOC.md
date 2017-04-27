# rhc
a microservice framework


### A simple REST service

Here is a rather useless ping server. It accepts `GET /test/ping` and responds with `{"ping": "pong"}`.

Create a file named `micro` with the following contents (you can exclude the comments if you want):

```
SERVER useless 12345   # listen on 12345
    ROUTE /test/ping$  # match HTTP resource=/test/ping
        GET ping.ping  # match method=GET, call the ping function in ping.py
```

Create ping.py:

```python
def ping(request):
    return {'ping': 'pong'}
```

Start the REST server:

```
> export PYTHONPATH=path_to_rhc
> python -m rhc.micro
```

You should see something like this:

```
INFO:__main__:listening on useless port 12345
```

which tells you that a service named `useless` is listening on port 12345. We can test it by opening another terminal and curling the /test/ping resource:

```
> curl localhost:12345/test/ping
```

You should see the response:

```
{"ping": "pong"}
```

### Configuration instead of code

The above example could also be written without the micro file by writing calls to code in `rhc`'s libraries. The code would not be as straightforward, would be difficult to maintain as the service grew in complexity, and would become increasingly repetitive.
