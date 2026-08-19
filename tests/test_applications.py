from tout_pris.asgi import application as asgi_application
from tout_pris.wsgi import application as wsgi_application


def test_the_wsgi_application_is_callable():
    assert callable(wsgi_application)


def test_the_asgi_application_is_callable():
    assert callable(asgi_application)
