import logging

from brevo import Brevo
from brevo.core.api_error import ApiError
from brevo.transactional_emails import (
    SendTransacEmailRequestSender,
    SendTransacEmailRequestToItem,
)

from app.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html_content: str) -> None:
    if not settings.brevo_api_key:
        logger.info("BREVO_API_KEY is not set, skipping email %r to %s", subject, to)
        return

    client = Brevo(api_key=settings.brevo_api_key)
    try:
        client.transactional_emails.send_transac_email(
            sender=SendTransacEmailRequestSender(
                email=settings.mail_from_email,
                name=settings.mail_from_name,
            ),
            to=[SendTransacEmailRequestToItem(email=to)],
            subject=subject,
            html_content=html_content,
        )
    except ApiError:
        logger.exception("Brevo rejected email %r to %s", subject, to)
