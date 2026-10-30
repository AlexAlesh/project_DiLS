"""
Сервис отчётов DiLS.
"""

from dataclasses import dataclass
from decimal import Decimal
from django.db.models import Count, Q, Sum
from ..models import TripLeg

Q_CASH = Q(payment_type__name__istartswith="Нал")
Q_CASHLESS = Q(payment_type__name__istartswith="Безнал")


def completed_qs():
    """Базовый QuerySet завершенных рейсов (TripLeg)."""
    return TripLeg.objects.filter(
        transport_company__isnull=False, driver__isnull=False,
        vehicle__isnull=False, price__isnull=False, payment_type__isnull=False
    ).select_related(
        "trip", "trip__manager", "trip__customer",
        "transport_company", "driver", "vehicle", "vehicle__brand", "vehicle__vehicle_type", "payment_type"
    )


def aggregate_totals(qs) -> dict:
    agg = qs.aggregate(
        total=Sum("price"), cash=Sum("price", filter=Q_CASH),
        cashless=Sum("price", filter=Q_CASHLESS), count=Count("id"),
    )
    total = agg["total"] or Decimal("0.00")
    cash = agg["cash"] or Decimal("0.00")
    cashless = agg["cashless"] or Decimal("0.00")
    return {
        "count": agg["count"] or 0, "total": total, "cash": cash,
        "cashless": cashless, "other": total - cash - cashless,
    }


def group_by_transport_company(qs) -> list:
    return list(qs.values("transport_company_id", "transport_company__name").annotate(
        trips=Count("id"), total=Sum("price"), cash=Sum("price", filter=Q_CASH), cashless=Sum("price", filter=Q_CASHLESS)
    ).order_by("-total", "transport_company__name"))


def group_by_driver(qs) -> list:
    return list(qs.values("driver_id", "driver__full_name", "transport_company__name").annotate(
        trips=Count("id"), total=Sum("price"), cash=Sum("price", filter=Q_CASH), cashless=Sum("price", filter=Q_CASHLESS)
    ).order_by("-trips", "driver__full_name"))


def group_by_vehicle(qs) -> list:
    return list(qs.values("vehicle_id", "vehicle__plate_number", "vehicle__brand__name", "transport_company__name").annotate(
        trips=Count("id"), total=Sum("price"), cash=Sum("price", filter=Q_CASH), cashless=Sum("price", filter=Q_CASHLESS)
    ).order_by("-trips", "vehicle__plate_number"))


def group_by_payment_type(qs) -> list:
    return list(qs.exclude(payment_type__isnull=True).values("payment_type__name").annotate(
        trips=Count("id"), total=Sum("price")
    ).order_by("-total"))


@dataclass
class ReportResult:
    totals: dict
    by_transport_company: list
    by_driver: list
    by_vehicle: list
    by_payment_type: list


def build_report(qs) -> ReportResult:
    return ReportResult(
        totals=aggregate_totals(qs),
        by_transport_company=group_by_transport_company(qs),
        by_driver=group_by_driver(qs),
        by_vehicle=group_by_vehicle(qs),
        by_payment_type=group_by_payment_type(qs),
    )

def build_report_as_dict(qs) -> dict:
    r = build_report(qs)
    return {
        "totals": r.totals, "by_transport_company": r.by_transport_company,
        "by_driver": r.by_driver, "by_vehicle": r.by_vehicle, "by_payment_type": r.by_payment_type,
    }