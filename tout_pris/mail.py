import logging

import httpx
from brevo import Brevo
from brevo.transactional_emails import (
    SendTransacEmailRequestSender,
    SendTransacEmailRequestToItem,
)
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_TIMEOUT_SECONDS = 10


def send_email(
    to: str, subject: str, html_content: str | None = None, text_content: str | None = None
) -> None:
    if not settings.BREVO_API_KEY:
        logger.info("BREVO_API_KEY is not set, skipping email %r to %s", subject, to)
        return

    content = {}
    if html_content is not None:
        content["html_content"] = html_content
    if text_content is not None:
        content["text_content"] = text_content

    try:
        with httpx.Client(timeout=BREVO_TIMEOUT_SECONDS) as http_client:
            client = Brevo(api_key=settings.BREVO_API_KEY, httpx_client=http_client)
            client.transactional_emails.send_transac_email(
                sender=SendTransacEmailRequestSender(
                    email=settings.MAIL_FROM_EMAIL,
                    name=settings.MAIL_FROM_NAME,
                ),
                to=[SendTransacEmailRequestToItem(email=to)],
                subject=subject,
                **content,
            )
    except Exception:
        logger.exception("Failed to send email %r to %s", subject, to)


class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages) -> int:
        for message in email_messages:
            for recipient in message.to:
                send_email(
                    recipient,
                    message.subject,
                    html_content=html_alternative_of(message),
                    text_content=message.body,
                )
        return len(email_messages)


def html_alternative_of(message) -> str | None:
    for alternative in getattr(message, "alternatives", []):
        if alternative[1] == "text/html":
            return alternative[0]
    return None
