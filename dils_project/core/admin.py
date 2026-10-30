"""
Регистрация моделей DiLS в админке Django.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Brand, Customer, Driver, PaymentType, TransportCompany,
    Trip, TripHistory, TripLeg, User, UserPreferences, Vehicle, VehicleType,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'get_full_name', 'email', 'phone', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone')
    fieldsets = BaseUserAdmin.fieldsets + (('DiLS', {'fields': ('role', 'phone')}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (('DiLS', {'fields': ('role', 'phone', 'email', 'first_name', 'last_name')}),)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'manager', 'created_at')
    list_filter = ('manager',)
    search_fields = ('name',)
    readonly_fields = ('created_at',)


@admin.register(TransportCompany)
class TransportCompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at',)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(VehicleType)
class VehicleTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(PaymentType)
class PaymentTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'transport_company', 'phone', 'created_at')
    list_filter = ('transport_company',)
    search_fields = ('full_name', 'phone')
    autocomplete_fields = ('transport_company',)
    readonly_fields = ('created_at',)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('plate_number', 'brand', 'vehicle_type', 'transport_company', 'created_at')
    list_filter = ('transport_company', 'brand', 'vehicle_type')
    search_fields = ('plate_number',)
    autocomplete_fields = ('transport_company', 'brand', 'vehicle_type')
    readonly_fields = ('created_at',)


class TripHistoryInline(admin.TabularInline):
    model = TripHistory
    extra = 0
    can_delete = False
    ordering = ('-changed_at',)
    readonly_fields = ('user', 'field_name', 'old_value', 'new_value', 'changed_at')

    def has_add_permission(self, request, obj=None):
        return False


class TripLegInline(admin.TabularInline):
    model = TripLeg
    extra = 0
    fields = ('transport_company', 'driver', 'vehicle', 'price', 'payment_type', 'ttn_number')
    autocomplete_fields = ('transport_company', 'driver', 'vehicle', 'payment_type')


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'loading_date', 'unloading_date', 'manager', 'customer', 'trips_count', 'status', 'created_at'
    )
    list_filter = ('status', 'loading_date', 'unloading_date')
    search_fields = (
        'id', 'customer__name', 'manager__username', 'manager__last_name'
    )
    date_hierarchy = 'loading_date'
    autocomplete_fields = ('manager', 'customer')
    readonly_fields = ('status', 'created_at', 'updated_at')
    inlines = [TripLegInline, TripHistoryInline]

    fieldsets = (
        ('Менеджер', {
            'fields': ('loading_date', 'unloading_date', 'manager', 'customer', 'delivery_info', 'trips_count'),
        }),
        ('Служебное', {
            'fields': ('status', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(TripLeg)
class TripLegAdmin(admin.ModelAdmin):
    list_display = ('id', 'trip', 'transport_company', 'driver', 'vehicle', 'price', 'payment_type')
    list_filter = ('transport_company', 'payment_type')
    search_fields = ('trip__id', 'driver__full_name', 'vehicle__plate_number')
    autocomplete_fields = ('trip', 'transport_company', 'driver', 'vehicle', 'payment_type')


@admin.register(TripHistory)
class TripHistoryAdmin(admin.ModelAdmin):
    list_display = ('trip', 'field_name', 'old_value', 'new_value', 'user', 'changed_at')
    list_filter = ('field_name', 'changed_at')
    search_fields = ('trip__id', 'field_name', 'old_value', 'new_value')
    readonly_fields = ('trip', 'user', 'field_name', 'old_value', 'new_value', 'changed_at')

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
    search_fields = ('user__username', 'user__last_name')
    readonly_fields = ('updated_at',)