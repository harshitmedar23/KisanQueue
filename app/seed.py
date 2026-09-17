from datetime import date, timedelta

from app.extensions import db
from app.models import User, Centre, SlotConfig, MandiPrice, Vehicle
from sqlalchemy import inspect


def seed_data():
    """Populate realistic Karnataka centre data and booking slots idempotently."""
    if User.query.filter_by(role="admin").first() is None:
        admin = User(
            name="Centre Administrator",
            mobile_number="9642993490",
            email="admin@example.com",
            role="admin",
        )
        db.session.add(admin)

    centre_profiles = [
        ("Yeshwanthpur APMC Procurement Centre", "Tumkur Road, Bengaluru", 13.0280, 77.5400),
        ("Ramanagara Silk City Mandi", "Bengaluru-Mysuru Highway, Ramanagara", 12.7218, 77.2815),
        ("Tumakuru APMC Grain Centre", "B.H. Road, Tumakuru", 13.3392, 77.1010),
        ("Mysuru Bandipalya Mandi", "Bandipalya, Mysuru", 12.2730, 76.6390),
        ("Mandya Sugarcane Procurement Centre", "M.C. Road, Mandya", 12.5218, 76.8951),
        ("Kolar APMC Produce Centre", "A.P.M.C. Yard, Kolar", 13.1367, 78.1290),
        ("Chikkaballapur APMC Mandi", "M.G. Road, Chikkaballapur", 13.4355, 77.7315),
        ("Hassan Agricultural Market", "B.M. Road, Hassan", 13.0068, 76.1004),
        ("Chikkamagaluru APMC Procurement Centre", "Kadur Road, Chikkamagaluru", 13.3161, 75.7756),
        ("Shivamogga APMC Centre", "Savalanga Road, Shivamogga", 13.9299, 75.5681),
        ("Davanagere Grain Mandi", "P.B. Road, Davanagere", 14.4644, 75.9218),
        ("Hubballi APMC Procurement Centre", "Gokul Road, Hubballi", 15.3647, 75.1240),
        ("Belagavi Agricultural Market", "Kakati Road, Belagavi", 15.8497, 74.4977),
        ("Vijayapura APMC Mandi", "Solapur Road, Vijayapura", 16.8302, 75.7100),
        ("Raichur APMC Grain Centre", "Station Road, Raichur", 16.2120, 77.3439),
        ("Kalaburagi Agricultural Market", "Sedam Road, Kalaburagi", 17.3297, 76.8343),
    ]

    existing_centres = Centre.query.order_by(Centre.id.asc()).all()
    centres_to_seed = []
    for index, (name, location, latitude, longitude) in enumerate(centre_profiles):
        if index < len(existing_centres):
            centre = existing_centres[index]
            # Keep foreign keys and existing bookings intact while replacing demo labels.
            centre.name = name
            centre.location = location
            centre.latitude = latitude
            centre.longitude = longitude
        else:
            centre = Centre(name=name, location=location, latitude=latitude, longitude=longitude)
            db.session.add(centre)
            db.session.flush()
        centres_to_seed.append(centre)

    db.session.commit()
    if inspect(db.engine).has_table("vehicles") and Vehicle.query.count() == 0:
        db.session.add_all([
            Vehicle(type="tata_ace", driver_name="Ravi Kumar", driver_phone="9876543210", capacity_kg=800),
            Vehicle(type="tractor", driver_name="Suresh Gowda", driver_phone="9876543211", capacity_kg=2500),
            Vehicle(type="truck", driver_name="Manjunath H", driver_phone="9876543212", capacity_kg=8000),
        ])
        db.session.commit()

    today = date.today()
    time_slots = ["08:00 - 10:00", "10:00 - 12:00", "13:00 - 15:00", "15:00 - 17:00"]
    for centre in centres_to_seed:
        for day_offset in range(7):
            d = today + timedelta(days=day_offset)
            for time_slot in time_slots:
                existing_slot = SlotConfig.query.filter_by(
                    centre_id=centre.id, date=d, time_slot=time_slot
                ).first()
                if not existing_slot:
                    db.session.add(SlotConfig(
                        centre_id=centre.id, date=d, time_slot=time_slot, capacity=25
                    ))
    db.session.commit()
    default_prices = [
        ("Wheat", 2275, 2350),
        ("Rice (Paddy)", 2300, 2420),
        ("Maize", 2225, 2180),
        ("Soybean", 4892, 5050),
        ("Cotton", 7121, 7350),
        ("Sugarcane", 340, 365),
        ("Other", 0, 0),
    ]
    existing_crops = {price.crop_type for price in MandiPrice.query.all()}
    missing_prices = [
        MandiPrice(crop_type=crop, market_name="Local Mandi", msp_per_quintal=msp,
                   market_price_per_quintal=market_price)
        for crop, msp, market_price in default_prices
        if crop not in existing_crops and market_price > 0
    ]
    if missing_prices:
        db.session.add_all(missing_prices)
        db.session.commit()
