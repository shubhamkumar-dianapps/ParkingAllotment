import logging
from django.core.mail import EmailMessage
from django.conf import settings

logger = logging.getLogger(__name__)


class MessagingService:
    @staticmethod
    def send_token_email(request, ticket, pdf_buffer, email):
        """Send token PDF via email, with error handling."""
        if not email:
            return False

        checkout_url = request.build_absolute_uri(f"/qrcheckout/{ticket.id}")

        subject = f"Elite Parking Token - {ticket.id}"
        body = f"""
        Dear Customer,

        Thank you for choosing Elite Parking!

        Your parking token is attached.

        Token No: {ticket.id}
        Vehicle: {ticket.vehicle_number}
        Slot: {ticket.slot}
        Check-in: {ticket.check_in.strftime('%d %b %Y, %I:%M %p')}

        Scan the QR code in the PDF or use this direct link for instant checkout:
        {checkout_url}

        Best regards,
        Elite Parking Team
        """

        try:
            msg = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [email])
            msg.attach(
                f"EliteParking_Token_{ticket.id}.pdf",
                pdf_buffer.getvalue(),
                "application/pdf",
            )
            msg.send()
            return True
        except Exception as e:
            logger.error(
                f"Failed to send token email to {email} for ticket {ticket.id}: {e}",
                exc_info=True,
            )
            return False
