from django.contrib import admin
from ordered_model.admin import (
    OrderedInlineModelAdminMixin,
    OrderedModelAdmin,
    OrderedTabularInline,
)

from catalog.models import ItemStatus, ItemType, Kit, KitItem


class KitItemInline(OrderedTabularInline):
    model = KitItem
    extra = 0
    fields = ["item_type", "person", "quantity", "move_up_down_links"]
    readonly_fields = ["move_up_down_links"]
    autocomplete_fields = ["item_type", "person"]
    ordering = ["position"]


@admin.register(ItemType)
class ItemTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "household"]
    list_filter = ["household"]
    search_fields = ["name", "household__name"]
    autocomplete_fields = ["household"]


@admin.register(ItemStatus)
class ItemStatusAdmin(OrderedModelAdmin):
    list_display = ["name", "household", "progress", "color", "is_default", "move_up_down_links"]
    list_filter = ["household", "progress", "is_default"]
    search_fields = ["name", "household__name"]
    autocomplete_fields = ["household"]


@admin.register(Kit)
class KitAdmin(OrderedInlineModelAdminMixin, OrderedModelAdmin):
    list_display = ["name", "household", "move_up_down_links"]
    list_filter = ["household"]
    search_fields = ["name", "household__name"]
    autocomplete_fields = ["household"]
    inlines = [KitItemInline]


@admin.register(KitItem)
class KitItemAdmin(OrderedModelAdmin):
    list_display = ["item_type", "kit", "person", "quantity", "move_up_down_links"]
    list_filter = ["kit__household"]
    search_fields = ["item_type__name", "kit__name"]
    autocomplete_fields = ["kit", "item_type", "person"]
