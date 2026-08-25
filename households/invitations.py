import hashlib
import secrets

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from accounts.models import User
from households.memberships import display_name_of
from households.models import HouseholdMember, Invitation


def hashed(token):
    return hashlib.sha256(token.encode()).hexdigest()


@transaction.atomic
def invite(household, email, invited_by):
    Invitation.objects.filter(household=household, email=email, accepted_at=None).delete()
    if HouseholdMember.objects.filter(household=household, user__email=email).exists():
        return None
    token = secrets.token_urlsafe()
    invitation = Invitation.objects.create(
        household=household,
        email=email,
        invited_by=invited_by,
        token_hash=hashed(token),
    )
    transaction.on_commit(lambda: send_invitation(invitation, token))
    return invitation


def send_invitation(invitation, token):
    known_account = User.objects.filter(email=invitation.email).exists()
    template = "invitation_existing_account" if known_account else "invitation_new_account"
    context = {
        "household": invitation.household.name,
        "inviter": display_name_of(invitation.invited_by),
        "url": settings.INVITATION_FRONTEND_URL.format(key=token),
        "expires_at": invitation.expires_at.date().isoformat(),
    }
    EmailMessage(
        subject=render_to_string("households/email/invitation_subject.txt", context).strip(),
        body=render_to_string(f"households/email/{template}.txt", context),
        to=[invitation.email],
    ).send()


def pending_invitation(token):
    return Invitation.objects.filter(
        token_hash=hashed(token), accepted_at=None, expires_at__gt=timezone.now()
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
    return household
