"""Тесты исправлений core/forms.py (валидация дат, new_customer_name, привязка к ТК)."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from core.forms import TripLogistForm, TripManagerForm
from core.models import (Brand, Customer, Driver, TransportCompany, Trip,
                         TripLeg, Vehicle, VehicleType)


class FormsFixTests(TestCase):
    def setUp(self):
        self.c = Customer.objects.create(name="ТестКлиент")
        self.tc1 = TransportCompany.objects.create(name="ТК1")
        self.tc2 = TransportCompany.objects.create(name="ТК2")
        self.d = Driver.objects.create(transport_company=self.tc1, full_name="Иванов И.")
        self.brand = Brand.objects.create(name="КАМАЗ")
        self.vt = VehicleType.objects.create(name="Фура")
        self.v = Vehicle.objects.create(transport_company=self.tc1, plate_number="А123ВС77",
                                        brand=self.brand, vehicle_type=self.vt)

    def test_trips_count_missing_defaults_to_one(self):
        f = TripManagerForm(data={'loading_date': '2026-10-30', 'unloading_date': '2026-10-31',
                                  'customer': self.c.pk, 'delivery_info': 'x'})
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(f.cleaned_data['trips_count'], 1)

    def test_trips_count_zero_normalized(self):
        f = TripManagerForm(data={'loading_date': '2026-10-30', 'unloading_date': '2026-10-31',
                                  'customer': self.c.pk, 'delivery_info': 'x', 'trips_count': 0})
        self.assertTrue(f.is_valid())
        self.assertEqual(f.cleaned_data['trips_count'], 1)

    def test_unloading_before_loading_rejected(self):
        f = TripManagerForm(data={'loading_date': '2026-12-10', 'unloading_date': '2026-12-01',
                                  'customer': self.c.pk})
        self.assertFalse(f.is_valid())
        self.assertIn('unloading_date', f.errors)

    def test_valid_dates_pass(self):
        f = TripManagerForm(data={'loading_date': '2026-12-01', 'unloading_date': '2026-12-10',
                                  'customer': self.c.pk})
        self.assertTrue(f.is_valid(), f.errors)

    def test_leg_driver_vehicle_tc_mismatch(self):
        leg = TripLeg.objects.create(trip=Trip.objects.create(customer=self.c))
        f = TripLogistForm(data={'transport_company': self.tc2.pk, 'driver': self.d.pk,
                                 'vehicle': self.v.pk, 'price': 1000}, instance=leg)
        self.assertFalse(f.is_valid())
        self.assertIn('driver', f.errors)
        self.assertIn('vehicle', f.errors)

    def test_leg_same_tc_passes(self):
        leg = TripLeg.objects.create(trip=Trip.objects.create(customer=self.c))
        f = TripLogistForm(data={'transport_company': self.tc1.pk, 'driver': self.d.pk,
                                 'vehicle': self.v.pk, 'price': 1000}, instance=leg)
        self.assertTrue(f.is_valid(), f.errors)


class NewCustomerByNameTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.mgr = User.objects.create_user(username="mgr1", password="x",
                                            role=User.ROLE_MANAGER, last_name="M")

    def test_create_new_customer_via_hidden_field(self):
        f = TripManagerForm(data={'loading_date': '2026-10-30', 'unloading_date': '2026-10-31',
                                  'customer': '', 'delivery_info': 'x',
                                  'new_customer_name': 'Ромашка'}, user=self.mgr)
        self.assertTrue(f.is_valid(), f.errors)
        c = Customer.objects.filter(name='Ромашка').first()
        self.assertIsNotNone(c)
        self.assertEqual(c.manager_id, self.mgr.pk)

    def test_no_duplicate_by_case_insensitive_name(self):
        Customer.objects.create(name='ромашка', manager=self.mgr)
        f = TripManagerForm(data={'loading_date': '2026-10-30', 'unloading_date': '2026-10-31',
                                  'customer': '', 'new_customer_name': 'РОМАШКА'}, user=self.mgr)
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(Customer.objects.filter(name__iexact='ромашка').count(), 1)

    def test_empty_customer_still_errors(self):
        f = TripManagerForm(data={'loading_date': '2026-10-30', 'unloading_date': '2026-10-31',
                                  'customer': ''}, user=self.mgr)
        self.assertFalse(f.is_valid())
        self.assertIn('customer', f.errors)
