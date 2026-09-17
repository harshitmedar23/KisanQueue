from io import BytesIO

import qrcode
from flask import url_for
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def build_receipt(booking):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Procurement receipt #{booking.token_number}")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(60, 790, "Farmer Procurement Receipt")
    pdf.setFont("Helvetica", 11)
    lines = [
        f"Farmer: {booking.farmer.name}",
        f"Centre: {booking.centre.name}",
        f"Date: {booking.slot_config.date}  |  Slot: {booking.slot_config.time_slot}",
        f"Token: #{booking.token_number}",
        f"Crop: {booking.crop_type}",
        f"Quantity: {booking.quantity_kg:.1f} kg",
        f"Payment: Rs. {booking.payment_amount or 0:.2f} ({booking.payment_status})",
    ]
    y = 750
    for line in lines:
        pdf.drawString(60, y, line)
        y -= 24
    if booking.checkin_token:
        qr = qrcode.make(url_for("admin.check_in", token=booking.checkin_token, _external=True))
        qr_buffer = BytesIO()
        qr.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)
        from reportlab.lib.utils import ImageReader
        pdf.drawImage(ImageReader(qr_buffer), 60, y - 150, width=130, height=130)
        pdf.drawString(205, y - 70, "Scan at the centre for check-in")
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer
