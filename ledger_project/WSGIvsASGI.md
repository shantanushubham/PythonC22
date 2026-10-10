# WSGI vs ASGI

## WSGI

WSGI is a Python standard for web servers and web applications. It is a simple and lightweight interface for web servers to interact with web applications.

## ASGI

ASGI is a Python standard for web servers and web applications. It is a more modern and flexible interface for web servers to interact with web applications.

## WSGI vs ASGI in Django

Both are interfaces between your Django application and a web server.

| Feature | WSGI | ASGI |
| :--- | :--- | :--- |
| **Full form** | Web Server Gateway Interface | Asynchronous Server Gateway Interface |
| **Execution model** | Primarily synchronous | Synchronous and asynchronous |
| **HTTP requests** | Yes | Yes |
| **Async Django views** | Can run them, but with limitations | Supports them natively |
| **WebSockets** | Not natively supported | Supported with appropriate ASGI components |
| **Common server** | Gunicorn | Uvicorn, Daphne |
| **Typical use case** | Traditional Django applications | Async APIs, WebSockets, real-time applications |


The key difference: WSGI is designed around synchronous request handling, while ASGI supports asynchronous request handling and protocols such as WebSockets.

For example, imagine your Django API needs to call three external services.

* With synchronous code, the request generally waits for each call to finish.
* With asynchronous code, the application can await multiple I/O operations concurrently.

ASGI allows Django to take advantage of asynchronous request handling. However, simply switching to ASGI doesn’t automatically make your entire application asynchronous.