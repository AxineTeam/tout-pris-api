from django.middleware.locale import LocaleMiddleware as DjangoLocaleMiddleware
from django.utils import translation
from django.utils.cache import patch_vary_headers


class LocaleMiddleware(DjangoLocaleMiddleware):
    def process_request(self, request):
        if request.user.is_authenticated:
            translation.activate(request.user.language)
            request.LANGUAGE_CODE = translation.get_language()
        else:
            super().process_request(request)

    def process_response(self, request, response):
        patch_vary_headers(response, ("Accept-Language", "Cookie"))
        response.headers.setdefault("Content-Language", translation.get_language())
        return response
