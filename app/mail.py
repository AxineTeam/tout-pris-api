import logging

import httpx
from brevo import Brevo
from brevo.transactional_emails import (
    SendTransacEmailRequestSender,
    SendTransacEmailRequestToItem,
)

from app.config import settings

logger = logging.getLogger(__name__)

BREVO_TIMEOUT_SECONDS = 10


def send_email(to: str, subject: str, html_content: str) -> None:
    if not settings.brevo_api_key:
        logger.info("BREVO_API_KEY is not set, skipping email %r to %s", subject, to)
        return

    try:
        with httpx.Client(timeout=BREVO_TIMEOUT_SECONDS) as http_client:
            client = Brevo(api_key=settings.brevo_api_key, httpx_client=http_client)
            client.transactional_emails.send_transac_email(
                sender=SendTransacEmailRequestSender(
                    email=settings.mail_from_email,
                    name=settings.mail_from_name,
                ),
                to=[SendTransacEmailRequestToItem(email=to)],
                subject=subject,
                html_content=html_content,
            )
    except Exception:
        logger.exception("Failed to send email %r to %s", subject, to)
