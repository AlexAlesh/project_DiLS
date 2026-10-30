"""
Middleware: пробрасывает текущего пользователя в thread-local,
чтобы сигналы (core/signals.py) могли писать его в TripHistory.
"""

from .signals import set_current_user


class CurrentUserMiddleware:
    """
    Кладёт request.user в thread-local на время запроса.
    Используется в сигналах через get_current_user().

    Важно: для анонимных запросов кладём None, а не AnonymousUser —
    иначе TripHistory.objects.create(user=...) упадёт на ForeignKey.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and not getattr(user, "is_authenticated", False):
            user = None
        set_current_user(user)

        try:
            response = self.get_response(request)
        finally:
            # Чистим, чтобы не утекало между запросами одного потока
            set_current_user(None)
        return response