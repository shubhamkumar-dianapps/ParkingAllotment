from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from io import BytesIO
import qrcode
import base64  # <-- Critical import for base64 encoding
from .models import Slot, Ticket, Floor, ParkingConfig
from services.slot_allocator import SlotAllocator
from services.billing import BillingService
from django.core.mail import EmailMessage
from django.conf import settings
from .models import Slot, Ticket, Floor, ParkingConfig
from services.slot_allocator import SlotAllocator
from services.billing import BillingService


# =============================================
# Home & Selection Views
# =============================================


def home(request):
    return render(request, "home.html")


def select_vehicle(request):
    """Display vehicle type selection."""
    vehicle_types = ParkingConfig.objects.values_list("vehicle_type", flat=True)
    if not vehicle_types:
        return render(
            request,
            "500.html",
            {
                "error_title": "Configuration Error",
                "error_message": "No vehicle types configured.",
                "suggestion": "Contact administrator.",
            },
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

    slots = Slot.objects.filter(
        floor=floor,
        vehicle_type=vehicle_type.upper(),
        is_available=True,
    ).order_by("section", "slot_number")

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
        form_data = _extract_form_data(request)

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
            vehicle_number=form_data["vehicle_number"],
            phone=form_data["phone"],
            email=form_data["email"],
            vehicle_type=slot.vehicle_type,
            slot=allocated_slot,
            initial_payment=form_data["initial_payment"],
        )

        # Generate QR code
        checkout_url = request.build_absolute_uri(f"/qrcheckout/{ticket.id}")
        _generate_and_save_qr(ticket, checkout_url)

        # Generate PDF with embedded QR
        pdf_buffer = _generate_parking_token_pdf(ticket, checkout_url)

        # Send email with PDF attachment
        _send_token_email(request, ticket, pdf_buffer, form_data["email"])

        # Auto-download via base64
        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode("utf-8")
        pdf_data_url = f"data:application/pdf;base64,{pdf_base64}"

        return render(
            request,
            "token_success.html",
            {"ticket": ticket, "pdf_data_url": pdf_data_url},
        )

    return render(request, "vehicle_form.html", {"slot": slot})


# =============================================
# Checkout Views
# =============================================


def checkout(request):
    """Manual checkout via token entry."""
    if request.method == "POST":
        token_input = request.POST.get("token", "").strip()
        return _process_checkout(request, token_input, auto=False)
    return render(request, "checkout.html")


def auto_checkout(request, token_id):
    """Auto checkout via QR scan."""
    return _process_checkout(request, str(token_id), auto=True)


def _process_checkout(request, token_input, auto=False):
    """Shared logic for both manual and QR checkout."""
    if not token_input:
        messages.error(request, "Please enter a token number.")
        return render(request, "checkout.html")

    try:
        token_id = int(token_input)
        ticket = Ticket.objects.get(id=token_id, check_out__isnull=True)
    except (ValueError, Ticket.DoesNotExist):
        return render(
            request,
            "not_found.html",
            {
                "error_title": "Invalid Token",
                "error_message": "Token not found or already used.",
                "suggestion": "Please check your token number or contact support.",
            },
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
    if auto:
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
            "auto": auto,
        },
    )


# =============================================
# Token Success & PDF Download
# =============================================


def token_success(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    return render(request, "token_success.html", {"ticket": ticket})


def download_pdf(request, ticket_id):
    """Manual PDF download endpoint."""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    pdf_buffer = _generate_parking_token_pdf(
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


def _validate_slot(request, slot_id):
    """Validate slot existence and availability."""
    try:
        slot = Slot.objects.get(id=slot_id)
    except Slot.DoesNotExist:
        return render(
            request,
            "not_found.html",
            {
                "error_title": "Slot Not Found",
                "error_message": "Selected slot no longer exists.",
            },
        )

    if not slot.is_available:
        return render(
            request,
            "not_found.html",
            {
                "error_title": "Slot Taken",
                "error_message": f"Slot {slot.section}-{slot.slot_number} is no longer available.",
            },
        )

    return slot


def _extract_form_data(request):
    """Extract and clean form data."""
    return {
        "vehicle_number": request.POST["vehicle_number"].strip().upper(),
        "phone": request.POST["phone"].strip(),
        "email": request.POST["email"].strip().lower(),
        "initial_payment": int(request.POST.get("initial_payment", 0) or 0),
    }


def _generate_and_save_qr(ticket, url):
    """Generate QR code and save to ticket.qr_code."""
    qr = qrcode.QRCode(version=1, box_size=15, border=6)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    ticket.qr_code.save(f"qr_token_{ticket.id}.png", buffer)


def _generate_parking_token_pdf(ticket, checkout_url):
    """Generate professional PDF token with embedded QR."""
    # Generate fresh QR for PDF
    qr = qrcode.QRCode(version=1, box_size=15, border=6)
    qr.add_data(checkout_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # Create PDF
    pdf_buffer = BytesIO()
    p = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4

    # Header
    p.setFont("Helvetica-Bold", 32)
    p.drawCentredString(width / 2, height - 80, "ELITE PARKING")
    p.setFont("Helvetica", 18)
    p.drawCentredString(width / 2, height - 120, "Official Parking Token")

    # QR Code
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, height - 180, "Scan for Instant Checkout")
    qr_reader = ImageReader(qr_buffer)
    p.drawImage(
        qr_reader,
        width / 2 - 130,
        height - 460,
        width=260,
        height=260,
        preserveAspectRatio=True,
    )

    # Token Number
    p.setFont("Helvetica-Bold", 28)
    p.drawCentredString(width / 2, height - 500, f"TOKEN NO: {ticket.id}")

    # Details
    y = height - 570
    p.setFont("Helvetica-Bold", 16)
    details = [
        ("Vehicle Number", ticket.vehicle_number),
        ("Phone Number", ticket.phone),
        ("Email", ticket.email or "N/A"),
        ("Vehicle Type", "4 Wheeler" if ticket.vehicle_type == "CAR" else "2 Wheeler"),
        ("Parking Slot", str(ticket.slot)),
        ("Check-in Time", ticket.check_in.strftime("%d %B %Y, %I:%M %p")),
        ("Initial Payment", f"₹{ticket.initial_payment}"),
    ]
    for label, value in details:
        p.drawString(100, y, f"{label}:")
        p.setFont("Helvetica", 16)
        p.drawString(300, y, value)
        p.setFont("Helvetica-Bold", 16)
        y -= 40

    # Footer
    p.setFont("Helvetica-Oblique", 12)
    p.drawCentredString(width / 2, 80, "Thank you for choosing Elite Parking")

    p.showPage()
    p.save()
    pdf_buffer.seek(0)
    return pdf_buffer


def _send_token_email(request, ticket, pdf_buffer, email):
    """Send token PDF via email."""
    checkout_url = request.build_absolute_uri(
        f"/qrcheckout/{ticket.id}"
    )  # Now request is available

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

    msg = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [email])
    msg.attach(
        f"EliteParking_Token_{ticket.id}.pdf", pdf_buffer.getvalue(), "application/pdf"
    )
    msg.send()


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
    return render(
        request,
        "500.html",
        {
            "error_title": "Server Error",
            "error_message": "Something went wrong. Please try again later.",
        },
        status=500,
    )
