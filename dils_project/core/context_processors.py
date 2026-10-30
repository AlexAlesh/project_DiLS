"""Context-процессоры DiLS."""

from .models import Trip, TripLeg, UserPreferences


def notifications(request):
    """Счётчик непросмотренных рейсов и пользовательские настройки для base.html."""
    ctx = {"new_legs_count": 0, "prefs": None}
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return ctx

    ctx["prefs"] = UserPreferences.get_for_user(user)

    if getattr(user, "is_logist", False) or getattr(user, "is_admin_role", False):
        # Непросмотренные логистом рейсы (TripLeg) в статусе «в работе».
        ctx["new_legs_count"] = TripLeg.objects.filter(
            trip__status=Trip.STATUS_SENT_TO_WORK,
            logist_viewed=False,
        ).count()

    return ctx