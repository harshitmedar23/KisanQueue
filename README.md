# Farmer Procurement System

A Flask application for farmer slot booking, mandi prices, live procurement queues, staff operations, payments, QR check-in, notifications, and multilingual farmer access.

## 1. What The Project Does

### Farmer workflow

1. Register with a valid 10-digit Indian mobile number.
2. Receive an OTP and verify the account.
3. View mandi prices, MSP comparison, price movement, and centre locations.
4. Select a crop, quantity, procurement centre, date, and time slot.
5. Receive a token number and follow the live queue.
6. Get queue, payment, and booking notifications.
7. Download a PDF receipt containing a QR check-in token.
8. View procurement history and switch the interface between English, Hindi, and Kannada.

### Staff/admin workflow

1. Login with an admin/staff mobile number using OTP.
2. Open the queue dashboard for a centre and date.
3. Serve the next token, mark no-shows, and record payments.
4. Check in farmers using the QR token from their receipt.
5. Manage slot capacity and time windows.
6. Publish mandi/MSP price updates.
7. View analytics and centre throughput.
8. Create additional staff accounts from **Staff**.
9. Review the audit log of staff actions.

Public registration can create farmer accounts only. New admin accounts must be created by an existing admin.

## 2. Technology

- Python 3.11+ recommended
- Flask 3
- Flask-SQLAlchemy and Flask-Migrate
- MySQL 8+ with PyMySQL
- Flask-SocketIO for live queue updates
- Bootstrap 5, custom CSS, Chart.js, Leaflet
- ReportLab and qrcode for PDF receipts and QR check-in
- Flask-Limiter for OTP/login rate limiting

## 3. Requirements For Teammates

Install Python, MySQL Server, optionally MySQL Workbench, and Git.

## 4. First-Time Setup On Windows

Open PowerShell in the project folder:

```powershell
cd "farmer_procurement_app - Copy"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 5. Create The MySQL Database

### MySQL Workbench

1. Open MySQL Workbench and connect to the local MySQL server.
2. Open `schema.sql`.
3. Execute the complete file.
4. Refresh Schemas and confirm `farmer_procurement_prod` exists.

### MySQL command line

```powershell
mysql -u root -p -h 127.0.0.1 < schema.sql
```

The schema creates:

```text
users, otps, centres, slot_configs, bookings,
notifications, push_subscriptions, mandi_prices, audit_logs
```

Do not manually insert centre rows. When the app starts, `app/seed.py` adds initial data idempotently:

- 1 admin account
- 15 Karnataka procurement centres
- 7 days of slots per centre
- 4 slots per day
- Capacity of 25 per slot
- Default wheat, paddy, and maize mandi prices

## 6. Configure `.env`

Set the teammate's local MySQL password:

```env
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@127.0.0.1:3306/farmer_procurement_prod
OTP_DEMO_MODE=True
TELEGRAM_ENABLED=False
UPI_VPA=yourname@okaxis
UPI_PAYEE_NAME=Your Centre Name
```

`UPI_VPA` is the payment UPI ID encoded into the QR shown on the farmer's
**Track Progress** page. Replace the example with the bank UPI ID that should
receive payments.

Every teammate should use their own `.env`. Never share `.env` in Git, chat, screenshots, or a ZIP file. `.env.example` contains placeholders only.

## 7. Start The Application

```powershell
cd "farmer_procurement_app - Copy"
.\.venv\Scripts\Activate.ps1
py run.py
```

Open `http://127.0.0.1:5000`.

Keep the server terminal running. Stop it with `Ctrl+C`.

## 8. Accounts And Login

### Initial admin

```text
Mobile: 9642993490
Role: admin
```

With `OTP_DEMO_MODE=True`, the OTP appears in the browser flash message. Configure real SMS before disabling demo mode.

### New farmer

Use **Register** with a real 10-digit Indian mobile number beginning with 6, 7, 8, or 9.

Rejected examples:

```text
1234567890
9876543210
9999999999
08123252305
```

The app validates before creating an OTP record. Format validation cannot prove that a SIM is active; real SMS OTP verification is required for that.

### New admin/staff

An existing admin opens **Staff**, enters the staff member's name, mobile, and optional email, then creates the account. The staff member uses the normal OTP login page.

## 9. Feature Guide

### Mandi prices

The app automatically attempts to synchronize crop prices from the configured live mandi API whenever the farmer or admin prices page is opened. It updates matching stored crop records and falls back to the database when the API is unavailable. Configure `MANDI_API_URL`, `MANDI_API_KEY`, and the field names in `.env`; staff can still edit prices from **Admin -> Prices**. Farmers see the latest price, MSP comparison, price direction, and a compact trend.

### Booking and slots

Farmers choose a crop, quantity, centre, and slot. The app checks capacity, assigns a centre/date token, increments booked count, and sends a notification.

### Live queue

Staff use **Serve next token**. The current farmer becomes completed and the next booked farmer becomes serving. Socket.IO broadcasts updates to queue-status pages. Wait time uses recent completed service durations where available.

### Payments and MSP

Staff can enter a payment amount. If the amount is omitted and an MSP record exists, the app estimates payment from quantity and MSP per quintal.

### QR receipt and check-in

The farmer downloads a PDF receipt from Dashboard or History. Its QR code opens the staff check-in route. Staff confirms arrival.

### Centre map

The Mandi Prices page shows all 15 seeded centres. Centre buttons focus the map and open the selected marker.

### Notifications

Booking, queue, and payment events are saved in-app. Email, Telegram, SMS, and Web Push are optional integrations.

### Analytics and audit log

Analytics shows bookings, completed work, no-shows, pending payments, revenue, centre throughput, average measured waiting time, and the current waiting count. These metrics make queue congestion and waiting-time changes measurable. Audit Log records queue serving, no-shows, payments, slot changes, check-ins, and staff creation.

### Languages

The `EN / HI / KN` switcher changes the visible interface between English, Hindi, and Kannada. Crop names, centre labels, dynamic slot text, queue messages, and map popups are included.

## 10. Telegram Bot (Optional)

Keep the web app running in one terminal. In a second terminal:

```powershell
cd "farmer_procurement_app - Copy"
.\.venv\Scripts\Activate.ps1
py telegram_bot_runner.py
```

Configure:

```env
TELEGRAM_ENABLED=True
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_BOT_USERNAME=your_bot_username
```

Farmers open **Notifications**, link Telegram, and receive queue/payment updates there.

## 11. Optional Email, SMS, And Push

Email:

```env
MAIL_USERNAME=your_email
MAIL_PASSWORD=your_app_password
MAIL_SUPPRESS_SEND=False
```

Twilio SMS:

```env
SMS_ENABLED=True
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=...
```

Web Push requires VAPID keys in `.env`.

## 12. Database Maintenance

Check the database from Flask:

```powershell
py -c "from app import create_app; from app.models import Centre; app=create_app(); ctx=app.app_context(); ctx.push(); print(Centre.query.count()); ctx.pop()"
```

Create and apply future migrations:

```powershell
flask --app run.py db migrate -m "describe the change"
flask --app run.py db upgrade
```

Do not delete production tables to reset test data. Back up first and delete only intended rows.

## 13. Troubleshooting

### Cannot connect to MySQL

- Confirm MySQL Server is running.
- Confirm username/password in `.env`.
- Confirm port `3306` is available.
- Confirm schema name is `farmer_procurement_prod`.

### Login shows an old number

Refresh with `Ctrl+F5`, clear browser autofill, and return to `/auth/login`. Stale OTP session values are cleared on login/logout.

### Protected page redirects to login

Login first, then open the farmer or admin route.

### Assets look old

Use `Ctrl+F5`. Confirm `/static/css/style.css` and `/static/js/main.js` return HTTP `200`.

## 14. Security Notes

- Replace the demo secret key before deployment.
- Never commit `.env`.
- Rotate any API token or password exposed in chat or screenshots.
- Replace demo OTP with Twilio Verify or another real SMS provider.
- Use Redis for Flask-Limiter in multi-instance deployments.
- Use a production WSGI server instead of Flask's development server.
