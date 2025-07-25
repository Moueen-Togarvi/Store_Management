# inventory/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    # Show these fields in the admin list view
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    # Add 'role' to the fieldsets and add_fieldsets for user creation/edit
    fieldsets = UserAdmin.fieldsets + (
        ('Role Info', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role Info', {'fields': ('role',)}),
    )

from .models import Product, Category, Supplier, StockHistory, CustomUser

admin.site.register(Product)
admin.site.register(Category)
admin.site.register(Supplier)
admin.site.register(StockHistory)
