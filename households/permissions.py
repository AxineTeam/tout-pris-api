from rest_framework.permissions import SAFE_METHODS, BasePermission

from households.models import HouseholdRole


def is_owner(household, user):
    return household.members.filter(user=user, role=HouseholdRole.OWNER).exists()


class IsSomeoneInTheHousehold(BasePermission):
    message = "Choose which person you are in this household first."

    def has_permission(self, request, view):
        return (
            request.method in SAFE_METHODS
            or view.household.persons.filter(user=request.user).exists()
        )


class IsHouseholdOwner(BasePermission):
    message = "Only an owner of this household can do that."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_owner(view.household, request.user)


class IsHouseholdOwnerOrLeavingThemselves(BasePermission):
    message = "Only an owner of this household can act on another member."

    def has_object_permission(self, request, view, member):
        if request.method == "DELETE" and member.user_id == request.user.pk:
            return True
        return is_owner(view.household, request.user)
