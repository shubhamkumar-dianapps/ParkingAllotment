from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from .models import Slot, Ticket, Floor, ParkingConfig
from services.slot_allocator import SlotAllocator
from services.billing import BillingService
from django.contrib import messages
from django.http import HttpResponse
from reportlab.pdfgen import canvas
import qrcode
from io import BytesIO


def home(request):
    return render(request, "home.html")


def select_vehicle(request):
    return render(request, "vehicle_type.html")


def view_slots(request, vehicle_type):
    floor_no = int(request.GET.get("floor", 1))
    floor = get_object_or_404(Floor, number=floor_no)

    slots = Slot.objects.filter(
        floor=floor, vehicle_type=vehicle_type, is_available=True
    ).order_by("section", "slot_number")

    floors = Floor.objects.order_by("number")

    # Get base price from config for this vehicle type
    config = get_object_or_404(ParkingConfig, vehicle_type=vehicle_type.upper())
    base_price_for_type = config.base_price

    return render(
        request,
        "slots.html",
        {
            "slots": slots,
            "vehicle_type": vehicle_type.upper(),
            "floor": floor,
            "floors": floors,
            "base_price_for_type": base_price_for_type,  # Pass to template
        },
    )


# def vehicle_form(request, slot_id):
#     # Fetch the slot (ensure it's available)
#     try:
#         slot = Slot.objects.get(id=slot_id, is_available=True)
#     except Slot.DoesNotExist:
#         return render(request, "not_found.html")

#     if request.method == "POST":
#         vehicle_number = request.POST["vehicle_number"].strip().upper()
#         phone = request.POST["phone"].strip()
#         initial_payment = int(request.POST.get("initial_payment", 0) or 0)

#         # Critical: Re-allocate with locking to prevent race condition
#         allocated_slot = SlotAllocator.allocate(
#             vehicle_type=slot.vehicle_type, floor=slot.floor, section=slot.section
#         )

#         if not allocated_slot:
#             messages.error(
#                 request, "Sorry, this slot was just taken by another customer."
#             )
#             return redirect("view_slots", vehicle_type=slot.vehicle_type)

#         # Create ticket
#         ticket = Ticket.objects.create(
#             vehicle_number=vehicle_number,
#             phone=phone,
#             vehicle_type=slot.vehicle_type,
#             slot=allocated_slot,
#             initial_payment=initial_payment,
#         )

#         # Success: Show dedicated token page
#         return redirect("token_success", ticket_id=ticket.id)

#     # GET request: Show form
#     return render(request, "vehicle_form.html", {"slot": slot})


def vehicle_form(request, slot_id):
    slot = get_object_or_404(Slot, id=slot_id, is_available=True)

    if request.method == "POST":
        vehicle_number = request.POST["vehicle_number"]
        phone = request.POST["phone"]
        initial_payment = int(request.POST.get("initial_payment", 0))

        slot = SlotAllocator.allocate(slot.vehicle_type, slot.floor, slot.section)
        if not slot:
            return render(request, "slots.html", {"error": "Slot taken"})

        ticket = Ticket.objects.create(
            vehicle_number=vehicle_number,
            phone=phone,
            vehicle_type=slot.vehicle_type,
            slot=slot,
            initial_payment=initial_payment,
        )

        # Generate QR Code (links to bill page)
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr_url = request.build_absolute_uri(f"/checkout/?token={ticket.id}")
        qr.add_data(qr_url)
        qr.make(fit=True)
        img = qr.make_image(fill="black", back_color="white")
        qr_buffer = BytesIO()
        img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)
        ticket.qr_code.save(
            f"qr_{ticket.id}.png", qr_buffer
        )  # Save to model if you add ImageField, or pass to template

        # Generate PDF for auto-download
        pdf_buffer = BytesIO()
        pdf = canvas.Canvas(pdf_buffer)
        pdf.drawString(100, 800, "Elite Parking Token")
        pdf.drawString(100, 780, f"Token ID: {ticket.id}")
        pdf.drawString(100, 760, f"Vehicle Number: {ticket.vehicle_number}")
        pdf.drawString(100, 740, f"Check-in Time: {ticket.check_in}")
        pdf.drawString(100, 720, f"Initial Payment: ₹{ticket.initial_payment}")
        pdf.save()
        pdf_buffer.seek(0)

        # Auto-download PDF response
        response = HttpResponse(pdf_buffer, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="token_{ticket.id}.pdf"'
        )
        return response  # This triggers auto-download, then user can go to home

    return render(request, "vehicle_form.html", {"slot": slot})


# def checkout(request):
#     if request.method == "POST":
#         token = request.POST["token"]
#         ticket = get_object_or_404(Ticket, id=token, check_out__isnull=True)

#         ticket.check_out = timezone.now()
#         total, refund, due, hours = BillingService.calculate(ticket)
#         ticket.final_amount = total
#         ticket.save()

#         ticket.slot.is_available = True
#         ticket.slot.save()

#         return render(
#             request,
#             "bill.html",
#             {
#                 "ticket": ticket,
#                 "total": total,
#                 "refund": refund,
#                 "due": due,
#                 "hours": hours,
#             },
#         )

#     return render(request, "checkout.html")


def checkout(request):
    if request.method == "POST":
        token_input = request.POST.get("token", "").strip()

        # Validate input
        if not token_input:
            messages.error(request, "Please enter a token number.")
            return render(request, "checkout.html")

        try:
            token_id = int(token_input)
        except ValueError:
            messages.error(request, "Invalid token format. Please enter a number.")
            return render(request, "checkout.html")

        try:
            # Try to get active ticket (not checked out yet)
            ticket = Ticket.objects.get(id=token_id, check_out__isnull=True)
        except Ticket.DoesNotExist:
            # This covers both: invalid token OR already checked out
            return render(
                request,
                "not_found.html",
                {
                    "error_title": "Token Not Found or Already Used",
                    "error_message": "The token you entered is either invalid or has already been checked out.",
                    "suggestion": "Please check your token number or contact support.",
                },
            )

        # Proceed with checkout
        ticket.check_out = timezone.now()
        total, refund, due, hours = BillingService.calculate(ticket)
        ticket.final_amount = total
        ticket.save()

        # Free the slot
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

    # GET request - show form
    return render(request, "checkout.html")


def token_success(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    return render(request, "token_success.html", {"ticket": ticket})


def download_pdf(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)

    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 800, "Elite Parking Token")
    p.drawString(100, 780, f"Token ID: {ticket.id}")
    p.drawString(100, 760, f"Vehicle Number: {ticket.vehicle_number}")
    p.drawString(100, 740, f"Check-in Time: {ticket.check_in}")
    p.drawString(100, 720, f"Initial Payment: ₹{ticket.initial_payment}")
    p.save()
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="token_{ticket.id}.pdf"'
    return response
