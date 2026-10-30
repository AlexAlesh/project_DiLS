"""
Views DiLS.
"""

import json
from datetime import date, timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    BrandForm, CustomerForm, DriverForm, PaymentTypeForm, ProfileForm,
    TransportCompanyForm, TripFilterForm, TripLogistForm, TripManagerForm,
    VehicleForm, VehicleTypeForm,
)
from .models import (
    Brand, Customer, CustomerAddress, Driver, PaymentType, TransportCompany,
    Trip, TripLeg, User, UserPreferences, Vehicle, VehicleType,
)
from .services.report_service import build_report_as_dict, completed_qs
from .services.trip_service import (
    can_edit_as_logist, can_edit_as_manager, mark_as_viewed,
    save_logist_part, save_manager_part, trips_base_queryset, legs_base_queryset,
)
from .utils import (
    REPORTS_DASHBOARDS, REPORTS_FILTERS, REQUESTS_DASHBOARDS,
    REQUESTS_FILTERS, TRIPS_DASHBOARDS, TRIPS_FILTERS,
    apply_filters, compute_dashboards, parse_date,
)


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.is_admin_role or request.user.role in roles:
                return view(request, *args, **kwargs)
            raise PermissionDenied
        return wrapper
    return decorator


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin_role:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


# Разграничение прав на справочники:
#   - заказчики и их адреса — ведёт менеджер (и админ);
#   - ТК, водители, машины, марки, типы ТС, типы оплаты — ведёт логист (и админ).
_LOOKUP_OWNER_ROLES = {
    "customers": (User.ROLE_MANAGER,),
    "customer-addresses": (User.ROLE_MANAGER,),
    "transport-companies": (User.ROLE_LOGIST,),
    "drivers": (User.ROLE_LOGIST,),
    "vehicles": (User.ROLE_LOGIST,),
    "brands": (User.ROLE_LOGIST,),
    "vehicle-types": (User.ROLE_LOGIST,),
    "payment-types": (User.ROLE_LOGIST,),
}


def _can_manage_lookup(user, kind):
    """Проверка права пользователя на изменение записи справочника `kind`."""
    if user.is_admin_role:
        return True
    return user.role in _LOOKUP_OWNER_ROLES.get(kind, ())


def lookup_permission_required(get_kind):
    """Декоратор AJAX-эндпоинтов управления справочниками.

    `get_kind` — функция, возвращающая вид справочника по аргументам view
    (например, kwargs["kind"] или связка kind+pk). Для AJAX-эндпоинтов
    вместо 403 возвращается JSON с ошибкой, чтобы фронт корректно показал alert.
    """
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            kind = get_kind(request, kwargs)
            if not _can_manage_lookup(request.user, kind):
                return JsonResponse({"error": "Недостаточно прав для изменения этого справочника"}, status=403)
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def _lookup_kind_from_url(request, kwargs):
    return kwargs.get("kind")


def _fixed_kind(kind):
    """Getter, всегда возвращающий фиксированный вид справочника."""
    return lambda request, kwargs: kind


def _address_kind(request, kwargs):
    """Для эндпоинтов адресов заказчика: если адрес не найден, разрешаем
    пройти дальше — view сам вернёт корректный 404."""
    exists = CustomerAddress.objects.filter(pk=kwargs.get("pk")).exists()
    return "customer-addresses" if exists else "customers"


@login_required
def home_redirect(request):
    user = request.user
    if user.is_admin_role: return redirect("core:settings_index")
    if user.is_logist: return redirect("core:request_list")
    return redirect("core:trip_list")


# ============================================================
# Общие контекстные билдеры
# ============================================================

def _build_list_context(request, *, kind):
    prefs = UserPreferences.get_for_user(request.user)

    if kind == "trips":
        filters_registry = TRIPS_FILTERS
        dashboards_registry = TRIPS_DASHBOARDS
        visible_filters = prefs.trips_visible_filters
        visible_dashboards = prefs.trips_visible_dashboards
        qs = apply_filters(trips_base_queryset(), request.GET, visible_filters, filters_registry, is_leg=False)

        if request.user.is_manager:
            m_filter = request.GET.get("manager")
            if m_filter is None:
                qs = qs.filter(manager=request.user)
            elif m_filter != "":
                qs = qs.filter(manager_id=m_filter)

        if request.GET.get("status") != Trip.STATUS_DRAFT:
            qs = qs.exclude(status=Trip.STATUS_DRAFT)

        dashboards = compute_dashboards(qs, visible_dashboards, dashboards_registry, request=request)

        if request.GET.get("no_driver") == "1":
            qs = qs.filter(legs__driver__isnull=True).distinct()
        if request.GET.get("no_price") == "1":
            qs = qs.filter(legs__price__isnull=True).distinct()

        status_param = request.GET.get("status")
        if status_param in (Trip.STATUS_COMPLETED, Trip.STATUS_IN_WORK, Trip.STATUS_DRAFT, Trip.STATUS_SENT_TO_WORK):
            if status_param == Trip.STATUS_IN_WORK:
                qs = qs.filter(status__in=[Trip.STATUS_SENT_TO_WORK, Trip.STATUS_IN_WORK])
            else:
                qs = qs.filter(status=status_param)

        paginator = Paginator(qs, 50)
        page_obj = paginator.get_page(request.GET.get("page"))

    else: # requests (Логист)
        filters_registry = REQUESTS_FILTERS
        dashboards_registry = REQUESTS_DASHBOARDS
        visible_filters = prefs.requests_visible_filters
        visible_dashboards = prefs.requests_visible_dashboards

        legs_qs = apply_filters(legs_base_queryset(), request.GET, visible_filters, filters_registry, is_leg=True)
        legs_qs = legs_qs.exclude(trip__status=Trip.STATUS_DRAFT)

        dashboards = compute_dashboards(legs_qs, visible_dashboards, dashboards_registry, request=request)

        if request.GET.get("no_driver") == "1":
            legs_qs = legs_qs.filter(driver__isnull=True)
        if request.GET.get("no_price") == "1":
            legs_qs = legs_qs.filter(price__isnull=True)

        status_param = request.GET.get("status")
        if status_param == 'completed':
            legs_qs = legs_qs.filter(transport_company__isnull=False, driver__isnull=False, vehicle__isnull=False, price__isnull=False, payment_type__isnull=False)
        elif status_param == 'in_work':
            legs_qs = legs_qs.exclude(transport_company__isnull=False, driver__isnull=False, vehicle__isnull=False, price__isnull=False, payment_type__isnull=False)

        trip_ids = legs_qs.values_list('trip_id', flat=True).distinct()

        prefetch = Prefetch('legs', queryset=legs_qs.select_related(
            'transport_company', 'driver', 'vehicle',
            'vehicle__brand', 'vehicle__vehicle_type', 'payment_type'
        ))

        qs = Trip.objects.filter(id__in=trip_ids).select_related(
            'manager', 'customer'
        ).prefetch_related(prefetch).order_by('-created_at')

        paginator = Paginator(qs, 50)
        page_obj = paginator.get_page(request.GET.get("page"))

    return {
        "page_obj": page_obj, "paginator": paginator,
        "dashboards": dashboards, "dashboards_registry": dashboards_registry,
        "filters_registry": filters_registry,
        "visible_filters": visible_filters, "visible_dashboards": visible_dashboards,
        "filter_choices": TripFilterForm.filter_choices(user=request.user),
        "current_filters": {k: request.GET.getlist(k) for k in request.GET.keys()},
        "kind": kind,
    }


# ============================================================
# ЗАЯВКИ (Менеджер)
# ============================================================

@role_required(User.ROLE_MANAGER)
def trip_list(request):
    ctx = _build_list_context(request, kind="trips")
    ctx["logist_user"] = User.objects.filter(role=User.ROLE_LOGIST).first()
    return render(request, "trips/list.html", ctx)


@role_required(User.ROLE_MANAGER)
def trip_create(request):
    if request.method == "POST":
        form = TripManagerForm(request.POST, user=request.user)
        if form.is_valid():
            trip = save_manager_part(None, form, manager=request.user)
            messages.success(request, "Заявка сохранена.")
            return redirect("core:trip_list")
    else:
        form = TripManagerForm(user=request.user)

    return render(request, "trips/form.html", {"form": form, "mode": "create", "trip": None})


@login_required
def trip_detail(request, pk):
    trip = get_object_or_404(trips_base_queryset(), pk=pk)
    logist_user = User.objects.filter(role=User.ROLE_LOGIST).first()
    return render(request, "trips/detail.html", {"trip": trip, "logist_user": logist_user})


@login_required
def trip_edit(request, pk):
    trip = get_object_or_404(trips_base_queryset(), pk=pk)

    if request.user.is_admin_role or can_edit_as_manager(request.user, trip):
        if request.method == "POST":
            form = TripManagerForm(request.POST, instance=trip, user=request.user)
            if form.is_valid():
                save_manager_part(trip, form)
                messages.success(request, "Заявка обновлена.")
                return redirect("core:trip_list")
        else:
            form = TripManagerForm(instance=trip, user=request.user)
        return render(request, "trips/form.html", {"form": form, "trip": trip, "mode": "edit"})

    raise PermissionDenied


@role_required(User.ROLE_MANAGER)
@require_POST
def trip_delete(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    if not (request.user.is_admin_role or trip.manager_id == request.user.pk):
        raise PermissionDenied
    if trip.status != Trip.STATUS_DRAFT:
        messages.error(request, "Удалять можно только черновики.")
        return redirect("core:trip_list")
    trip.delete()
    messages.success(request, "Черновик успешно удалён.")
    return redirect("core:trip_list")


@login_required
def trip_history(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    history = trip.history.select_related("user").all()
    return render(request, "trips/history.html", {"trip": trip, "history": history})


# ============================================================
# РЕЙСЫ (Логист)
# ============================================================

@role_required(User.ROLE_LOGIST)
def request_list(request):
    ctx = _build_list_context(request, kind="requests")
    return render(request, "requests/list.html", ctx)


@role_required(User.ROLE_LOGIST)
def request_edit(request, pk):
    leg = get_object_or_404(legs_base_queryset(), pk=pk)
    if leg.trip.status == Trip.STATUS_DRAFT:
        raise PermissionDenied

    leg_ids = list(leg.trip.legs.order_by('id').values_list('id', flat=True))
    try:
        leg_ordinal = leg_ids.index(leg.pk) + 1
    except ValueError:
        leg_ordinal = 1

    if request.method == "POST":
        form = TripLogistForm(request.POST, instance=leg)
        if form.is_valid():
            save_logist_part(leg, form)
            mark_as_viewed(leg)
            messages.success(request, "Рейс обновлён.")
            return redirect("core:request_list")
    else:
        form = TripLogistForm(instance=leg)

    mark_as_viewed(leg)
    return render(request, "requests/form.html", {
        "form": form, "leg": leg, "leg_ordinal": leg_ordinal
    })


@role_required(User.ROLE_LOGIST)
@require_POST
def request_mark_viewed(request, pk):
    leg = get_object_or_404(TripLeg, pk=pk)
    mark_as_viewed(leg)
    return JsonResponse({"ok": True})


# ============================================================
# РЕЙСЫ ВОДИТЕЛЕЙ (Новая страница для логиста)
# ============================================================

@role_required(User.ROLE_LOGIST)
def driver_trips_list(request):
    prefs = UserPreferences.get_for_user(request.user)
    today = date.today()

    # 1. Даты по умолчанию (сегодня и +2 дня)
    if "loading_date_from" not in request.GET and "loading_date_to" not in request.GET:
        params = request.GET.copy()
        params["loading_date_from"] = today.strftime("%Y-%m-%d")
        params["loading_date_to"] = (today + timedelta(days=2)).strftime("%Y-%m-%d")
        return redirect(f"{request.path}?{params.urlencode()}")

    # 2. ТК по умолчанию
    if "transport_company" not in request.GET and prefs.driver_trips_default_tcs:
        params = request.GET.copy()
        for tc_id in prefs.driver_trips_default_tcs:
            params.appendlist("transport_company", str(tc_id))
        return redirect(f"{request.path}?{params.urlencode()}")

    # 3. Базовый QuerySet
    qs = TripLeg.objects.exclude(trip__status=Trip.STATUS_DRAFT).select_related(
        "trip", "trip__customer", "trip__manager", "driver",
        "vehicle", "vehicle__brand", "vehicle__vehicle_type", "payment_type", "transport_company"
    ).order_by("trip__loading_date", "id")

    # 4. Фильтры
    d_from = parse_date(request.GET.get("loading_date_from"))
    d_to = parse_date(request.GET.get("loading_date_to"))
    if d_from: qs = qs.filter(trip__loading_date__gte=d_from)
    if d_to: qs = qs.filter(trip__loading_date__lte=d_to)

    tc_ids = request.GET.getlist("transport_company")
    if tc_ids:
        qs = qs.filter(transport_company_id__in=tc_ids)

    # 5. Поля и пагинация
    visible_fields = prefs.driver_trips_visible_fields or UserPreferences.DRIVER_TRIPS_DEFAULT_FIELDS

    paginator = Paginator(qs, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    all_tcs = TransportCompany.objects.all().order_by("name")

    return render(request, "requests/driver_trips.html", {
        "page_obj": page_obj,
        "visible_fields": visible_fields,
        "all_tcs": all_tcs,
        "selected_tcs": tc_ids,
        "date_from": request.GET.get("loading_date_from"),
        "date_to": request.GET.get("loading_date_to"),
        "default_tcs": prefs.driver_trips_default_tcs,
    })


# ============================================================
# Отчёты
# ============================================================

@login_required
def report_index(request):
    if request.user.is_manager:
        raise PermissionDenied

    prefs = UserPreferences.get_for_user(request.user)
    qs = apply_filters(completed_qs(), request.GET, prefs.reports_visible_filters, REPORTS_FILTERS, is_leg=True)
    report = build_report_as_dict(qs)
    totals = report["totals"]

    all_dashboards = {
        "cashless": {"key": "cashless", "label": "Безналичные", "style": "primary", "count": totals["cashless"]},
        "cash": {"key": "cash", "label": "Наличные", "style": "success", "count": totals["cash"]},
        "total": {"key": "total", "label": "Итоговая сумма", "style": "dark", "count": totals["total"]},
    }
    enabled = set(prefs.reports_visible_dashboards or [])
    dashboards = [all_dashboards[k] for k in all_dashboards if k in enabled]

    return render(request, "reports/index.html", {
        "count": totals["count"], "cash_sum": totals["cash"], "cashless_sum": totals["cashless"],
        "total_sum": totals["total"], "report": report,
        "dashboards": dashboards, "dashboards_registry": REPORTS_DASHBOARDS,
        "visible_dashboards": prefs.reports_visible_dashboards,
        "filters_registry": REPORTS_FILTERS, "visible_filters": prefs.reports_visible_filters,
        "filter_choices": TripFilterForm.filter_choices(user=request.user), "kind": "reports",
    })


# ============================================================
# Профиль и Настройки
# ============================================================

@login_required
def profile_index(request):
    user = request.user

    if request.method == "POST":
        # Вид справочника в POST-запросах профиля определяется ролью пользователя.
        directory_kind = "transport-companies" if user.is_logist else "customers"

        if "add_lookup" in request.POST:
            if not _can_manage_lookup(user, directory_kind):
                messages.error(request, "Недостаточно прав для изменения этого справочника.")
                return redirect("core:profile_index")
            name = (request.POST.get("lookup_name") or "").strip()
            if name:
                if user.is_logist:
                    TransportCompany.objects.get_or_create(name=name)
                else:
                    manager = user if user.is_manager else None
                    Customer.objects.get_or_create(name=name, manager=manager)
                messages.success(request, "Добавлено в справочник.")
            return redirect("core:profile_index")

        elif "delete_lookup" in request.POST:
            if not _can_manage_lookup(user, directory_kind):
                messages.error(request, "Недостаточно прав для изменения этого справочника.")
                return redirect("core:profile_index")
            pk = request.POST.get("lookup_pk")
            if pk:
                if user.is_logist:
                    TransportCompany.objects.filter(pk=pk).delete()
                else:
                    qs = Customer.objects.filter(pk=pk)
                    if user.is_manager:
                        qs = qs.filter(Q(manager=user) | Q(manager__isnull=True))
                    qs.delete()
                messages.success(request, "Удалено из справочника.")
            return redirect("core:profile_index")

        else:
            form = ProfileForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                messages.success(request, "Профиль обновлён.")
                return redirect("core:profile_index")
    else:
        form = ProfileForm(instance=user)

    if user.is_logist:
        directory = TransportCompany.objects.all().order_by("name")
        directory_kind = "transport-companies"
        directory_title = "Справочник транспортных компаний"
    else:
        if user.is_manager:
            directory = Customer.objects.filter(Q(manager=user) | Q(manager__isnull=True)).distinct().order_by("name")
        else:
            directory = Customer.objects.all().order_by("name")
        directory_kind = "customers"
        directory_title = "Справочник заказчиков"

    return render(request, "profile/index.html", {
        "user_obj": user, "form": form, "directory": directory,
        "directory_kind": directory_kind, "directory_title": directory_title,
    })


@admin_required
def settings_index(request):
    return render(request, "settings/index.html")


@admin_required
def settings_users(request):
    users = User.objects.all().order_by("last_name", "first_name", "username")
    return render(request, "settings/users.html", {"users": users})


@admin_required
def settings_user_edit(request, pk):
    target = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        target.last_name = (request.POST.get("last_name") or "").strip()
        target.first_name = (request.POST.get("first_name") or "").strip()
        target.email = (request.POST.get("email") or "").strip()
        target.phone = (request.POST.get("phone") or "").strip()
        role = request.POST.get("role")
        if role in dict(User.ROLE_CHOICES):
            target.role = role
        target.save()
        messages.success(request, "Пользователь обновлён.")
        return redirect("core:settings_users")
    return render(request, "settings/user_form.html", {"target": target})


# ============================================================
# AJAX: Зависимые селекты и поиск
# ============================================================

@login_required
@require_GET
def ajax_dependent_select(request, kind):
    tc_ids = request.GET.getlist("transport_company")
    if not tc_ids:
        return JsonResponse({"results": []})

    if kind == "drivers":
        qs = Driver.objects.filter(transport_company_id__in=tc_ids).order_by("full_name")
        results = [{"id": d.pk, "text": d.full_name} for d in qs]
    elif kind == "vehicles":
        qs = Vehicle.objects.filter(transport_company_id__in=tc_ids).select_related("brand").order_by("plate_number")
        results = [{"id": v.pk, "text": f"{v.plate_number} ({v.brand.name})"} for v in qs]
    else:
        return JsonResponse({"results": []})
    return JsonResponse({"results": results})


_SEARCH_MAP = {
    "customers": (Customer, "name"), "transport-companies": (TransportCompany, "name"),
    "drivers": (Driver, "full_name"), "vehicles": (Vehicle, "plate_number"),
    "brands": (Brand, "name"), "vehicle-types": (VehicleType, "name"),
    "payment-types": (PaymentType, "name"),
}


@login_required
@require_GET
def ajax_search(request, kind):
    if kind not in _SEARCH_MAP: return JsonResponse({"results": []})
    model, field = _SEARCH_MAP[kind]
    q = (request.GET.get("q") or "").strip()
    qs = model.objects.all()

    if kind == "customers" and request.user.is_manager:
        qs = qs.filter(Q(manager=request.user) | Q(manager__isnull=True)).distinct()

    if q:
        qs = qs.filter(**{f"{field}__icontains": q})
    tc_id = request.GET.get("transport_company")
    if kind in ("drivers", "vehicles") and tc_id:
        qs = qs.filter(transport_company_id=tc_id)
    return JsonResponse({"results": [{"id": obj.pk, "text": str(obj)} for obj in qs[:20]]})


# ============================================================
# AJAX: Создание и сохранение настроек
# ============================================================

@lookup_permission_required(_lookup_kind_from_url)
@require_POST
def ajax_create_lookup(request, kind):
    if kind not in _SEARCH_MAP: return JsonResponse({"error": "unknown kind"}, status=400)
    name = (request.POST.get("name") or "").strip()
    if not name: return JsonResponse({"error": "name required"}, status=400)

    try:
        if kind == "customers":
            manager = request.user if request.user.is_manager else None
            qs = Customer.objects.filter(name=name)
            if manager:
                qs = qs.filter(Q(manager=manager) | Q(manager__isnull=True))
            obj = qs.first()
            if obj:
                if manager and not obj.manager:
                    obj.manager = manager
                    obj.save()
            else:
                obj = Customer.objects.create(name=name, manager=manager)
        elif kind == "transport-companies":
            obj, _ = TransportCompany.objects.get_or_create(name=name)
        elif kind == "brands":
            obj, _ = Brand.objects.get_or_create(name=name)
        elif kind == "vehicle-types":
            obj, _ = VehicleType.objects.get_or_create(name=name)
        elif kind == "payment-types":
            obj, _ = PaymentType.objects.get_or_create(name=name)
        elif kind == "drivers":
            tc_id = request.POST.get("transport_company")
            if not tc_id: return JsonResponse({"error": "transport_company required"}, status=400)
            obj, _ = Driver.objects.get_or_create(
                transport_company_id=tc_id, full_name=name,
                defaults={"phone": (request.POST.get("phone") or "").strip()},
            )
        elif kind == "vehicles":
            tc_id, brand_id, vtype_id = request.POST.get("transport_company"), request.POST.get("brand"), request.POST.get("vehicle_type")
            if not (tc_id and brand_id and vtype_id): return JsonResponse({"error": "tc, brand, vtype required"}, status=400)
            from .models import format_plate_number
            obj, _ = Vehicle.objects.get_or_create(
                transport_company_id=tc_id, plate_number=format_plate_number(name),
                defaults={"brand_id": brand_id, "vehicle_type_id": vtype_id},
            )
    except Exception as exc: return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"id": obj.pk, "text": str(obj)})


@login_required
@require_POST
def ajax_save_preferences(request):
    try: payload = json.loads(request.body or "{}")
    except json.JSONDecodeError: return JsonResponse({"error": "invalid json"}, status=400)

    page = payload.get("page")
    field = payload.get("field")
    values = payload.get("values", [])

    attr = _PREF_ATTR_MAP.get((page, field))
    if not attr: return JsonResponse({"error": "unknown target"}, status=400)

    prefs = UserPreferences.get_for_user(request.user)
    setattr(prefs, attr, values)
    prefs.save()
    return JsonResponse({"ok": True})


_PREF_ATTR_MAP = {
    ("trips", "filters"): "trips_visible_filters",
    ("trips", "dashboards"): "trips_visible_dashboards",
    ("requests", "filters"): "requests_visible_filters",
    ("requests", "dashboards"): "requests_visible_dashboards",
    ("reports", "filters"): "reports_visible_filters",
    ("reports", "dashboards"): "reports_visible_dashboards",
    ("driver_trips", "fields"): "driver_trips_visible_fields",
    ("driver_trips", "default_tcs"): "driver_trips_default_tcs",
}


# ============================================================
# AJAX: Управление справочниками и адресами
# ============================================================

@login_required
@require_GET
def ajax_get_lookup_details(request, kind, pk):
    # Чтение деталей доступно всем ролям (справочники видны в формах),
    # но скрытые поля редакторов в UI включаются по правам (см. can_manage).
    try:
        if kind == "transport-companies":
            tc = TransportCompany.objects.get(pk=pk)
            drivers = [{"id": d.pk, "name": d.full_name, "phone": d.phone} for d in tc.drivers.all()]
            vehicles = [{"id": v.pk, "name": v.plate_number, "brand": v.brand.name, "brand_id": v.brand_id, "type": v.vehicle_type.name, "type_id": v.vehicle_type_id} for v in tc.vehicles.all()]
            return JsonResponse({
                "id": tc.pk, "name": tc.name, "contact_person": tc.contact_person,
                "phone": tc.phone, "email": tc.email,
                "drivers": drivers, "vehicles": vehicles,
                "can_manage": _can_manage_lookup(request.user, kind),
            })
        elif kind == "customers":
            c = Customer.objects.get(pk=pk)
            addresses = [{"id": a.pk, "info": a.info} for a in c.addresses.all()]
            return JsonResponse({
                "id": c.pk, "name": c.name, "contact_person": c.contact_person,
                "phone": c.phone, "email": c.email, "addresses": addresses,
                "can_manage": _can_manage_lookup(request.user, kind),
            })
    except (TransportCompany.DoesNotExist, Customer.DoesNotExist):
        return JsonResponse({"error": "Not found"}, status=404)
    return JsonResponse({"error": "Unknown kind"}, status=400)


@lookup_permission_required(_lookup_kind_from_url)
@require_POST
def ajax_edit_lookup(request, kind, pk):
    name = (request.POST.get("name") or "").strip()
    if not name: return JsonResponse({"error": "name required"}, status=400)
    try:
        if kind == "transport-companies":
            obj = TransportCompany.objects.get(pk=pk)
            obj.name = name
            obj.contact_person = (request.POST.get("contact_person") or "").strip()
            obj.phone = (request.POST.get("phone") or "").strip()
            obj.email = (request.POST.get("email") or "").strip()
            obj.save()
        elif kind == "customers":
            obj = Customer.objects.get(pk=pk)
            obj.name = name
            obj.contact_person = (request.POST.get("contact_person") or "").strip()
            obj.phone = (request.POST.get("phone") or "").strip()
            obj.email = (request.POST.get("email") or "").strip()
            obj.save()
        return JsonResponse({"ok": True})
    except (TransportCompany.DoesNotExist, Customer.DoesNotExist):
        return JsonResponse({"error": "Not found"}, status=404)


@lookup_permission_required(_fixed_kind("drivers"))
@require_POST
def ajax_delete_driver(request, pk):
    try:
        Driver.objects.get(pk=pk).delete()
        return JsonResponse({"ok": True})
    except Driver.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)


@lookup_permission_required(_fixed_kind("vehicles"))
@require_POST
def ajax_delete_vehicle(request, pk):
    try:
        Vehicle.objects.get(pk=pk).delete()
        return JsonResponse({"ok": True})
    except Vehicle.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)


@lookup_permission_required(_fixed_kind("drivers"))
@require_POST
def ajax_edit_driver(request, pk):
    try:
        driver = Driver.objects.get(pk=pk)
        name = (request.POST.get("name") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        if not name: return JsonResponse({"error": "name required"}, status=400)
        driver.full_name = name
        driver.phone = phone
        driver.save()
        return JsonResponse({"ok": True})
    except Driver.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)


@lookup_permission_required(_fixed_kind("vehicles"))
@require_POST
def ajax_edit_vehicle(request, pk):
    try:
        vehicle = Vehicle.objects.get(pk=pk)
        name = (request.POST.get("name") or "").strip()
        brand_id = request.POST.get("brand")
        vtype_id = request.POST.get("vehicle_type")
        if not (name and brand_id and vtype_id): return JsonResponse({"error": "all fields required"}, status=400)
        from .models import format_plate_number
        vehicle.plate_number = format_plate_number(name)
        vehicle.brand_id = brand_id
        vehicle.vehicle_type_id = vtype_id
        vehicle.save()
        return JsonResponse({"ok": True})
    except Vehicle.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)


@lookup_permission_required(_address_kind)
@require_POST
def ajax_delete_customer_address(request, pk):
    try:
        CustomerAddress.objects.get(pk=pk).delete()
        return JsonResponse({"ok": True})
    except CustomerAddress.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)


@lookup_permission_required(_fixed_kind("customers"))
@require_POST
def ajax_add_customer_address(request, pk):
    info = (request.POST.get("info") or "").strip()
    if not info: return JsonResponse({"error": "info required"}, status=400)
    try:
        customer = Customer.objects.get(pk=pk)
        obj, created = CustomerAddress.objects.get_or_create(customer=customer, info=info)
        return JsonResponse({"ok": True, "id": obj.pk})
    except Customer.DoesNotExist:
        return JsonResponse({"error": "Customer not found"}, status=404)


@lookup_permission_required(_address_kind)
@require_POST
def ajax_edit_customer_address(request, pk):
    info = (request.POST.get("info") or "").strip()
    if not info: return JsonResponse({"error": "info required"}, status=400)
    try:
        obj = CustomerAddress.objects.get(pk=pk)
        obj.info = info
        obj.save()
        return JsonResponse({"ok": True})
    except CustomerAddress.DoesNotExist:
        return JsonResponse({"error": "Address not found"}, status=404)


@login_required
@require_GET
def ajax_get_customer_addresses(request, pk):
    addresses = CustomerAddress.objects.filter(customer_id=pk).values_list('info', flat=True)
    return JsonResponse({"addresses": list(addresses)})