import asyncio
import threading

from django.http import HttpResponse
from django.test import override_settings
from django.urls import path

from tout_pris.asgi import application as asgi_application
from tout_pris.wsgi import application as wsgi_application


def report_serving_thread(request):
    return HttpResponse(threading.current_thread().name)


urlpatterns = [path("serving-thread/", report_serving_thread)]


def serve(path, headers=()):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver"), *headers],
        "client": ("127.0.0.1", 0),
        "server": ("testserver", 80),
    }
    messages = []
    body_sent = False

    async def receive():
        nonlocal body_sent
        if body_sent:
            await asyncio.Event().wait()
        body_sent = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(asgi_application(scope, receive, send))

    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    return start["status"], {key.decode(): value.decode() for key, value in start["headers"]}, body


def test_the_wsgi_application_is_callable():
    assert callable(wsgi_application)


def test_the_asgi_application_serves_a_request(db):
    status, _, body = serve("/api/health/")

    assert status == 200
    assert b'"status":"ok"' in body


def test_the_asgi_application_negotiates_the_language_of_the_request(db):
    status, headers, _ = serve("/api/health/", headers=[(b"accept-language", b"fr")])

    assert status == 200
    assert headers["Content-Language"] == "fr"


@override_settings(ROOT_URLCONF=__name__)
def test_the_asgi_application_gives_each_request_its_own_thread(db):
    _, _, first = serve("/serving-thread/")
    _, _, second = serve("/serving-thread/")

    assert first != threading.current_thread().name.encode()
    assert first != second
