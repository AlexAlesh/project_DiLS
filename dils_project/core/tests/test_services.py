"""
Тесты сервисов DiLS.
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
)
from core.services.report_service import (
    aggregate_totals,
    build_report_as_dict,
    completed_qs,
    group_by_driver,
    group_by_transport_company,
    group_by_vehicle,
)
from core.services.trip_service import (
    can_edit_as_logist,
    can_edit_as_manager,
    mark_as_viewed,
)


class TripServicePermissionTests(TestCase):

    def setUp(self):
        self.manager1 = User.objects.create_user(
            username="m1", password="x", role=User.ROLE_MANAGER,
        )
        self.manager2 = User.objects.create_user(
            username="m2", password="x", role=User.ROLE_MANAGER,
        )
        self.logist = User.objects.create_user(
            username="l1", password="x", role=User.ROLE_LOGIST,
        )
        self.admin = User.objects.create_user(
            username="a1", password="x",
            role=User.ROLE_ADMIN, is_superuser=True,
        )
        self.trip = Trip.objects.create(manager=self.manager1)

    def test_manager_can_edit_own(self):
        self.assertTrue(can_edit_as_manager(self.manager1, self.trip))

    def test_manager_cannot_edit_other(self):
        self.assertFalse(can_edit_as_manager(self.manager2, self.trip))

    def test_admin_can_edit_any(self):
        self.assertTrue(can_edit_as_manager(self.admin, self.trip))

    def test_logist_cannot_edit_manager_part(self):
        self.assertFalse(can_edit_as_manager(self.logist, self.trip))

    def test_logist_can_edit_logist_part(self):
        self.assertTrue(can_edit_as_logist(self.logist, self.trip))

    def test_manager_cannot_edit_logist_part(self):
        self.assertFalse(can_edit_as_logist(self.manager1, self.trip))

    def test_mark_as_viewed(self):
        self.assertFalse(self.trip.logist_viewed)
        mark_as_viewed(self.trip)
        self.trip.refresh_from_db()
        self.assertTrue(self.trip.logist_viewed)


class ReportServiceTests(TestCase):

    def setUp(self):
        self.manager = User.objects.create_user(
            username="mgr", password="x", role=User.ROLE_MANAGER,
        )
        self.customer = Customer.objects.create(name="Заказчик")

        self.tc1 = TransportCompany.objects.create(name="ТК-1")
        self.tc2 = TransportCompany.objects.create(name="ТК-2")

        self.brand = Brand.objects.create(name="Камаз")
        self.vtype = VehicleType.objects.create(name="Полуприцеп")
        self.cash = PaymentType.objects.create(name="Нал. за доставку")
        self.cashless = PaymentType.objects.create(name="Безналичные")

        self.driver1 = Driver.objects.create(
            transport_company=self.tc1, full_name="Водитель 1",
        )
        self.driver2 = Driver.objects.create(
            transport_company=self.tc2, full_name="Водитель 2",
        )

        self.vehicle1 = Vehicle.objects.create(
            transport_company=self.tc1, plate_number="М 362 АЕ 790",
            brand=self.brand, vehicle_type=self.vtype,
        )
        self.vehicle2 = Vehicle.objects.create(
            transport_company=self.tc2, plate_number="А 121 ВС 777",
            brand=self.brand, vehicle_type=self.vtype,
        )

        # 2 завершённых (1 нал, 1 безнал), 1 в работе
        self._trip_completed(self.tc1, self.driver1, self.vehicle1,
                             self.cash, Decimal("10000.00"))
        self._trip_completed(self.tc2, self.driver2, self.vehicle2,
                             self.cashless, Decimal("20000.00"))
        self._trip_in_work()

    def _trip_completed(self, tc, driver, vehicle, payment, price):
        return Trip.objects.create(
            manager=self.manager,
            customer=self.customer,
            loading_date=date.today(),
            unloading_date=date.today() + timedelta(days=1),
            transport_company=tc,
            driver=driver,
            vehicle=vehicle,
            price=price,
            payment_type=payment,
            ttn_number="Т",
        )

    def _trip_in_work(self):
        return Trip.objects.create(
            manager=self.manager,
            customer=self.customer,
            loading_date=date.today(),
            unloading_date=date.today() + timedelta(days=1),
            price=Decimal("500.00"),  # неполный — будет "В работе"
        )

    def test_completed_qs_only_completed(self):
        qs = completed_qs()
        self.assertEqual(qs.count(), 2)

    def test_aggregate_totals(self):
        qs = completed_qs()
        totals = aggregate_totals(qs)

        self.assertEqual(totals["count"], 2)
        self.assertEqual(totals["cash"], Decimal("10000.00"))
        self.assertEqual(totals["cashless"], Decimal("20000.00"))
        self.assertEqual(totals["total"], Decimal("30000.00"))

    def test_group_by_transport_company(self):
        qs = completed_qs()
        groups = group_by_transport_company(qs)
        self.assertEqual(len(groups), 2)
        self.assertTrue(all(g["trips"] == 1 for g in groups))

    def test_group_by_driver(self):
        qs = completed_qs()
        groups = group_by_driver(qs)
        self.assertEqual(len(groups), 2)
        names = {g["driver__full_name"] for g in groups}
        self.assertIn("Водитель 1", names)
        self.assertIn("Водитель 2", names)

    def test_group_by_vehicle(self):
        qs = completed_qs()
        groups = group_by_vehicle(qs)
        self.assertEqual(len(groups), 2)

    def test_build_report_as_dict_structure(self):
        qs = completed_qs()
        report = build_report_as_dict(qs)

        self.assertIn("totals", report)
        self.assertIn("by_transport_company", report)
        self.assertIn("by_driver", report)
        self.assertIn("by_vehicle", report)
        self.assertIn("by_payment_type", report)

        self.assertEqual(report["totals"]["count"], 2)
        self.assertEqual(report["totals"]["total"], Decimal("30000.00"))

    def test_in_work_trip_not_in_report(self):
        """Рейс со статусом «В работе» не должен попадать в отчёт."""
        qs = completed_qs()
        trip_ids = set(qs.values_list("id", flat=True))
        in_work = Trip.objects.filter(price=Decimal("500.00")).first()
        self.assertNotIn(in_work.pk, trip_ids)