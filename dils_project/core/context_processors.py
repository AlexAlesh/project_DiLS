from .models import Trip, TripLeg, UserPreferences

def notifications(request):
    ctx = {"new_requests_count": 0, "prefs": None}
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return ctx

    try:
        ctx["prefs"] = UserPreferences.get_for_user(user)
    except Exception:
        ctx["prefs"] = None

    if getattr(user, "is_logist", False) or getattr(user, "is_admin_role", False):
        try:
            # Считаем непросмотренные РЕЙСЫ (TripLeg)
            ctx["new_requests_count"] = TripLeg.objects.filter(
                trip__status=Trip.STATUS_SENT_TO_WORK,
                logist_viewed=False,
            ).count()
        except Exception:
            ctx["new_requests_count"] = 0

    return ctx