"""Makes the request's user available to model code, so every change is attributed."""
from contextvars import ContextVar

_current_user = ContextVar("qms_current_user", default=None)


def get_current_user():
    return _current_user.get()


def set_current_user(user):
    return _current_user.set(user)


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _current_user.set(getattr(request, "user", None))
        try:
            return self.get_response(request)
        finally:
            _current_user.reset(token)
