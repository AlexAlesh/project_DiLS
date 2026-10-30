"""
Тесты моделей DiLS.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from core.models import (
    Brand,
    Customer,
    Driver,
    PaymentType,
    TransportCompany,
    Trip,
    User,
    Vehicle,
    VehicleType,
    format_plate_number,
)


class FormatPlateNumberTests(TestCase):
    """Проверка автоформатирования гос. номера."""

    def test_full_cyrillic(self):
        self.assertEqual(
            format_plate_number("М362АЕ790"),
            "М 362 АЕ 790",
        )

    def test_with_spaces(self):
        self.assertEqual(
            format_plate_number("М 362 АЕ 790"),
            "М 362 АЕ 790",
        )

    def test_lowercase(self):
        self.assertEqual(
            format_plate_number("м362еа790"),
            "М 362 АЕ 790",
        )

    def test_latin_to_cyrillic(self):
        self.assertEqual(
            format_plate_number("M362AE790"),
            "М 362 АЕ 790",
        )

    def test_three_digit_region(self):
        self.assertEqual(
            format_plate_number("а123вс777"),
            "А 123 ВС 777",
        )

    def test_empty(self):
        self.assertEqual(format_plate_number(""), "")

    def test_garbage(self):
        # Не падает, возвращает хотя бы нормализованную строку
        result = format_plate_number("abc")
        self.assertIsInstance(result, str)


class UserModelTests(TestCase):

    def test_role_flags(self):
        m = User(username="m1", role=User.ROLE_MANAGER)
        l = User(username="l1", role=User.ROLE_LOGIST)
        a = User(username="a1", role=User.ROLE_ADMIN)

        self.assertTrue(m.is_manager)
        self.assertFalse(m.is_logist)
        self.assertFalse(m.is_admin_role)

        self.assertTrue(l.is_logist)
        self.assertFalse(l.is_manager)

        self.assertTrue(a.is_admin_role)

    def test_short_name(self):
        u = User(username="x", first_name="Иван", last_name="Иванов",
                 role=User.ROLE_MANAGER)
        self.assertEqual(u.short_name, "Иванов И.")

        u2 = User(username="y", first_name="Пётр", last_name="Петров",
                  role=User.ROLE_MANAGER)
        u2.middle_name = "Сергеевич"  # не модель — просто проверка без отчества
        self.assertEqual(u2.short_name, "Петров П.")


class TripStatusTests(TestCase):
    """Проверка логики статусов."""

    def setUp(self):
        self.manager = User.objects.create_user(
            username="mgr", password="x", role=User.ROLE_MANAGER,
        )
        self.customer = Customer.objects.create(name="Заказчик")
        self.tc = TransportCompany.objects.create(name="ТК")
        self.brand = Brand.objects.create(name="Камаз")
        self.vtype = VehicleType.objects.create(name="Полуприцеп")
        self.payment = PaymentType.objects.create(name="Безналичные")

        self.driver = Driver.objects.create(
            transport_company=self.tc, full_name="Иванов Иван",
        )
        self.vehicle = Vehicle.objects.create(
            transport_company=self.tc,
            plate_number="М 362 АЕ 790",
            brand=self.brand,
            vehicle_type=self.vtype,
        )

    def test_draft_status_when_empty(self):
        trip = Trip.objects.create(manager=self.manager)
        self.assertEqual(trip.status, Trip.STATUS_DRAFT)

    def test_sent_to_work_when_manager_filled(self):
        trip = Trip.objects.create(
            manager=self.manager,
            customer=self.customer,
            loading_date=date.today(),
            unloading_date=date.today() + timedelta(days=1),
        )
        trip.refresh_from_db()
        self.assertEqual(trip.status, Trip.STATUS_SENT_TO_WORK)

    def test_in_work_when_logist_started(self):
        trip = Trip.objects.create(
            manager=self.manager,
            customer=self.customer,
            loading_date=date.today(),
            unloading_date=date.today() + timedelta(days=1),
        )
        trip.price = Decimal("1000.00")
        trip.save()
        trip.refresh_from_db()
        self.assertEqual(trip.status, Trip.STATUS_IN_WORK)

    def test_completed_when_all_filled(self):
        trip = Trip.objects.create(
            manager=self.manager,
            customer=self.customer,
            loading_date=date.today(),
            unloading_date=date.today() + timedelta(days=1),
            transport_company=self.tc,
            driver=self.driver,
            vehicle=self.vehicle,
            price=Decimal("18500.00"),
            payment_type=self.payment,
            ttn_number="ТТН-1",
        )
        trip.refresh_from_db()
        self.assertEqual(trip.status, Trip.STATUS_COMPLETED)

    def test_plate_number_property(self):
        trip = Trip.objects.create(
            manager=self.manager,
            vehicle=self.vehicle,
        )
        self.assertEqual(trip.plate_number, "М 362 АЕ 790")
        self.assertEqual(trip.brand_name, "Камаз")
        self.assertEqual(trip.vehicle_type_name, "Полуприцеп")


class VehicleFormattingTests(TestCase):
    """Сохранение Vehicle нормализует номер."""

    def test_plate_formatted_on_save(self):
        tc = TransportCompany.objects.create(name="ТК")
        brand = Brand.objects.create(name="Volvo")
        vtype = VehicleType.objects.create(name="Полуприцеп")

        v = Vehicle.objects.create(
            transport_company=tc,
            plate_number="м362еа790",
            brand=brand,
            vehicle_type=vtype,
        )
        v.refresh_from_db()
        self.assertEqual(v.plate_number, "М 362 АЕ 790")


class TripHistoryTests(TestCase):
    """Логирование изменений в TripHistory."""

    def setUp(self):
        self.manager = User.objects.create_user(
            username="mgr", password="x", role=User.ROLE_MANAGER,
        )

    def test_creation_logged(self):
        trip = Trip.objects.create(manager=self.manager)
        self.assertTrue(
            trip.history.filter(field_name="__created__").exists(),
        )

    def test_update_logged(self):
        trip = Trip.objects.create(manager=self.manager)
        trip.ttn_number = "ТТН-777"
        trip.save()

        entries = trip.history.filter(field_name="№ ТТН")
        self.assertTrue(entries.exists())
        entry = entries.first()
        self.assertEqual(entry.new_value, "ТТН-777")


class UserPreferencesTests(TestCase):

    def test_auto_created_on_user(self):
        u = User.objects.create_user(username="u1", password="x")
        self.assertTrue(hasattr(u, "preferences"))

    def test_defaults_applied(self):
        u = User.objects.create_user(username="u2", password="x")
        prefs = u.preferences
        self.assertTrue(prefs.trips_visible_filters)
        self.assertIn("all", prefs.trips_visible_dashboards)