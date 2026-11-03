"""
Сигналы приложения core.
"""

import threading
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Trip, TripLeg, TripHistory, User, UserPreferences


_thread_locals = threading.local()

def set_current_user(user) -> None:
    _thread_locals.user = user

def get_current_user():
    return getattr(_thread_locals, "user", None)


# Отслеживаемые поля заявки (только менеджерские)
TRACKED_FIELDS = {
    "loading_date": "Дата загрузки",
    "unloading_date": "Дата разгрузки",
    "manager_id": "Менеджер",
    "customer_id": "Заказчик",
    "delivery_info": "Информация по доставке",
    "trips_count": "Количество рейсов",
}

_FK_ACCESSORS = {
    "manager_id": "manager",
    "customer_id": "customer",
}


def _resolve_display(instance, field_name: str, raw_value):
    if raw_value in (None, ""): return ""
    if field_name in _FK_ACCESSORS:
        accessor = _FK_ACCESSORS[field_name]
        related = getattr(instance, accessor, None)
        if related is None:
            model_field = Trip._meta.get_field(accessor)
            model = model_field.related_model
            try: related = model.objects.get(pk=raw_value)
            except model.DoesNotExist: return f"id={raw_value}"
        return str(related)
    return str(raw_value)


@receiver(pre_save, sender=Trip)
def trip_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_values = None
        instance._old_instance = None
        return
    try: old = Trip.objects.get(pk=instance.pk)
    except Trip.DoesNotExist:
        instance._old_values = None
        instance._old_instance = None
        return
    instance._old_instance = old
    instance._old_values = {field: getattr(old, field, None) for field in TRACKED_FIELDS}


@receiver(post_save, sender=Trip)
def trip_post_save(sender, instance, created, **kwargs):
    # Пересчёт служебного поля status (Trip.refresh_status) не должен
    # порождать записей в истории изменений менеджерских полей.
    if getattr(instance, '_skip_history', False):
        return

    user = get_current_user()

    if created:
        TripHistory.objects.create(
            trip=instance, user=user, field_name="__created__", old_value="", new_value="Заявка создана",
        )
        return

    old_values = getattr(instance, "_old_values", None)
    old_instance = getattr(instance, "_old_instance", None)
    if old_values is None or old_instance is None: return

    changes = []
    for field, label in TRACKED_FIELDS.items():
        old_raw = old_values.get(field)
        new_raw = getattr(instance, field, None)
        if old_raw != new_raw:
            changes.append({
                "label": label,
                "old": _resolve_display(old_instance, field, old_raw),
                "new": _resolve_display(instance, field, new_raw),
            })

    if not changes: return

    TripHistory.objects.bulk_create([
        TripHistory(trip=instance, user=user, field_name=ch["label"], old_value=ch["old"], new_value=ch["new"])
        for ch in changes
    ])


# Отслеживаемые поля рейса (логист) — для истории изменений.
LEG_TRACKED_FIELDS = {
    "transport_company_id": "Транспортная компания",
    "driver_id": "Водитель",
    "vehicle_id": "Машина",
    "price": "Цена",
    "payment_type_id": "Тип оплаты",
    "ttn_number": "№ ТТН",
    "logist_comment": "Комментарий логиста",
}

_LEG_FK_ACCESSORS = {
    "transport_company_id": "transport_company",
    "driver_id": "driver",
    "vehicle_id": "vehicle",
    "payment_type_id": "payment_type",
}


@receiver(pre_save, sender=TripLeg)
def leg_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_values = None
        instance._old_instance = None
        return
    try:
        old = TripLeg.objects.get(pk=instance.pk)
    except TripLeg.DoesNotExist:
        instance._old_values = None
        instance._old_instance = None
        return
    instance._old_instance = old
    instance._old_values = {field: getattr(old, field, None) for field in LEG_TRACKED_FIELDS}


def _leg_display(instance, field_name, raw_value):
    if raw_value in (None, ""):
        return ""
    if field_name == "price":
        return f"{raw_value} руб."
    if field_name in _LEG_FK_ACCESSORS:
        accessor = _LEG_FK_ACCESSORS[field_name]
        related = getattr(instance, accessor, None)
        if related is None:
            model_field = TripLeg._meta.get_field(accessor)
            model = model_field.related_model
            try:
                related = model.objects.get(pk=raw_value)
            except model.DoesNotExist:
                return f"id={raw_value}"
        return str(related)
    return str(raw_value)


@receiver(post_save, sender=TripLeg)
def leg_post_save(sender, instance, created, **kwargs):
    # Служебные сохранения (например, пометка «просмотрено») не пишут в историю.
    if getattr(instance, "_skip_history", False):
        return
    if created:
        return
    old_values = getattr(instance, "_old_values", None)
    old_instance = getattr(instance, "_old_instance", None)
    if old_values is None or old_instance is None:
        return

    user = get_current_user()
    changes = []
    for field, label in LEG_TRACKED_FIELDS.items():
        old_raw = old_values.get(field)
        new_raw = getattr(instance, field, None)
        if old_raw != new_raw:
            changes.append({
                "label": label,
                "old": _leg_display(old_instance, field, old_raw),
                "new": _leg_display(instance, field, new_raw),
            })
    if not changes:
        return

    TripHistory.objects.bulk_create([
        TripHistory(trip_id=instance.trip_id, leg=instance, user=user,
                    field_name=f"Рейс #{instance.pk}: {ch['label']}",
                    old_value=ch["old"], new_value=ch["new"])
        for ch in changes
    ])


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    if created:
        UserPreferences.get_for_user(instance)