import re


_FAKE_MOBILE_NUMBERS = {
    "0123456789",
    "1234567890",
    "9876543210",
    "0987654321",
}


def is_valid_mobile_number(value):
    """Validate an Indian mobile number before any OTP is created."""
    if not value or not re.fullmatch(r"[6-9]\d{9}", value):
        return False
    if value in _FAKE_MOBILE_NUMBERS or len(set(value)) == 1:
        return False
    if value == value[:1] * 10:
        return False
    return True
