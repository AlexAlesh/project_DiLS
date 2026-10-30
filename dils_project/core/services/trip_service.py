"""
Бизнес-логика работы с заявками и рейсами.
"""

from contextlib import contextmanager

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

    # Для новой заявки (без pk) пересчет на этом этапе невозможен —
    # форма сохранит Trip с дефолтным статусом, финальный пересчет
    # выполнится ниже после досоздания рейсов.
    if trip.pk:
        trip.refresh_status(save=False)

    # Передаем сохраненный экземпляр обратно в форму и вызываем ее save():
    # форма сохранит Trip (одним UPDATE, уже с актуальным статусом)
    # и выполнит досоздание/удаление TripLeg.
    form.instance = trip
    with suppress_trip_refresh():
        trip = form.save()

    trip.refresh_status()
    return trip


@transaction.atomic
def save_logist_part(leg, form):
    """Сохраняет часть рейса (поля логиста).

    Статус заявки пересчитывает TripLeg.save() — здесь повторного
    сохранения leg не требуется.
    """
    instance = form.save(commit=False)
    for field in LOGIST_FIELDS:
        setattr(leg, field, getattr(instance, field))
    leg.save()
    return leg


# ============================================================
# Прочее
# ============================================================

@contextmanager
def suppress_trip_refresh():
    """Временно подавляет каскадный пересчет статуса Trip при save/delete TripLeg.

    Используется, когда вызывающий код сам пересчитывает статус одним
    UPDATE после всех изменений (см. save_manager_part), чтобы не плодить
    лишние записи в БД.
    """
    original_save = TripLeg.save
    original_delete = TripLeg.delete

    def silent_save(self, *args, **kwargs):
        kwargs['_skip_trip_refresh'] = True
        original_save(self, *args, **kwargs)

    def silent_delete(self, *args, **kwargs):
        kwargs['_skip_trip_refresh'] = True
        original_delete(self, *args, **kwargs)

    TripLeg.save = silent_save
    TripLeg.delete = silent_delete
    try:
        yield
    finally:
        TripLeg.save = original_save
        TripLeg.delete = original_delete


def mark_as_viewed(leg: TripLeg) -> None:
    """Помечает рейс как просмотренный логистом."""
    if not leg.logist_viewed:
        leg.logist_viewed = True
        # Флаг просмотра не влияет на статус — пересчет не нужен.
        leg.save(update_fields=["logist_viewed"], _skip_trip_refresh=True)