"""
Бизнес-логика работы с заявками и рейсами.
"""

from django.db import transaction
from ..models import Trip, TripLeg


# ============================================================
# QuerySet
# ============================================================

def trips_base_queryset():
    """Базовый QuerySet заявок (для менеджера)."""
    return Trip.objects.select_related(
        "manager", "customer"
    ).prefetch_related(
        "legs__transport_company", "legs__driver", "legs__vehicle", "legs__payment_type"
    )

def legs_base_queryset():
    """Базовый QuerySet рейсов (для логиста)."""
    return TripLeg.objects.select_related(
        "trip", "trip__manager", "trip__customer",
        "transport_company", "driver", "vehicle",
        "vehicle__brand", "vehicle__vehicle_type", "payment_type"
    )


# ============================================================
# Права
# ============================================================

def can_edit_as_manager(user, trip) -> bool:
    if user.is_admin_role: return True
    if not user.is_manager: return False
    return trip.manager_id is None or trip.manager_id == user.pk

def can_edit_as_logist(user, leg) -> bool:
    return user.is_admin_role or user.is_logist


# ============================================================
# Сохранение
# ============================================================

MANAGER_FIELDS = (
    "loading_date", "unloading_date", "customer", "delivery_info", "trips_count"
)

LOGIST_FIELDS = (
    "transport_company", "driver", "vehicle", "price", "payment_type", "ttn_number", "logist_comment"
)


@transaction.atomic
def save_manager_part(trip, form, manager=None):
    """Сохраняет часть менеджера (и автосоздает пустые рейсы)."""
    instance = form.save(commit=False)

    if trip is None:
        trip = instance
        if manager and not trip.manager_id:
            trip.manager = manager
    else:
        for field in MANAGER_FIELDS:
            setattr(trip, field, getattr(instance, field))

    trip.save()

    # Передаем сохраненный экземпляр обратно в форму и вызываем ее save(),
    # чтобы сработала логика досоздания TripLeg (рейсов).
    form.instance = trip
    form.save()

    return trip


@transaction.atomic
def save_logist_part(leg, form):
    """Сохраняет часть логиста (поля рейса)."""
    instance = form.save(commit=False)
    for field in LOGIST_FIELDS:
        setattr(leg, field, getattr(instance, field))
    leg.save()
    return leg


# ============================================================
# Прочее
# ============================================================

def mark_as_viewed(leg: TripLeg) -> None:
    """Помечает рейс как просмотренный логистом."""
    if not leg.logist_viewed:
        leg.logist_viewed = True
        leg.save(update_fields=["logist_viewed"])