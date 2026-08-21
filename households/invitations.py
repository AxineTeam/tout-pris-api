from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from accounts.models import User
from households.models import HouseholdMember, Invitation, Person
from households.signals import display_name_of


@transaction.atomic
def invite(household, email, invited_by, person=None):
    Invitation.objects.filter(household=household, email=email, accepted_at=None).delete()
    if HouseholdMember.objects.filter(household=household, user__email=email).exists():
        return None
    invitation = Invitation.objects.create(
        household=household, email=email, invited_by=invited_by, person=person
    )
    transaction.on_commit(lambda: send_invitation(invitation))
    return invitation


def send_invitation(invitation):
    known_account = User.objects.filter(email=invitation.email).exists()
    template = "invitation_existing_account" if known_account else "invitation_new_account"
    context = {
        "household": invitation.household.name,
        "inviter": display_name_of(invitation.invited_by),
        "url": settings.INVITATION_FRONTEND_URL.format(key=invitation.token),
        "expires_at": invitation.expires_at.date().isoformat(),
    }
    EmailMessage(
        subject=render_to_string("households/email/invitation_subject.txt", context).strip(),
        body=render_to_string(f"households/email/{template}.txt", context),
        to=[invitation.email],
    ).send()


def pending_invitation(token):
    return Invitation.objects.filter(
        token=token, accepted_at=None, expires_at__gt=timezone.now()
    ).first()


@transaction.atomic
def accept(invitation, user):
    household = invitation.household
    invitation.accepted_at = timezone.now()
    invitation.accepted_by = user
    invitation.save()

    if HouseholdMember.objects.filter(household=household, user=user).exists():
        return household

    HouseholdMember.objects.create(household=household, user=user)
    claim_person(invitation, user)
    return household


def claim_person(invitation, user):
    person = invitation.person
    if person and person.household_id == invitation.household_id and person.user_id is None:
        person.user = user
        person.save()
        return
    Person.objects.create(household=invitation.household, user=user, name=display_name_of(user))
