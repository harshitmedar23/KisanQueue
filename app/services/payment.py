"""Static UPI deep-link QR generation for manual payment confirmation."""
import base64
import io
from urllib.parse import urlencode

import qrcode


def upi_qr_data_uri(vpa, payee_name, amount, note, reference):
    query = urlencode({
        "pa": vpa,
        "pn": payee_name,
        "am": f"{float(amount):.2f}",
        "cu": "INR",
        "tn": note,
        "tr": reference,
    })
    image = qrcode.make(f"upi://pay?{query}")
    output = io.BytesIO()
    image.save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
