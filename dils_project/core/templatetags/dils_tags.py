"""
Кастомные шаблонные теги и фильтры DiLS.
"""

from decimal import Decimal, InvalidOperation

from django import template
from django.utils.formats import date_format
from django.utils.safestring import mark_safe

register = template.Library()


# ============================================================
# get_item: dict[key] в шаблоне
# ============================================================

@register.filter
def get_item(mapping, key):
    """Возвращает mapping[key] или пустую строку."""
    if mapping is None:
        return ""
    try:
        return mapping.get(key, "")
    except AttributeError:
        try:
            return mapping[key]
        except (KeyError, TypeError):
            return ""


# ============================================================
# status_badge: статус рейса → Bootstrap badge (HTML-безопасный)
# ============================================================

_STATUS_STYLE = {
    "draft": "secondary",
    "sent_to_work": "primary",
    "in_work": "warning",
    "completed": "success",
}

_STATUS_LABEL = {
    "draft": "Черновик",
    "sent_to_work": "Отправлено в работу",
    "in_work": "В работе",
    "completed": "Выполнено",
}


@register.simple_tag
def status_badge(status: str) -> str:
    """
    Возвращает HTML-бейдж статуса.
    Помечается safe — иначе в шаблоне выведется как текст.
    """
    if not status:
        return ""
    style = _STATUS_STYLE.get(status, "secondary")
    label = _STATUS_LABEL.get(status, status)
    return mark_safe(f'<span class="badge text-bg-{style}">{label}</span>')


# ============================================================
# format_money: Decimal → "1 234,50 ₽"
# ============================================================

@register.filter
def format_money(value, with_currency: bool = True) -> str:
    """Форматирует число как деньги. None → '—'."""
    if value in (None, ""):
        return "—"

    try:
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)

    try:
        value = value.quantize(Decimal("0.01"))
    except InvalidOperation:
        pass

    int_part, _, frac = f"{value:.2f}".partition(".")
    sign = ""
    if int_part.startswith("-"):
        sign, int_part = "-", int_part[1:]

    int_grouped = f"{int(int_part):,}".replace(",", "\u00A0")
    result = f"{sign}{int_grouped},{frac}"

    if with_currency:
        result += "\u00A0₽"
    return result


# ============================================================
# format_date: date → "дд.мм.гггг"
# ============================================================

@register.filter
def format_date(value) -> str:
    """Короткий формат даты. None → '—'."""
    if not value:
        return "—"
    try:
        return date_format(value, format="d.m.Y", use_l10n=False)
    except (AttributeError, ValueError):
        return str(value)


# ============================================================
# yesno_icon: bool/None → ✓ / ✗ / —
# ============================================================

@register.filter
def yesno_icon(value) -> str:
    """True → ✓, False → ✗, None → —."""
    if value is None:
        return "—"
    return "✓" if value else "✗"


# ============================================================
# short_name: пользователь → "Иванов И."
# ============================================================

@register.filter
def short_name(user) -> str:
    """Фамилия + инициалы. Устойчиво к пустым значениям."""
    if not user:
        return "—"
    if hasattr(user, "short_name"):
        return user.short_name
    return str(user)