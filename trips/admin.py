from django.contrib import admin
from ordered_model.admin import (
    OrderedInlineModelAdminMixin,
    OrderedModelAdmin,
    OrderedTabularInline,
)

from trips.models import Trip, TripItem, TripParticipant


class TripParticipantInline(admin.TabularInline):
    model = TripParticipant
    extra = 0
    autocomplete_fields = ["person"]


class TripItemInline(OrderedTabularInline):
    model = TripItem
    extra = 0
    fields = ["item_type", "person", "quantity", "status", "note", "move_up_down_links"]
    readonly_fields = ["move_up_down_links"]
    autocomplete_fields = ["item_type", "person", "status"]
    ordering = ["position"]


@admin.register(Trip)
class TripAdmin(OrderedInlineModelAdminMixin, admin.ModelAdmin):
    list_display = ["name", "household", "date"]
    list_filter = ["household"]
    search_fields = ["name", "household__name"]
    autocomplete_fields = ["household"]
    inlines = [TripParticipantInline, TripItemInline]


@admin.register(TripParticipant)
class TripParticipantAdmin(admin.ModelAdmin):
    list_display = ["trip", "person"]
    list_filter = ["trip__household"]
    search_fields = ["trip__name", "person__name"]
    autocomplete_fields = ["trip", "person"]


@admin.register(TripItem)
class TripItemAdmin(OrderedModelAdmin):
    list_display = ["item_type", "trip", "person", "quantity", "status", "move_up_down_links"]
    list_filter = ["trip__household", "status"]
    search_fields = ["item_type__name", "trip__name"]
    autocomplete_fields = ["trip", "item_type", "person", "status"]
