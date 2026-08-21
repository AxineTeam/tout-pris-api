from django.contrib import admin

from households.models import Household, HouseholdMember, Invitation, Person


class HouseholdMemberInline(admin.TabularInline):
    model = HouseholdMember
    extra = 0
    autocomplete_fields = ["user"]


class PersonInline(admin.TabularInline):
    model = Person
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ["name", "personal_of", "created_at"]
    search_fields = ["name"]
    autocomplete_fields = ["personal_of"]
    inlines = [HouseholdMemberInline, PersonInline]


@admin.register(HouseholdMember)
class HouseholdMemberAdmin(admin.ModelAdmin):
    list_display = ["household", "user", "role"]
    list_filter = ["role"]
    search_fields = ["household__name", "user__username", "user__email"]
    autocomplete_fields = ["household", "user"]


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ["name", "household", "user"]
    list_filter = ["household"]
    search_fields = ["name", "household__name"]
    autocomplete_fields = ["household", "user"]


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "household", "invited_by", "expires_at", "accepted_at"]
    list_filter = ["household"]
    search_fields = ["email", "household__name"]
    autocomplete_fields = ["household", "person", "invited_by", "accepted_by"]
    readonly_fields = ["token_hash", "created_at"]
