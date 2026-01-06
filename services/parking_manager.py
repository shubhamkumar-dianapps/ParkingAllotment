import logging
import base64
from django.db import transaction
from django.utils import timezone
from parking.models import Ticket
from services.slot_allocator import SlotAllocator
from services.qr_generator import generate_and_save_qr
from services.pdf_generator import generate_parking_token_pdf
from services.billing import BillingService
from services.messaging import MessagingService

logger = logging.getLogger(__name__)


class ParkingManager:
    @staticmethod
    def book_vehicle(request, slot_id, form_data):
        """
        Orchestrates the vehicle booking process:
        1. Allocates slot
        2. Creates ticket
        3. Generates QR
        4. Generates PDF
        5. Sends Email
        Returns: meta dict with ticket and pdf_data_url, or None if allocation fails
        """
        allocated_slot = SlotAllocator.allocate(slot_id=slot_id)
        if not allocated_slot:
            return None

        # Create ticket
        ticket = form_data.save(commit=False)
        ticket.slot = allocated_slot
        ticket.vehicle_type = allocated_slot.vehicle_type
        ticket.save()
        logger.info(f"Ticket {ticket.id} created for slot {allocated_slot}.")

        # Generate QR code
        checkout_url = request.build_absolute_uri(f"/qrcheckout/{ticket.id}")
        generate_and_save_qr(ticket, checkout_url)

        # Generate PDF
        pdf_buffer = generate_parking_token_pdf(ticket, checkout_url)

        # Send Email
        email_sent = MessagingService.send_token_email(
            request, ticket, pdf_buffer, ticket.email
        )

        # Prepare PDF for display
        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode("utf-8")
        pdf_data_url = f"data:application/pdf;base64,{pdf_base64}"

        return {
            "ticket": ticket,
            "pdf_data_url": pdf_data_url,
            "email_sent": email_sent,
        }

    @staticmethod
    def process_checkout(token_id):
        """
        Orchestrates the checkout process:
        1. Validates token
        2. Calculates bill
        3. Updates ticket and slot
        Returns: success (bool), data (dict or error message)
        """
        try:
            ticket = Ticket.objects.select_related("slot__floor").get(
                id=token_id, check_out__isnull=True
            )
        except Ticket.DoesNotExist:
            return False, "The token was not found or has already been used."

        # Perform checkout calculations
        ticket.check_out = timezone.now()
        total, refund, due, hours = BillingService.calculate(ticket)
        ticket.final_amount = total
        ticket.save()

        # Release slot
        if ticket.slot:
            ticket.slot.is_available = True
            ticket.slot.save()
            logger.info(
                f"Slot Freed: Slot ID {ticket.slot.id} released by Ticket #{ticket.id}."
            )

        return True, {
            "ticket": ticket,
            "total": total,
            "refund": refund,
            "due": due,
            "hours": hours,
        }
