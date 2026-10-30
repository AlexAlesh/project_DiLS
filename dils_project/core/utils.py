"""
Утилиты: реестры фильтров/дашбордов, парсинг, применение фильтров.
"""

import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .models import Trip, TripLeg

logger = logging.getLogger(__name__)


# ============================================================
# РЕЕСТРЫ ФИЛЬТРОВ
# ============================================================

TRIPS_FILTERS = [
    {'key': 'loading_date',      'label': 'Дата загрузки',         'type': 'date_range'},
    {'key': 'unloading_date',    'label': 'Дата разгрузки',        'type': 'date_range'},
    {'key': 'manager',           'label': 'Менеджер',              'type': 'select'},
    {'key': 'customer',          'label': 'Заказчик',              'type': 'select'},
    {'key': 'transport_company', 'label': 'Транспортная компания', 'type': 'select'},
    {'key': 'driver',            'label': 'Водители',              'type': 'select'},
]

REQUESTS_FILTERS = [
    {'key': 'loading_date',      'label': 'Дата загрузки',         'type': 'date_range'},
    {'key': 'unloading_date',    'label': 'Дата разгрузки',        'type': 'date_range'},
    {'key': 'manager',           'label': 'Менеджер',              'type': 'select'},
    {'key': 'customer',          'label': 'Заказчик',              'type': 'select'},
    {'key': 'transport_company', 'label': 'Транспортная компания', 'type': 'select'},
    {'key': 'driver',            'label': 'Водители',              'type': 'select'},
    {'key': 'plate_number',      'label': 'Гос. номер',            'type': 'text'},
    {'key': 'brand',             'label': 'Марка',                 'type': 'select'},
    {'key': 'vehicle_type',      'label': 'Тип авто',              'type': 'select'},
    {'key': 'payment_type',      'label': 'Тип оплаты',            'type': 'select'},
]

REPORTS_FILTERS = [
    {'key': 'loading_date',      'label': 'Дата загрузки',         'type': 'date_range'},
    {'key': 'unloading_date',    'label': 'Дата разгрузки',        'type': 'date_range'},
    {'key': 'transport_company', 'label': 'Транспортная компания', 'type': 'select'},
    {'key': 'driver',            'label': 'Водители',              'type': 'select'},
    {'key': 'plate_number',      'label': 'Гос. номер',            'type': 'text'},
    {'key': 'brand',             'label': 'Марка',                 'type': 'select'},
    {'key': 'vehicle_type',      'label': 'Тип авто',              'type': 'select'},
    {'key': 'payment_type',      'label': 'Тип оплаты',            'type': 'select'},
    {'key': 'price',             'label': 'Цена',                  'type': 'number_range'},
    {'key': 'ttn_number',        'label': 'ТТН',                   'type': 'text'},
]


# ============================================================
# МАППИНГ ПОЛЕЙ (для Trip и для TripLeg)
# ============================================================

TRIP_FIELD_MAP = {
    'loading_date':      'loading_date',
    'unloading_date':    'unloading_date',
    'manager':           'manager_id',
    'customer':          'customer_id',
}

LEG_FIELD_MAP = {
    'loading_date':      'trip__loading_date',
    'unloading_date':    'trip__unloading_date',
    'manager':           'trip__manager_id',
    'customer':          'trip__customer_id',
    'transport_company': 'transport_company_id',
    'driver':            'driver_id',
    'plate_number':      'vehicle__plate_number',
    'brand':             'vehicle__brand_id',
    'vehicle_type':      'vehicle__vehicle_type_id',
    'payment_type':      'payment_type_id',
    'price':             'price',
    'ttn_number':        'ttn_number',
}


# ============================================================
# ПАРСИНГ
# ============================================================

def parse_date(value):
    if not value: return None
    for fmt in ('%Y-%m-%d', '%d.%m.%Y'):
        try: return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, TypeError): continue
    return None

def parse_decimal(value):
    if not value: return None
    cleaned = str(value).replace(' ', '').replace(',', '.').strip()
    try: return Decimal(cleaned)
    except InvalidOperation: return None


# ============================================================
# ПРИМЕНЕНИЕ ФИЛЬТРОВ
# ============================================================

def _apply_date_range(qs, field, params, key):
    d_from = parse_date(params.get(f'{key}_from'))
    d_to = parse_date(params.get(f'{key}_to'))
    if d_from: qs = qs.filter(**{f'{field}__gte': d_from})
    if d_to: qs = qs.filter(**{f'{field}__lte': d_to})
    return qs

def _apply_select(qs, field, params, key):
    raw = params.getlist(key) if hasattr(params, 'getlist') else [params.get(key)]
    ids = []
    for x in raw:
        if not x: continue
        try: ids.append(int(x))
        except (ValueError, TypeError): continue
    if ids: qs = qs.filter(**{f'{field}__in': ids})
    return qs

def _apply_text(qs, field, params, key):
    value = (params.get(key) or '').strip()
    if value: qs = qs.filter(**{f'{field}__icontains': value})
    return qs

def _apply_number_range(qs, field, params, key):
    v_min = parse_decimal(params.get(f'{key}_min'))
    v_max = parse_decimal(params.get(f'{key}_max'))
    if v_min is not None: qs = qs.filter(**{f'{field}__gte': v_min})
    if v_max is not None: qs = qs.filter(**{f'{field}__lte': v_max})
    return qs

_APPLIERS = {
    'date_range':   _apply_date_range,
    'select':       _apply_select,
    'text':         _apply_text,
    'number_range': _apply_number_range,
}

def apply_filters(qs, params, allowed_keys, registry, is_leg=False):
    field_map = LEG_FIELD_MAP if is_leg else TRIP_FIELD_MAP
    registry_by_key = {f['key']: f for f in registry}
    for key in allowed_keys:
        spec = registry_by_key.get(key)
        if not spec: continue
        field = field_map.get(key)
        if not field: continue
        applier = _APPLIERS.get(spec['type'])
        if not applier: continue
        try:
            qs = applier(qs, field, params, key)
        except Exception:
            logger.exception('Ошибка применения фильтра %r', key)
    return qs


# ============================================================
# ДАШБОРДЫ
# ============================================================
#
# Статусная логика живёт в одном месте: Trip.compute_status() (Python)
# и TripLeg.FILLED_SQL / STARTED_SQL / EMPTY_SQL (эквивалентные Q-объекты).
# Все SQL-фильтры ниже построены на этих Q-объектах — рассинхрон Python/SQL
# исключён конструктивно.

PAGE_SIZE = 50  # размер страницы для всех списков

DASHBOARD_PARAMS = ('no_driver', 'no_price', 'status')


def apply_dashboard_params(qs, request):
    """Применяет к queryset dashboard-параметры из GET (?status=..., ?no_driver=1...).

    Работает и с Trip-, и с TripLeg-queryset'ами: для legs статусные
    фильтры берутся из Q-объектов модели TripLeg (FILLED/STARTED/EMPTY),
    что гарантирует совпадение с Python-логикой is_filled()/is_started().
    Для trips фильтруем по материализованному полю Trip.status.
    """
    if request is None:
        return qs
    get = request.GET
    status_param = get.get('status')
    no_driver = get.get('no_driver') == '1'
    no_price = get.get('no_price') == '1'
    leg = qs.model is TripLeg

    if status_param == Trip.STATUS_COMPLETED:
        qs = qs.filter(TripLeg.FILLED_SQL) if leg else qs.filter(status=Trip.STATUS_COMPLETED)
    elif status_param == Trip.STATUS_IN_WORK:
        if leg:
            # «В работе» = начатые, но не заполненные плечи
            # (пустые сюда не попадают — см. compute_status()).
            qs = qs.filter(TripLeg.STARTED_SQL)
        else:
            qs = qs.filter(status__in=[Trip.STATUS_SENT_TO_WORK, Trip.STATUS_IN_WORK])
    elif status_param == Trip.STATUS_DRAFT:
        qs = qs.filter(trip__status=Trip.STATUS_DRAFT) if leg else qs.filter(status=Trip.STATUS_DRAFT)
    elif status_param == Trip.STATUS_SENT_TO_WORK:
        qs = qs.filter(TripLeg.EMPTY_SQL) if leg else qs.filter(status=Trip.STATUS_SENT_TO_WORK)

    if no_driver:
        qs = qs.filter(driver__isnull=True) if leg else \
            qs.filter(legs__driver__isnull=True).distinct()
    if no_price:
        qs = qs.filter(price__isnull=True) if leg else \
            qs.filter(legs__price__isnull=True).distinct()
    return qs


def build_dashboard_query(key, request):
    if request is None: return "?"
    params = request.GET.copy()
    for p in DASHBOARD_PARAMS:
        if p in params: del params[p]
    if key == 'completed': params['status'] = 'completed'
    elif key == 'in_work': params['status'] = 'in_work'
    elif key == 'sent_to_work': params['status'] = 'sent_to_work'
    elif key == 'no_driver': params['no_driver'] = '1'
    elif key == 'no_price': params['no_price'] = '1'
    elif key == 'draft': params['status'] = 'draft'
    q = params.urlencode()
    return "?" + q if q else "?"

def is_dashboard_active(key, request):
    if request is None: return False
    get = request.GET
    if key == 'all': return not any(p in get for p in DASHBOARD_PARAMS)
    if key == 'completed': return get.get('status') == 'completed'
    if key == 'in_work': return get.get('status') == 'in_work'
    if key == 'sent_to_work': return get.get('status') == 'sent_to_work'
    if key == 'no_driver': return get.get('no_driver') == '1'
    if key == 'no_price': return get.get('no_price') == '1'
    if key == 'draft': return get.get('status') == 'draft'
    return False


# --- Дашборды для Заявок (Trip) ---
# Считаются по материализованному полю Trip.status, которое поддерживается
# в актуальном состоянии через Trip.refresh_status()/compute_status().
def _count_trips_all(qs): return qs.count()
def _count_trips_completed(qs): return qs.filter(status=Trip.STATUS_COMPLETED).count()
def _count_trips_in_work(qs): return qs.filter(status=Trip.STATUS_IN_WORK).count()
def _count_trips_sent_to_work(qs): return qs.filter(status=Trip.STATUS_SENT_TO_WORK).count()
def _count_trips_no_driver(qs):
    return qs.filter(legs__driver__isnull=True).distinct().count()
def _count_trips_no_price(qs):
    return qs.filter(legs__price__isnull=True).distinct().count()
def _count_trips_draft(qs): return qs.filter(status=Trip.STATUS_DRAFT).count()

TRIPS_DASHBOARDS = [
    {'key': 'all',          'label': 'Все заявки',   'style': 'primary',   'resolver': _count_trips_all},
    {'key': 'completed',    'label': 'Завершённые',  'style': 'success',   'resolver': _count_trips_completed},
    {'key': 'in_work',      'label': 'В работе',     'style': 'info',      'resolver': _count_trips_in_work},
    {'key': 'sent_to_work', 'label': 'Ожидают рейсов', 'style': 'warning', 'resolver': _count_trips_sent_to_work},
    {'key': 'no_driver',    'label': 'Без водителя', 'style': 'warning',   'resolver': _count_trips_no_driver},
    {'key': 'no_price',     'label': 'Без цены',     'style': 'danger',    'resolver': _count_trips_no_price},
    {'key': 'draft',        'label': 'Черновики',    'style': 'secondary', 'resolver': _count_trips_draft},
]


# --- Дашборды для Рейсов (TripLeg) ---
# FILLED_SQL/STARTED_SQL/EMPTY_SQL определены в модели TripLeg рядом с
# is_filled()/is_started(), чтобы Python- и SQL-логика не разъезжались.
def _count_legs_all(qs): return qs.count()
def _count_legs_completed(qs): return qs.filter(TripLeg.FILLED_SQL).count()
def _count_legs_in_work(qs): return qs.filter(TripLeg.STARTED_SQL).count()
def _count_legs_sent_to_work(qs): return qs.filter(TripLeg.EMPTY_SQL).count()
def _count_legs_no_driver(qs): return qs.filter(driver__isnull=True).count()
def _count_legs_no_price(qs): return qs.filter(price__isnull=True).count()

REQUESTS_DASHBOARDS = [
    {'key': 'all',          'label': 'Все рейсы',    'style': 'primary',   'resolver': _count_legs_all},
    {'key': 'completed',    'label': 'Завершённые',  'style': 'success',   'resolver': _count_legs_completed},
    {'key': 'in_work',      'label': 'В работе',     'style': 'info',      'resolver': _count_legs_in_work},
    {'key': 'sent_to_work', 'label': 'Пустые',       'style': 'warning',   'resolver': _count_legs_sent_to_work},
    {'key': 'no_driver',    'label': 'Без водителя', 'style': 'warning',   'resolver': _count_legs_no_driver},
    {'key': 'no_price',     'label': 'Без цены',     'style': 'danger',    'resolver': _count_legs_no_price},
]


REPORTS_DASHBOARDS = [
    {'key': 'cashless', 'label': 'Безналичные',    'style': 'primary'},
    {'key': 'cash',     'label': 'Наличные',       'style': 'success'},
    {'key': 'total',    'label': 'Итоговая сумма', 'style': 'dark'},
]


def compute_dashboards(qs, allowed_keys, registry, request=None):
    registry_by_key = {d['key']: d for d in registry}
    result = []
    for key in allowed_keys:
        spec = registry_by_key.get(key)
        if not spec or 'resolver' not in spec: continue
        try: count = spec['resolver'](qs)
        except Exception:
            logger.exception('Ошибка дашборда %r', key)
            count = 0
        result.append({
            'key': key, 'label': spec['label'], 'style': spec['style'], 'count': count,
            'url': build_dashboard_query(key, request), 'active': is_dashboard_active(key, request),
        })
    return result