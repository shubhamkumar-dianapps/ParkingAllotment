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


def home(request):
    return render(request, "home.html")


def select_vehicle(request):
    try:
        vehicle_types = ParkingConfig.objects.values_list("vehicle_type", flat=True)
    except ParkingConfig.DoesNotExist:
        render(
            request,
            "500.html",
            {
                "error_title": "Configuration Error",
                "error_message": "No vehicle types are configured for parking.",
                "suggestion": "Please contact the administrator.",
            },
        )
    return render(request, "vehicle_type.html")


def view_slots(request, vehicle_type):
    try:
        floor_no = int(request.GET.get("floor", 1))
    except ValueError:
        floor_no = 1
    try:
        floor = get_object_or_404(Floor, number=floor_no)
    except Floor.DoesNotExist:
        floor = Floor.objects.first()

    slots = Slot.objects.filter(
        floor=floor, vehicle_type=vehicle_type, is_available=True
    ).order_by("section", "slot_number")

    floors = Floor.objects.order_by("number")

    config = ParkingConfig.objects.get(vehicle_type=vehicle_type.upper())
    base_price_for_type = config.base_price

    return render(
        request,
        "slots.html",
        {
            "slots": slots,
            "vehicle_type": vehicle_type.upper(),
            "floor": floor,
            "floors": floors,
            "base_price_for_type": base_price_for_type,
        },
    )


def vehicle_form(request, slot_id):
    try:
        slot = Slot.objects.get(id=slot_id)
    except Slot.DoesNotExist:
        return render(
            request,
            "not_found.html",
            {
                "error_title": "Slot Not Found",
                "error_message": "The parking slot you selected no longer exists.",
                "suggestion": "Please go back and select another available slot.",
            },
        )

    if not slot.is_available:
        return render(
            request,
            "not_found.html",
            {
                "error_title": "Slot Already Booked",
                "error_message": f"Sorry, Slot {slot.section}-{slot.slot_number} on Floor {slot.floor.number} has just been taken by another customer.",
                "suggestion": "Please go back and select another available slot.",
            },
        )

    if request.method == "POST":
        vehicle_number = request.POST["vehicle_number"].strip().upper()
        phone = request.POST["phone"].strip()
        initial_payment = int(request.POST.get("initial_payment", 0) or 0)

        allocated_slot = SlotAllocator.allocate(
            vehicle_type=slot.vehicle_type, floor=slot.floor, section=slot.section
        )
        if not allocated_slot:
            messages.error(
                request, "Sorry, this slot was just taken by another customer."
            )
            return redirect("view_slots", vehicle_type=slot.vehicle_type)

        ticket = Ticket.objects.create(
            vehicle_number=vehicle_number,
            phone=phone,
            vehicle_type=slot.vehicle_type,
            slot=allocated_slot,
            initial_payment=initial_payment,
        )

        # Generate and save QR Code
        checkout_url = request.build_absolute_uri(f"/qrcheckout/{ticket.id}")
        qr = qrcode.QRCode(version=1, box_size=15, border=6)  # Larger for clarity
        qr.add_data(checkout_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")

        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)
        ticket.qr_code.save(f"qr_token_{ticket.id}.png", qr_buffer)
        ticket.save()

        # Generate PDF with embedded QR
        pdf_buffer = BytesIO()
        p = canvas.Canvas(pdf_buffer, pagesize=A4)
        width, height = A4

        p.setFont("Helvetica-Bold", 28)
        p.drawCentredString(width / 2, height - 100, "Elite Parking Token")

        p.setFont("Helvetica", 18)
        p.drawCentredString(width / 2, height - 150, f"Token No: {ticket.id}")
        p.drawCentredString(
            width / 2, height - 190, f"Vehicle: {ticket.vehicle_number}"
        )
        p.drawCentredString(width / 2, height - 230, f"Phone: {ticket.phone}")
        p.drawCentredString(width / 2, height - 270, f"Slot: {ticket.slot}")
        p.drawCentredString(
            width / 2,
            height - 310,
            f"Check-in: {ticket.check_in.strftime('%d %b %Y, %I:%M %p')}",
        )

        # Embed QR Code
        qr_reader = ImageReader(BytesIO(qr_buffer.getvalue()))
        p.drawImage(
            qr_reader,
            width / 2 - 120,
            height - 580,
            width=240,
            height=240,
            preserveAspectRatio=True,
        )
        p.drawCentredString(width / 2, height - 620, "Scan QR for Quick Checkout")

        p.showPage()
        p.save()
        pdf_buffer.seek(0)

        # Convert to base64 for auto-download
        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode("utf-8")
        pdf_data_url = f"data:application/pdf;base64,{pdf_base64}"

        # Redirect to token success with PDF data
        return render(
            request,
            "token_success.html",
            {"ticket": ticket, "pdf_data_url": pdf_data_url},
        )

    return render(request, "vehicle_form.html", {"slot": slot})


def checkout(request):
    if request.method == "POST":
        token_input = request.POST.get("token", "").strip()

        if not token_input:
            messages.error(request, "Please enter a token number.")
            return render(request, "checkout.html")

        try:
            token_id = int(token_input)
        except ValueError:
            messages.error(request, "Invalid token format. Please enter a number.")
            return render(request, "checkout.html")

        try:
            ticket = Ticket.objects.get(id=token_id, check_out__isnull=True)
        except Ticket.DoesNotExist:
            return render(
                request,
                "not_found.html",
                {
                    "error_title": "Token Not Found or Already Used",
                    "error_message": "The token you entered is either invalid or has already been checked out.",
                    "suggestion": "Please check your token number or contact support.",
                },
            )

        # Checkout process
        ticket.check_out = timezone.now()
        total, refund, due, hours = BillingService.calculate(ticket)
        ticket.final_amount = total
        ticket.save()

        if ticket.slot:
            ticket.slot.is_available = True
            ticket.slot.save()

        messages.success(request, "Checkout completed successfully!")

        return render(
            request,
            "bill.html",
            {
                "ticket": ticket,
                "total": total,
                "refund": refund,
                "due": due,
                "hours": hours,
            },
        )

    return render(request, "checkout.html")


def token_success(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    return render(request, "token_success.html", {"ticket": ticket})


def download_pdf(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 28)
    p.drawCentredString(width / 2, height - 100, "Elite Parking Token")

    p.setFont("Helvetica", 18)
    p.drawCentredString(width / 2, height - 150, f"Token No: {ticket.id}")
    p.drawCentredString(width / 2, height - 190, f"Vehicle: {ticket.vehicle_number}")
    p.drawCentredString(width / 2, height - 230, f"Phone: {ticket.phone}")
    p.drawCentredString(width / 2, height - 270, f"Slot: {ticket.slot}")
    p.drawCentredString(
        width / 2,
        height - 310,
        f"Check-in: {ticket.check_in.strftime('%d %b %Y, %I:%M %p')}",
    )

    p.setFont("Helvetica", 14)
    p.drawCentredString(
        width / 2, height - 360, "Thank you for choosing Elite Parking!"
    )

    p.showPage()
    p.save()
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="EliteParking_Token_{ticket.id}.pdf"'
    )
    return response


def auto_checkout(request, token_id):
    ticket = get_object_or_404(Ticket, id=token_id)

    # If already checked out, just show bill
    if ticket.check_out is not None:
        total, refund, due, hours = BillingService.calculate(ticket)
        return render(
            request,
            "bill.html",
            {
                "ticket": ticket,
                "total": total,
                "refund": refund,
                "due": due,
                "hours": hours,
                "auto": True,  # Optional: to show "Scanned QR" message
            },
        )

    # Auto checkout
    ticket.check_out = timezone.now()
    total, refund, due, hours = BillingService.calculate(ticket)
    ticket.final_amount = total
    ticket.save()

    if ticket.slot:
        ticket.slot.is_available = True
        ticket.slot.save()

    messages.success(request, "Checkout completed via QR scan!")

    return render(
        request,
        "bill.html",
        {
            "ticket": ticket,
            "total": total,
            "refund": refund,
            "due": due,
            "hours": hours,
            "auto": True,
        },
    )


def custom_404(request, exception=None):
    return render(
        request,
        "not_found.html",
        {
            "error_title": "Page Not Found",
            "error_message": "The page you requested does not exist.",
            "suggestion": "Please check the URL or go back to the home page.",
        },
        status=404,
    )


def custom_500(request):
    return render(
        request,
        "500.html",
        {
            "error_title": "Server Error",
            "error_message": "Something went wrong on our side. We're looking into it.",
            "suggestion": "Try again later or contact support if the problem persists.",
        },
        status=500,
    )
