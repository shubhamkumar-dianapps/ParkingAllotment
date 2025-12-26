import logging
import base64

from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse
from django.core.mail import EmailMessage
from django.conf import settings

from .models import Slot, Ticket, Floor, ParkingConfig
from .forms import VehicleDetailsForm
from services.slot_allocator import SlotAllocator
from services.billing import BillingService
from services.pdf_generator import generate_parking_token_pdf
from services.qr_generator import generate_and_save_qr


logger = logging.getLogger(__name__)

# =============================================
# Home & Selection Views
# =============================================


def home(request):
    return render(request, "home.html")


def select_vehicle(request):
    """Display vehicle type selection."""
    vehicle_types = ParkingConfig.objects.values_list("vehicle_type", flat=True)
    if not vehicle_types:
        return _render_error_page(
            request,
            "Configuration Error",
            "No vehicle types are configured in the system.",
            suggestion="Please contact the administrator to set up vehicle types.",
            status=500,
        )
    return render(request, "vehicle_type.html")


# =============================================
# Slot Viewing
# =============================================


def view_slots(request, vehicle_type):
    """Display available slots for selected vehicle type and floor."""
    try:
        floor_no = int(request.GET.get("floor", 1))
    except (ValueError, TypeError):
        floor_no = 1

    floor = get_object_or_404(Floor, number=floor_no)
    config = get_object_or_404(ParkingConfig, vehicle_type=vehicle_type.upper())

    slots = (
        Slot.objects.select_related("floor")
        .filter(
            floor=floor,
            vehicle_type=vehicle_type.upper(),
            is_available=True,
        )
        .order_by("section", "slot_number")
    )

    floors = Floor.objects.order_by("number")

    context = {
        "slots": slots,
        "vehicle_type": vehicle_type.upper(),
        "floor": floor,
        "floors": floors,
        "base_price_for_type": config.base_price,
    }
    return render(request, "slots.html", context)


# =============================================
# Vehicle Booking & Token Generation
# =============================================


def vehicle_form(request, slot_id):
    """Handle vehicle details submission and generate token with QR & PDF."""
    slot = _validate_slot(request, slot_id)
    if isinstance(slot, HttpResponse):
        return slot

    if request.method == "POST":
        form = VehicleDetailsForm(request.POST)
        if form.is_valid():
            allocated_slot = SlotAllocator.allocate(
                vehicle_type=slot.vehicle_type,
                floor=slot.floor,
                section=slot.section,
            )
            if not allocated_slot:
                messages.error(
                    request, "Sorry, this slot was just taken by another customer."
                )
                return redirect("view_slots", vehicle_type=slot.vehicle_type)

            # Create ticket with email
            ticket = Ticket.objects.create(
                vehicle_number=form.cleaned_data["vehicle_number"].strip().upper(),
                phone=form.cleaned_data["phone"].strip(),
                email=form.cleaned_data["email"].strip().lower(),
                vehicle_type=slot.vehicle_type,
                slot=allocated_slot,
                initial_payment=form.cleaned_data["initial_payment"] or 0,
            )
            logger.info(f"Ticket {ticket.id} created for slot {allocated_slot}.")

            # Generate QR code and save to model
            checkout_url = request.build_absolute_uri(f"/qrcheckout/{ticket.id}")
            generate_and_save_qr(ticket, checkout_url)

            # Generate PDF with embedded QR
            pdf_buffer = generate_parking_token_pdf(ticket, checkout_url)

            # Send email with PDF attachment
            _send_token_email(request, ticket, pdf_buffer, ticket.email)

            # Auto-download via base64 data URL
            pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode("utf-8")
            pdf_data_url = f"data:application/pdf;base64,{pdf_base64}"

            return render(
                request,
                "token_success.html",
                {"ticket": ticket, "pdf_data_url": pdf_data_url},
            )
    else:
        form = VehicleDetailsForm()

    return render(request, "vehicle_form.html", {"slot": slot, "form": form})


# =============================================
# Checkout Views
# =============================================


def checkout(request):
    """Manual checkout via token entry."""
    if request.method == "POST":
        token_input = request.POST.get("token", "").strip()
        return _process_checkout(request, token_input, is_qr_scan=False)
    return render(request, "checkout.html")


def qr_checkout(request, token_id):
    """Auto checkout via QR scan."""
    return _process_checkout(request, str(token_id), is_qr_scan=True)


def _process_checkout(request, token_input, is_qr_scan=False):
    """Shared logic for both manual and QR checkout."""
    if not token_input:
        messages.error(request, "Please enter a token number.")
        return render(request, "checkout.html")

    try:
        token_id = int(token_input)
        # Use select_related to avoid a second query for the slot
        ticket = Ticket.objects.select_related("slot__floor").get(
            id=token_id, check_out__isnull=True
        )
    except (ValueError, Ticket.DoesNotExist):
        logger.warning(f"Invalid or used token entered: '{token_input}'")
        return _render_error_page(
            request,
            "Invalid Token",
            "The token was not found or has already been used.",
            suggestion="Please check your token number or contact support.",
        )

    # Perform checkout
    ticket.check_out = timezone.now()
    total, refund, due, hours = BillingService.calculate(ticket)
    ticket.final_amount = total
    ticket.save()

    if ticket.slot:
        ticket.slot.is_available = True
        ticket.slot.save()

    success_msg = "Checkout completed successfully!"
    if is_qr_scan:
        success_msg += " (via QR scan)"
    messages.success(request, success_msg)

    return render(
        request,
        "bill.html",
        {
            "ticket": ticket,
            "total": total,
            "refund": refund,
            "due": due,
            "hours": hours,
            "is_qr_scan": is_qr_scan,
        },
    )


# =============================================
# Token Success & PDF Download
# =============================================


def token_success(request, ticket_id):
    ticket = get_object_or_404(Ticket.objects.select_related("slot"), id=ticket_id)
    return render(request, "token_success.html", {"ticket": ticket})


def download_pdf(request, ticket_id):
    """Manual PDF download endpoint."""
    ticket = get_object_or_404(Ticket.objects.select_related("slot"), id=ticket_id)
    pdf_buffer = generate_parking_token_pdf(
        ticket, request.build_absolute_uri(f"/qrcheckout/{ticket.id}")
    )

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="EliteParking_Token_{ticket.id}.pdf"'
    )
    return response


# =============================================
# Helper Functions
# =============================================


def _render_error_page(request, title, message, suggestion=None, status=404):
    """Render a standard error page."""
    template = "500.html" if status == 500 else "not_found.html"
    context = {
        "error_title": title,
        "error_message": message,
        "suggestion": suggestion,
    }
    return render(request, template, context, status=status)


def _validate_slot(request, slot_id):
    """Validate slot existence and availability."""
    try:
        slot = Slot.objects.get(id=slot_id)
    except Slot.DoesNotExist:
        logger.warning(f"Attempted to access non-existent slot_id: {slot_id}")
        return _render_error_page(
            request,
            "Slot Not Found",
            "The selected slot no longer exists.",
        )

    if not slot.is_available:
        logger.warning(f"Attempted to book an unavailable slot: {slot} (ID: {slot_id})")
        return _render_error_page(
            request,
            "Slot Taken",
            f"Slot {slot.section}-{slot.slot_number} is no longer available.",
        )

    return slot


def _send_token_email(request, ticket, pdf_buffer, email):
    """Send token PDF via email, with error handling."""
    if not email:
        return

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
    except Exception as e:
        logger.error(
            f"Failed to send token email to {email} for ticket {ticket.id}: {e}",
            exc_info=True,
        )
        messages.warning(
            request, "Your token was created, but we failed to send the email."
        )


# =============================================
# Error Handlers
# =============================================


def custom_404(request, exception=None):
    return render(
        request,
        "not_found.html",
        {
            "error_title": "Page Not Found",
            "error_message": "The requested page does not exist.",
        },
        status=404,
    )


def custom_500(request):
    logger.error(
        f"500 Server Error: {request.path}",
        exc_info=True,
        extra={"status_code": 500, "request": request},
    )
    return render(
        request,
        "500.html",
        {
            "error_title": "Server Error",
            "error_message": "Something went wrong. Please try again later.",
        },
        status=500,
    )
