"""
Команда наполнения БД демо-данными.
"""

from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from core.models import (
    Brand, Customer, Driver, PaymentType, TransportCompany,
    Trip, TripLeg, Vehicle, VehicleType,
)

User = get_user_model()
DEFAULT_PASSWORD = "dils12345"

class Command(BaseCommand):
    help = "Наполняет БД демонстрационными данными."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("→ seed_data"))
        users = self._create_users()
        self._create_lookups()
        tcs = self._create_transport_data()
        self._create_trips(users, tcs)
        self.stdout.write(self.style.SUCCESS("✅ Готово."))
        self.stdout.write("Логины (пароль у всех — {}): admin, manager, logist".format(DEFAULT_PASSWORD))

    def _create_users(self):
        specs = [
            {"username": "admin", "role": User.ROLE_ADMIN, "first_name": "Админ", "last_name": "Системный", "email": "admin@dils.local", "phone": "+7 900 000-00-01", "is_staff": True, "is_superuser": True},
            {"username": "manager", "role": User.ROLE_MANAGER, "first_name": "Иван", "last_name": "Менеджеров", "email": "manager@dils.local", "phone": "+7 900 000-00-02"},
            {"username": "logist", "role": User.ROLE_LOGIST, "first_name": "Пётр", "last_name": "Логистов", "email": "logist@dils.local", "phone": "+7 900 000-00-03"},
        ]
        result = {}
        for spec in specs:
            username = spec.pop("username")
            user, created = User.objects.get_or_create(username=username, defaults=spec)
            if created:
                user.set_password(DEFAULT_PASSWORD)
                user.save()
            result[username] = user
        return result

    def _create_lookups(self):
        for name in ["Камаз", "MAN", "Renault", "Mercedes-Benz", "Iveco", "Scania", "DAF", "Volvo", "Sitrak", "Chenglong", "Beiben"]:
            Brand.objects.get_or_create(name=name)
        for name in ["Полуприцеп", "Манипулятор", "Манипулятор с прицепом"]:
            VehicleType.objects.get_or_create(name=name)
        for name in ["Безналичные", "Нал. за доставку", "Нал. за блок и доставку", "Нал. за клей и доставку", "Нал. за блок, клей, доставку"]:
            PaymentType.objects.get_or_create(name=name)

        manager = User.objects.get(username="manager")
        for name in ["ООО «СтройБаза»", "ООО «Бетон-М»", "ИП Смирнов А.В.", "ООО «КирпичТорг»"]:
            Customer.objects.get_or_create(name=name, manager=manager)

    def _create_transport_data(self):
        data = [
            {"name": "ООО «ТрансЛогистик»", "drivers": [("Сидоров Сергей Петрович", "+7 916 111-22-33"), ("Кузнецов Андрей Иванович", "+7 916 111-22-44")], "vehicles": [("М 362 АЕ 790", "Камаз", "Полуприцеп"), ("А 121 ВС 777", "MAN", "Полуприцеп")]},
            {"name": "ИП Фёдоров", "drivers": [("Фёдоров Николай Сергеевич", "+7 916 222-33-44")], "vehicles": [("Е 456 КХ 799", "Volvo", "Манипулятор")]},
        ]
        result = []
        for tc_spec in data:
            tc, _ = TransportCompany.objects.get_or_create(name=tc_spec["name"])
            for full_name, phone in tc_spec["drivers"]:
                Driver.objects.get_or_create(transport_company=tc, full_name=full_name, defaults={"phone": phone})
            for plate, brand_name, vtype_name in tc_spec["vehicles"]:
                brand = Brand.objects.get(name=brand_name)
                vtype = VehicleType.objects.get(name=vtype_name)
                Vehicle.objects.get_or_create(transport_company=tc, plate_number=plate, defaults={"brand": brand, "vehicle_type": vtype})
            result.append(tc)
        return result

    def _create_trips(self, users, tcs):
        if Trip.objects.exists():
            self.stdout.write("  · заявки уже есть, пропуск")
            return

        manager = users["manager"]
        customer1 = Customer.objects.get(name="ООО «СтройБаза»")
        customer2 = Customer.objects.get(name="ООО «Бетон-М»")
        customer3 = Customer.objects.get(name="ИП Смирнов А.В.")

        payment_cash = PaymentType.objects.get(name="Нал. за доставку")
        payment_cashless = PaymentType.objects.get(name="Безналичные")
        today = date.today()

        # 1) Черновик
        Trip.objects.create(manager=manager, customer=customer1, delivery_info="Требуется согласование адреса доставки.")

        # 2) Отправлено в работу (1 рейс)
        t2 = Trip.objects.create(manager=manager, customer=customer2, loading_date=today, unloading_date=today + timedelta(days=2), delivery_info="Блок газобетон 600×300×200 — 20 паллет.", trips_count=1)
        TripLeg.objects.create(trip=t2)

        # 3) В работе (2 рейса)
        tc1 = tcs[0]
        t3 = Trip.objects.create(manager=manager, customer=customer3, loading_date=today - timedelta(days=1), unloading_date=today + timedelta(days=1), delivery_info="Клей плиточный — 10 мешков.", trips_count=2)
        TripLeg.objects.create(trip=t3, transport_company=tc1, driver=tc1.drivers.first(), vehicle=tc1.vehicles.first())
        TripLeg.objects.create(trip=t3)

        # 4) Выполнено (3 рейса)
        t4 = Trip.objects.create(manager=manager, customer=customer1, loading_date=today - timedelta(days=5), unloading_date=today - timedelta(days=4), delivery_info="Кирпич керамический — 2 поддона.", trips_count=3)
        for _ in range(3):
            TripLeg.objects.create(
                trip=t4, transport_company=tc1, driver=tc1.drivers.last(), vehicle=tc1.vehicles.last(),
                price=Decimal("18500.00"), payment_type=payment_cash, ttn_number="ТТН-000123"
            )

        # 5) Выполнено (1 рейс)
        tc2 = tcs[1]
        t5 = Trip.objects.create(manager=manager, customer=customer2, loading_date=today - timedelta(days=10), unloading_date=today - timedelta(days=9), delivery_info="Пеноблок — 15 паллет.", trips_count=1)
        TripLeg.objects.create(
            trip=t5, transport_company=tc2, driver=tc2.drivers.first(), vehicle=tc2.vehicles.first(),
            price=Decimal("22000.00"), payment_type=payment_cashless, ttn_number="ТТН-000124"
        )

        for t in Trip.objects.all():
            t.update_status()

        self.stdout.write("  + заявки и рейсы")