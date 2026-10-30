"""
Формы DiLS.
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q

from .models import (
    Brand, Customer, CustomerAddress, Driver, PaymentType, TransportCompany,
    Trip, TripLeg, User, Vehicle, VehicleType, format_plate_number,
)


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Логин", widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True}))
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput(attrs={"class": "form-control"}))


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["last_name", "first_name", "phone", "email", "color", "bg_color", "role_color"]
        widgets = {
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "color": forms.TextInput(attrs={"class": "form-control form-control-color", "type": "color"}),
            "bg_color": forms.TextInput(attrs={"class": "form-control form-control-color", "type": "color"}),
            "role_color": forms.TextInput(attrs={"class": "form-control form-control-color", "type": "color"}),
        }


# Справочники
class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": "form-control"})}

class TransportCompanyForm(forms.ModelForm):
    class Meta:
        model = TransportCompany
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": "form-control"})}

class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": "form-control"})}

class VehicleTypeForm(forms.ModelForm):
    class Meta:
        model = VehicleType
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": "form-control"})}

class PaymentTypeForm(forms.ModelForm):
    class Meta:
        model = PaymentType
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": "form-control"})}


# Водители и машины
class DriverForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = ["transport_company", "full_name", "phone"]
        widgets = {
            "transport_company": forms.Select(attrs={"class": "form-select"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
        }

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["transport_company", "plate_number", "brand", "vehicle_type"]
        widgets = {
            "transport_company": forms.Select(attrs={"class": "form-select"}),
            "plate_number": forms.TextInput(attrs={"class": "form-control", "data-plate-input": "1"}),
            "brand": forms.Select(attrs={"class": "form-select"}),
            "vehicle_type": forms.Select(attrs={"class": "form-select"}),
        }
    def clean_plate_number(self): return format_plate_number(self.cleaned_data["plate_number"])


# ============================================================
# ЗАЯВКА — часть менеджера
# ============================================================

class TripManagerForm(forms.ModelForm):
    new_customer_name = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Trip
        fields = ["loading_date", "unloading_date", "customer", "delivery_info", "trips_count"]
        widgets = {
            "loading_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "unloading_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "customer": forms.Select(attrs={"class": "form-select"}),
            "delivery_info": forms.Textarea(attrs={"class": "form-control", "rows": 3, "id": "id_delivery_info"}),
            "trips_count": forms.NumberInput(attrs={"class": "form-control text-center fw-bold fs-5", "min": "1", "style": "color: #0d6efd;"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        # trips_count необязателен в POST: если поле отсутствует или пустое,
        # используем default из модели (1). Модель гарантирует default=1.
        self.fields["trips_count"].required = False
        q = Q(manager__isnull=True)
        if user and user.is_manager: q |= Q(manager=user)
        if self.instance and self.instance.pk and self.instance.customer_id:
            q |= Q(pk=self.instance.customer_id)

        if user and user.is_manager:
            self.fields["customer"].queryset = Customer.objects.filter(q).distinct().order_by("name")
        else:
            self.fields["customer"].queryset = Customer.objects.all().order_by("name")

        self.fields["customer"].required = False
        self.fields["customer"].empty_label = "— выберите заказчика —"
        self.fields["loading_date"].input_formats = ["%Y-%m-%d"]
        self.fields["unloading_date"].input_formats = ["%Y-%m-%d"]

    def clean_trips_count(self):
        # Пустое/отсутствующее значение → default модели (1).
        value = self.cleaned_data.get("trips_count")
        if value is None:
            value = Trip._meta.get_field("trips_count").get_default()
        return max(1, int(value))

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get("customer")
        # Создание нового заказчика по имени (скрытое поле new_customer_name).
        if not customer:
            raw_name = (self.data.get("new_customer_name") or "").strip() \
                if hasattr(self.data, "get") else ""
            if raw_name:
                manager = self.user if (self.user and self.user.is_manager) else None
                qs = Customer.objects.filter(name__iexact=raw_name)
                if manager:
                    qs = qs.filter(Q(manager=manager) | Q(manager__isnull=True))
                existing = qs.distinct().first()
                if existing:
                    # Защита от дублей: переиспользуем существующего клиента.
                    if not existing.manager and manager:
                        existing.manager = manager
                        existing.save(update_fields=["manager"])
                    cleaned["customer"] = existing
                    self.instance.customer = existing
                    customer = existing
                else:
                    customer = Customer.objects.create(name=raw_name, manager=manager)
                    cleaned["customer"] = customer
                    self.instance.customer = customer

        if not customer:
            self.add_error("customer", "Выберите заказчика из списка.")
        elif customer and not customer.manager and self.user and self.user.is_manager:
            customer.manager = self.user
            customer.save()

        # Проверка дат: разгрузка не раньше загрузки.
        date_start = cleaned.get("loading_date")
        date_end = cleaned.get("unloading_date")
        if date_start and date_end and date_end < date_start:
            self.add_error("unloading_date", "Дата разгрузки не может быть раньше даты загрузки.")
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()

            # 1. Сохраняем адрес (инфо по доставке) в историю заказчика
            if instance.customer and instance.delivery_info:
                CustomerAddress.objects.get_or_create(
                    customer=instance.customer,
                    info=instance.delivery_info.strip()
                )

            # 2. Создаем/удаляем TripLeg (рейсы)
            current_count = instance.legs.count()
            target_count = instance.trips_count
            if target_count > current_count:
                for _ in range(target_count - current_count):
                    TripLeg.objects.create(trip=instance)
            elif target_count < current_count:
                empty_legs = instance.legs.filter(transport_company__isnull=True, driver__isnull=True, vehicle__isnull=True, price__isnull=True)
                for leg in empty_legs[current_count - target_count:]:
                    leg.delete()
        return instance


# ============================================================
# РЕЙС — часть логиста
# ============================================================

class TripLogistForm(forms.ModelForm):
    class Meta:
        model = TripLeg
        fields = ["transport_company", "driver", "vehicle", "price", "payment_type", "ttn_number", "logist_comment"]
        widgets = {
            "transport_company": forms.Select(attrs={"class": "form-select"}),
            "driver": forms.Select(attrs={"class": "form-select"}),
            "vehicle": forms.Select(attrs={"class": "form-select"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "payment_type": forms.Select(attrs={"class": "form-select"}),
            "ttn_number": forms.TextInput(attrs={"class": "form-control"}),
            "logist_comment": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        company = cleaned.get("transport_company")
        driver = cleaned.get("driver")
        vehicle = cleaned.get("vehicle")
        # Водитель и машина должны принадлежать выбранной ТК.
        if company:
            if driver and driver.transport_company_id != company.pk:
                self.add_error("driver", f"Водитель «{driver}» не принадлежит ТК «{company}».")
            if vehicle and vehicle.transport_company_id != company.pk:
                self.add_error("vehicle", f"Машина «{vehicle}» не принадлежит ТК «{company}».")
        return cleaned


# ============================================================
# ФИЛЬТРЫ
# ============================================================

class TripFilterForm(forms.Form):
    @staticmethod
    def filter_choices(user=None):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        customers_qs = Customer.objects.all()
        if user and user.is_manager:
            customers_qs = customers_qs.filter(Q(manager=user) | Q(manager__isnull=True)).distinct()

        return {
            "manager": [("", "Все")] + [(u.pk, u.short_name) for u in User.objects.filter(role=User.ROLE_MANAGER).order_by("last_name", "first_name")],
            "customer": [("", "Все")] + [(c.pk, c.name) for c in customers_qs.order_by("name")],
            "transport_company": [("", "Все")] + [(t.pk, t.name) for t in TransportCompany.objects.all()],
            "driver": [("", "Все")] + [(d.pk, d.full_name) for d in Driver.objects.all()],
            "brand": [("", "Все")] + [(b.pk, b.name) for b in Brand.objects.all()],
            "vehicle_type": [("", "Все")] + [(v.pk, v.name) for v in VehicleType.objects.all()],
            "payment_type": [("", "Все")] + [(p.pk, p.name) for p in PaymentType.objects.all()],
            "vehicle": [("", "Все")] + [(v.pk, f"{v.plate_number} ({v.brand.name})") for v in Vehicle.objects.select_related("brand")],
        }


class ReportFilterForm(forms.Form):
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))