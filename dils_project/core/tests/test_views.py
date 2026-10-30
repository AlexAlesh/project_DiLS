"""
Тесты доступа к вьюхам DiLS.

Проверяем ролевой доступ и редиректы.
"""

from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from core.models import Customer, Trip, User


class AnonymousAccessTests(TestCase):
    """Неавторизованный пользователь — везде редирект на логин."""

    def test_trip_list_redirects(self):
        r = self.client.get(reverse("core:trip_list"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)

    def test_request_list_redirects(self):
        r = self.client.get(reverse("core:request_list"))
        self.assertEqual(r.status_code, 302)

    def test_reports_redirects(self):
        r = self.client.get(reverse("core:report_index"))
        self.assertEqual(r.status_code, 302)

    def test_settings_redirects(self):
        r = self.client.get(reverse("core:settings_index"))
        self.assertEqual(r.status_code, 302)


class ManagerAccessTests(TestCase):

    def setUp(self):
        self.manager = User.objects.create_user(
            username="mgr", password="x", role=User.ROLE_MANAGER,
        )
        self.client.login(username="mgr", password="x")

    def test_can_open_trips(self):
        r = self.client.get(reverse("core:trip_list"))
        self.assertEqual(r.status_code, 200)

    def test_cannot_open_requests(self):
        r = self.client.get(reverse("core:request_list"))
        self.assertEqual(r.status_code, 403)

    def test_cannot_open_settings(self):
        r = self.client.get(reverse("core:settings_index"))
        self.assertEqual(r.status_code, 403)

    def test_can_open_reports(self):
        r = self.client.get(reverse("core:report_index"))
        self.assertEqual(r.status_code, 200)

    def test_home_redirects_to_trips(self):
        r = self.client.get(reverse("core:home"))
        self.assertRedirects(r, reverse("core:trip_list"))


class LogistAccessTests(TestCase):

    def setUp(self):
        self.logist = User.objects.create_user(
            username="log", password="x", role=User.ROLE_LOGIST,
        )
        self.client.login(username="log", password="x")

    def test_can_open_requests(self):
        r = self.client.get(reverse("core:request_list"))
        self.assertEqual(r.status_code, 200)

    def test_cannot_open_trips(self):
        r = self.client.get(reverse("core:trip_list"))
        self.assertEqual(r.status_code, 403)

    def test_cannot_open_settings(self):
        r = self.client.get(reverse("core:settings_index"))
        self.assertEqual(r.status_code, 403)

    def test_home_redirects_to_requests(self):
        r = self.client.get(reverse("core:home"))
        self.assertRedirects(r, reverse("core:request_list"))


class AdminAccessTests(TestCase):

    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm", password="x",
            role=User.ROLE_ADMIN, is_staff=True, is_superuser=True,
        )
        self.client.login(username="adm", password="x")

    def test_can_open_settings(self):
        r = self.client.get(reverse("core:settings_index"))
        self.assertEqual(r.status_code, 200)

    def test_can_open_users_list(self):
        r = self.client.get(reverse("core:settings_users"))
        self.assertEqual(r.status_code, 200)

    def test_home_redirects_to_settings(self):
        r = self.client.get(reverse("core:home"))
        self.assertRedirects(r, reverse("core:settings_index"))


class TripCreateTests(TestCase):

    def setUp(self):
        self.manager = User.objects.create_user(
            username="mgr", password="x", role=User.ROLE_MANAGER,
        )
        self.client.login(username="mgr", password="x")

    def test_create_trip_minimal(self):
        customer = Customer.objects.create(name="ООО Тест")
        url = reverse("core:trip_create")
        r = self.client.post(url, {
            "loading_date": date.today().isoformat(),
            "unloading_date": (date.today() + timedelta(days=1)).isoformat(),
            "customer": customer.pk,
            "new_customer_name": "",
            "delivery_info": "Тестовая доставка",
        })
        # Должен быть redirect на detail
        self.assertEqual(r.status_code, 302)

        trip = Trip.objects.last()
        self.assertIsNotNone(trip)
        self.assertEqual(trip.customer, customer)
        self.assertEqual(trip.manager, self.manager)

    def test_create_new_customer_via_field(self):
        url = reverse("core:trip_create")
        r = self.client.post(url, {
            "loading_date": date.today().isoformat(),
            "unloading_date": (date.today() + timedelta(days=1)).isoformat(),
            "customer": "",
            "new_customer_name": "ООО Новый",
            "delivery_info": "",
        })
        self.assertEqual(r.status_code, 302)

        trip = Trip.objects.last()
        self.assertEqual(trip.customer.name, "ООО Новый")


class AjaxEndpointsTests(TestCase):

    def setUp(self):
        self.logist = User.objects.create_user(
            username="log", password="x", role=User.ROLE_LOGIST,
        )
        self.client.login(username="log", password="x")

    def test_dependent_select_no_tc(self):
        r = self.client.get(reverse(
            "core:ajax_dependent_select", kwargs={"kind": "drivers"},
        ))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["results"], [])

    def test_search_customers(self):
        Customer.objects.create(name="ООО Ромашка")
        r = self.client.get(reverse(
            "core:ajax_search", kwargs={"kind": "customers"},
        ), {"q": "Ромаш"})
        self.assertEqual(r.status_code, 200)
        results = r.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertIn("Ромашка", results[0]["text"])

    def test_create_customer(self):
        r = self.client.post(reverse(
            "core:ajax_create_lookup", kwargs={"kind": "customers"},
        ), {"name": "ООО Аякс"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("id", data)
        self.assertEqual(data["text"], "ООО Аякс")

    def test_save_preferences(self):
        import json as _json
        payload = {
            "page": "requests",
            "field": "filters",
            "values": ["customer"],
        }
        r = self.client.post(
            reverse("core:ajax_save_preferences"),
            data=_json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("ok"))