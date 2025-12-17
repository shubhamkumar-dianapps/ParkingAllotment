from django.http import Http404
from django.shortcuts import render


class ExceptionHandlingMiddleware:
    """Middleware to catch uncaught exceptions and render friendly pages.

    - Http404 is re-raised so Django's 404 handler is used.
    - Other exceptions render `500.html` with status 500.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Http404:
            # Let Django (and our handler404) handle Http404
            raise
        except Exception:
            # For any other unhandled exception, render a friendly 500 page
            return render(request, "500.html", status=500)
