from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from io import BytesIO
import qrcode


def generate_parking_token_pdf(ticket, checkout_url):
    # Generate QR for PDF
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

    # Token & Details
    p.setFont("Helvetica-Bold", 28)
    p.drawCentredString(width / 2, height - 500, f"TOKEN NO: {ticket.id}")

    y = height - 570
    p.setFont("Helvetica-Bold", 16)
    details = [
        ("Vehicle Number", ticket.vehicle_number),
        ("Phone Number", ticket.phone),
        ("Email", ticket.email or "N/A"),
        ("Vehicle Type", ticket.vehicle_type),
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
