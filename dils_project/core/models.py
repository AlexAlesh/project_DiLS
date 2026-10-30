"""
Модели логистической системы DiLS.
"""

import re
from django.db import models
from django.db.models.deletion import ProtectedError
from django.contrib.auth.models import AbstractUser


def format_plate_number(value: str) -> str:
    if not value: return value
    cleaned = re.sub(r'\s+', '', str(value).upper())
    latin_to_cyrillic = {
        'A': 'А', 'B': 'В', 'E': 'Е', 'K': 'К', 'M': 'М',
        'H': 'Н', 'O': 'О', 'P': 'Р', 'C': 'С', 'T': 'Т',
        'Y': 'У', 'X': 'Х',
    }
    for lat, cyr in latin_to_cyrillic.items():
        cleaned = cleaned.replace(lat, cyr)
    match = re.match(r'^([А-Я])(\d{3})([А-Я]{2})(\d{2,3})$', cleaned)
    if match:
        return f"{match.group(1)} {match.group(2)} {match.group(3)} {match.group(4)}"
    return cleaned


class User(AbstractUser):
    ROLE_MANAGER = 'manager'
    ROLE_LOGIST = 'logist'
    ROLE_ADMIN = 'admin'
    ROLE_CHOICES = [
        (ROLE_MANAGER, 'Менеджер'), (ROLE_LOGIST, 'Логист'), (ROLE_ADMIN, 'Администратор'),
    ]

    role = models.CharField('Роль', max_length=20, choices=ROLE_CHOICES, default=ROLE_MANAGER)
    phone = models.CharField('Телефон', max_length=30, blank=True)
    color = models.CharField('Цвет рамки', max_length=7, default='#0d6efd')
    bg_color = models.CharField('Цвет заливки', max_length=7, default='#ffffff')
    role_color = models.CharField('Цвет должности', max_length=7, default='#6c757d')

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self): return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
    @property
    def is_manager(self): return self.role == self.ROLE_MANAGER
    @property
    def is_logist(self): return self.role == self.ROLE_LOGIST
    @property
    def is_admin_role(self): return self.role == self.ROLE_ADMIN or self.is_superuser
    @property
    def short_name(self):
        last = (self.last_name or '').strip()
        first = (self.first_name or '').strip()
        if last and first: return f"{last} {first[0]}."
        if last: return last
        if first: return first
        return self.get_full_name() or self.username


class Customer(models.Model):
    manager = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customers', verbose_name='Менеджер', null=True, blank=True)
    name = models.CharField('Наименование', max_length=255)
    contact_person = models.CharField('Контактное лицо', max_length=255, blank=True)
    phone = models.CharField('Телефон', max_length=30, blank=True)
    email = models.EmailField('Почта', blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Заказчик'
        verbose_name_plural = 'Заказчики'
        ordering = ['name']
        unique_together = [('manager', 'name')]

    def __str__(self): return self.name


class CustomerAddress(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='addresses', verbose_name='Заказчик')
    info = models.TextField('Информация по доставке')
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Адрес доставки заказчика'
        verbose_name_plural = 'Адреса доставки заказчиков'
        ordering = ['-created_at']
        unique_together = [('customer', 'info')]

    def __str__(self): return f"{self.customer.name}: {self.info[:30]}..."


class TransportCompany(models.Model):
    name = models.CharField('Наименование', max_length=255, unique=True)
    contact_person = models.CharField('Контактное лицо', max_length=255, blank=True)
    phone = models.CharField('Телефон', max_length=30, blank=True)
    email = models.EmailField('Почта', blank=True)
    created_at = models.DateTimeField('Создана', auto_now_add=True)
    class Meta:
        verbose_name = 'Транспортная компания'
        verbose_name_plural = 'Транспортные компании'
        ordering = ['name']
    def __str__(self): return self.name

    def delete(self, *args, **kwargs):
        """Защищает историю рейсов: ТК, чьи водители/машины участвовали в рейсах,
        удалить нельзя — иначе каскад CASCADE затрет справочник вместе со следом
        в выполненных рейсах."""
        if Driver.objects.filter(transport_company=self, legs__isnull=False).exists() or \
           Vehicle.objects.filter(transport_company=self, legs__isnull=False).exists():
            raise ProtectedError(
                f"Нельзя удалить ТК «{self.name}»: её водители или машины указаны в рейсах.",
                list(self.legs.all()),
            )
        return super().delete(*args, **kwargs)


class Brand(models.Model):
    name = models.CharField('Наименование', max_length=100, unique=True)
    class Meta:
        verbose_name = 'Марка'
        verbose_name_plural = 'Марки'
        ordering = ['name']
    def __str__(self): return self.name


class VehicleType(models.Model):
    name = models.CharField('Наименование', max_length=100, unique=True)
    class Meta:
        verbose_name = 'Тип авто'
        verbose_name_plural = 'Типы авто'
        ordering = ['name']
    def __str__(self): return self.name


class PaymentType(models.Model):
    name = models.CharField('Наименование', max_length=255, unique=True)
    class Meta:
        verbose_name = 'Тип оплаты'
        verbose_name_plural = 'Типы оплаты'
        ordering = ['name']
    def __str__(self): return self.name


class Driver(models.Model):
    transport_company = models.ForeignKey(TransportCompany, on_delete=models.CASCADE, related_name='drivers', verbose_name='Транспортная компания')
    full_name = models.CharField('ФИО', max_length=255)
    phone = models.CharField('Телефон', max_length=30, blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Водитель'
        verbose_name_plural = 'Водители'
        ordering = ['full_name']
        unique_together = [('transport_company', 'full_name')]
    def __str__(self): return self.full_name

    def delete(self, *args, **kwargs):
        """История рейсов не должна затираться: водителя, участвовавшего
        в рейсах (в т.ч. выполненных), удалить нельзя — только переименовать/перенести."""
        if self.legs.exists():
            raise ProtectedError(
                f"Нельзя удалить водителя «{self.full_name}»: он указан в рейсах.",
                list(self.legs.all()),
            )
        return super().delete(*args, **kwargs)


class Vehicle(models.Model):
    transport_company = models.ForeignKey(TransportCompany, on_delete=models.CASCADE, related_name='vehicles', verbose_name='Транспортная компания')
    plate_number = models.CharField('Гос. номер', max_length=20)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='vehicles', verbose_name='Марка')
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.PROTECT, related_name='vehicles', verbose_name='Тип авто')
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Транспортное средство'
        verbose_name_plural = 'Транспортные средства'
        ordering = ['plate_number']
        unique_together = [('transport_company', 'plate_number')]
    def __str__(self): return f"{self.plate_number} ({self.brand.name})"

    def delete(self, *args, **kwargs):
        """Защищает историю рейсов: машину, указанную в рейсах, удалить нельзя."""
        if self.legs.exists():
            raise ProtectedError(
                f"Нельзя удалить машину «{self.plate_number}»: она указана в рейсах.",
                list(self.legs.all()),
            )
        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.plate_number = format_plate_number(self.plate_number)
        super().save(*args, **kwargs)


class Trip(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SENT_TO_WORK = 'sent_to_work'
    STATUS_IN_WORK = 'in_work'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Черновик'),
        (STATUS_SENT_TO_WORK, 'Отправлено в работу'),
        (STATUS_IN_WORK, 'В работе'),
        (STATUS_COMPLETED, 'Выполнено'),
    ]

    loading_date = models.DateField('Дата загрузки', null=True, blank=True)
    unloading_date = models.DateField('Дата разгрузки', null=True, blank=True)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='managed_trips', verbose_name='Менеджер')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='trips', verbose_name='Заказчик')
    delivery_info = models.TextField('Информация по доставке', blank=True)
    trips_count = models.PositiveIntegerField('Количество рейсов', default=1)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status']), models.Index(fields=['loading_date']), models.Index(fields=['manager'])]

    def __str__(self): return f"Заявка #{self.pk}"

    def is_manager_filled(self) -> bool:
        return all([self.loading_date, self.unloading_date, self.customer])

    def update_status(self):
        legs = self.legs.all()
        if not legs.exists():
            self.status = self.STATUS_SENT_TO_WORK if self.is_manager_filled() else self.STATUS_DRAFT
        elif all(leg.is_filled() for leg in legs):
            self.status = self.STATUS_COMPLETED
        elif any(leg.is_started() for leg in legs):
            self.status = self.STATUS_IN_WORK
        elif self.is_manager_filled():
            self.status = self.STATUS_SENT_TO_WORK
        else:
            self.status = self.STATUS_DRAFT
        self.save(update_fields=['status', 'updated_at'])

    @property
    def manager_display(self) -> str:
        if not self.manager: return ''
        return self.manager.get_full_name() or self.manager.username

    @property
    def completed_legs_count(self) -> int:
        return sum(1 for leg in self.legs.all() if leg.is_filled())


class TripLeg(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_IN_WORK = 'in_work'
    STATUS_COMPLETED = 'completed'

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='legs', verbose_name='Заявка')
    transport_company = models.ForeignKey(TransportCompany, on_delete=models.SET_NULL, null=True, blank=True, related_name='legs', verbose_name='Транспортная компания')
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='legs', verbose_name='Водитель')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='legs', verbose_name='Транспортное средство')
    price = models.DecimalField('Цена', max_digits=12, decimal_places=2, null=True, blank=True)
    payment_type = models.ForeignKey(PaymentType, on_delete=models.SET_NULL, null=True, blank=True, related_name='legs', verbose_name='Тип оплаты')
    ttn_number = models.CharField('№ ТТН', max_length=100, blank=True)
    logist_comment = models.TextField('Комментарий логиста', blank=True)
    logist_viewed = models.BooleanField('Просмотрено логистом', default=False)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Рейс'
        verbose_name_plural = 'Рейсы'
        ordering = ['id']

    def __str__(self): return f"Рейс #{self.pk} (Заявка #{self.trip_id})"

    def is_filled(self) -> bool:
        return all([self.transport_company, self.driver, self.vehicle, self.price is not None, self.payment_type])

    def is_started(self) -> bool:
        return any([self.transport_company, self.driver, self.vehicle, self.price is not None, self.payment_type, self.ttn_number])

    @property
    def status(self) -> str:
        if self.is_filled(): return self.STATUS_COMPLETED
        if self.is_started(): return self.STATUS_IN_WORK
        return self.STATUS_DRAFT

    def update_trip_status(self):
        self.trip.update_status()

    @property
    def is_new_for_logist(self) -> bool:
        return self.trip.status in (Trip.STATUS_SENT_TO_WORK, Trip.STATUS_IN_WORK) and not self.logist_viewed

    @property
    def brand_name(self) -> str:
        return self.vehicle.brand.name if self.vehicle and self.vehicle.brand else ''

    @property
    def vehicle_type_name(self) -> str:
        return self.vehicle.vehicle_type.name if self.vehicle and self.vehicle.vehicle_type else ''

    @property
    def plate_number(self) -> str:
        return self.vehicle.plate_number if self.vehicle else ''

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_trip_status()


class TripHistory(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='history', verbose_name='Заявка')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Пользователь')
    field_name = models.CharField('Поле', max_length=100)
    old_value = models.TextField('Было', blank=True)
    new_value = models.TextField('Стало', blank=True)
    changed_at = models.DateTimeField('Изменено', auto_now_add=True)

    class Meta:
        verbose_name = 'История изменения'
        verbose_name_plural = 'История изменений'
        ordering = ['-changed_at']

    def __str__(self): return f"{self.trip_id}: {self.field_name}"


class UserPreferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences', verbose_name='Пользователь')
    trips_visible_filters = models.JSONField(default=list, blank=True)
    requests_visible_filters = models.JSONField(default=list, blank=True)
    reports_visible_filters = models.JSONField(default=list, blank=True)
    trips_visible_dashboards = models.JSONField(default=list, blank=True)
    requests_visible_dashboards = models.JSONField(default=list, blank=True)
    reports_visible_dashboards = models.JSONField(default=list, blank=True)

    # НОВЫЕ ПОЛЯ
    driver_trips_visible_fields = models.JSONField('Поля в Рейсах водителей', default=list, blank=True)
    driver_trips_default_tcs = models.JSONField('ТК по умолчанию (Рейсы водителей)', default=list, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Настройки'
        verbose_name_plural = 'Настройки'

    def __str__(self): return f"Настройки: {self.user}"

    TRIPS_DEFAULT_FILTERS = ['loading_date', 'unloading_date', 'manager', 'customer', 'transport_company', 'driver']
    REQUESTS_DEFAULT_FILTERS = ['loading_date', 'unloading_date', 'manager', 'customer', 'transport_company', 'driver', 'plate_number', 'brand', 'vehicle_type', 'payment_type']
    REPORTS_DEFAULT_FILTERS = ['loading_date', 'unloading_date', 'transport_company', 'driver', 'plate_number', 'brand', 'vehicle_type', 'payment_type', 'price', 'ttn_number']
    TRIPS_DEFAULT_DASHBOARDS = ['all', 'completed', 'in_work', 'no_driver', 'no_price', 'draft']
    REQUESTS_DEFAULT_DASHBOARDS = ['all', 'completed', 'in_work', 'no_driver', 'no_price']
    REPORTS_DEFAULT_DASHBOARDS = ['cashless', 'cash', 'total']

    # ДЕФОЛТНЫЕ ПОЛЯ ДЛЯ "РЕЙСЫ ВОДИТЕЛЕЙ"
    DRIVER_TRIPS_DEFAULT_FIELDS = [
        'loading_date', 'unloading_date', 'customer', 'manager',
        'delivery_info', 'transport_company', 'driver', 'vehicle',
        'price', 'payment_type', 'comment'
    ]

    @classmethod
    def get_for_user(cls, user) -> 'UserPreferences':
        obj, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'trips_visible_filters': cls.TRIPS_DEFAULT_FILTERS,
                'requests_visible_filters': cls.REQUESTS_DEFAULT_FILTERS,
                'reports_visible_filters': cls.REPORTS_DEFAULT_FILTERS,
                'trips_visible_dashboards': cls.TRIPS_DEFAULT_DASHBOARDS,
                'requests_visible_dashboards': cls.REQUESTS_DEFAULT_DASHBOARDS,
                'reports_visible_dashboards': cls.REPORTS_DEFAULT_DASHBOARDS,
                'driver_trips_visible_fields': cls.DRIVER_TRIPS_DEFAULT_FIELDS,
            },
        )
        return obj