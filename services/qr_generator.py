import qrcode
from io import BytesIO


def generate_and_save_qr(ticket, url):
    qr = qrcode.QRCode(version=1, box_size=15, border=6)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    ticket.qr_code.save(f"qr_token_{ticket.id}.png", buffer)
