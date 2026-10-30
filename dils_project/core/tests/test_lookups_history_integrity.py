"""
Защита истории рейсов при удалении записей справочников (проблема №4).

Водитель/машина/ТК, участвовавшие в рейсах (TripLeg), не должны удаляться —
иначе SET_NULL/CASCADE затирает данные о выполненных рейсах.
Стратегия приведена к единой логике PROTECT для связанных с рейсами записей.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models.deletion import ProtectedError
from django.test import TestCase

from core.models import (
    Brand, Customer, Driver, PaymentType, TransportCompany,
    Trip, TripLeg, User, Vehicle, VehicleType,
)


class LookupHistoryIntegrityTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="mgr", password="x", role=User.ROLE_MANAGER)
        self.customer = Customer.objects.create(name="Заказчик")
        self.tc = TransportCompany.objects.create(name="ТК Ромашка")
        self.brand = Brand.objects.create(name="Камаз")
        self.vtype = VehicleType.objects.create(name="Полуприцеп")
        self.payment = PaymentType.objects.create(name="Безнал")
        self.driver = Driver.objects.create(transport_company=self.tc, full_name="Иванов И.")
        self.vehicle = Vehicle.objects.create(
            transport_company=self.tc, plate_number="М 362 АЕ 790",
            brand=self.brand, vehicle_type=self.vtype,
        )

    def _completed_trip_with_leg(self):
        trip = Trip.objects.create(
            manager=self.manager, customer=self.customer,
            loading_date=date.today(), unloading_date=date.today() + timedelta(days=1),
        )
        leg = TripLeg.objects.create(trip=trip, transport_company=self.tc)
        leg.driver = self.driver
        leg.vehicle = self.vehicle
        leg.price = Decimal("10000")
        leg.payment_type = self.payment
        leg.save()
        trip.refresh_from_db()
        return trip, leg

    # --- защита записанных в рейсы ---
    def test_driver_used_in_completed_trip_cannot_be_deleted(self):
        trip, leg = self._completed_trip_with_leg()
        with self.assertRaises(ProtectedError):
            self.driver.delete()
        leg.refresh_from_db()
        self.assertEqual(leg.driver_id, self.driver.pk)
        trip.refresh_from_db()
        self.assertEqual(trip.status, Trip.STATUS_COMPLETED)

    def test_vehicle_used_in_completed_trip_cannot_be_deleted(self):
        trip, leg = self._completed_trip_with_leg()
        with self.assertRaises(ProtectedError):
            self.vehicle.delete()
        leg.refresh_from_db()
        self.assertEqual(leg.vehicle_id, self.vehicle.pk)

    def test_transport_company_with_drivers_in_trips_cannot_be_deleted(self):
        trip, leg = self._completed_trip_with_leg()
        with self.assertRaises(ProtectedError):
            self.tc.delete()
        self.assertTrue(Driver.objects.filter(pk=self.driver.pk).exists())
        self.assertTrue(Vehicle.objects.filter(pk=self.vehicle.pk).exists())
        leg.refresh_from_db()
        self.assertIsNotNone(leg.driver_id)
        self.assertIsNotNone(leg.vehicle_id)

    # --- неиспользованные записи удалять можно ---
    def test_unused_driver_can_be_deleted(self):
        self.driver.delete()
        self.assertFalse(Driver.objects.filter(pk=self.driver.pk).exists())

    def test_unused_vehicle_can_be_deleted(self):
        self.vehicle.delete()
        self.assertFalse(Vehicle.objects.filter(pk=self.vehicle.pk).exists())

    def test_unused_transport_company_can_be_deleted(self):
        self.tc.delete()
        self.assertFalse(TransportCompany.objects.filter(pk=self.tc.pk).exists())

    def test_tc_with_unused_driver_can_be_deleted(self):
        """ТК с водителями/машинами без рейсов удаляется как раньше (каскад)."""
        self.tc.delete()
        self.assertFalse(TransportCompany.objects.filter(pk=self.tc.pk).exists())
        self.assertFalse(Driver.objects.filter(pk=self.driver.pk).exists())

    def test_tc_with_empty_legs_can_be_deleted(self):
        """Пустой черновик-лег не блокирует удаление ТК."""
        trip = Trip.objects.create(manager=self.manager)
        TripLeg.objects.create(trip=trip, transport_company=self.tc)
        self.tc.delete()
        self.assertFalse(TransportCompany.objects.filter(pk=self.tc.pk).exists())
