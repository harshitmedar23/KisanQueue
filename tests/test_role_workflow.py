from app import create_app
from app.models import Booking, Centre, User, Vehicle


def test_user_role_helpers_and_booking_approval_fields():
    app = create_app()
    with app.app_context():
        centre = Centre(name="Test Centre")
        user = User(name="Owner One", mobile_number="9876500001", role="mandi_owner", assigned_centre_id=1)
        assert user.is_mandi_owner() is True
        assert user.is_admin() is False
        assert hasattr(Booking, "approval_status") is True
        assert hasattr(Vehicle, "driver_status") is True
        assert centre.name == "Test Centre"
