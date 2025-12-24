# Elite Parking Management System  
**Project Documentation**

**Version**: 1.0  
**Date**: December 14, 2025  
**Technology Stack**: Django 5+, Python 3.12, Bootstrap 5, SQLite.

## 1. Project Overview

  Comprehensive Django-based parking management system for multi-floor facilities. The project provides a responsive customer-facing UI, admin controls, tokenized parking tickets with QR codes, PDF billing, and robust concurrent-safe slot allocation.

  ---

  ## Quick facts
  - Technology: Django, Python
  - Database: SQLite (development), pluggable for production (Postgres recommended)
  - Frontend: Django templates + Bootstrap
  - Media: QR codes and generated PDFs stored in `media/`

  ---

  ## Contents
  - Overview
  - Workflow diagram (Mermaid)
  - Features
  - Architecture & key modules
  - Installation & setup
  - Usage & common commands
  - Testing & deployment notes
  - Contributing & contact

  ---

  ## Project Overview

  This application manages parking operations end-to-end: slot allocation, check-in, ticketing (QR), billing (PDF), and checkout. It supports multi-gate concurrent bookings using database row locking and clear separation between HTTP views and business logic (services).

  ---

  ## Workflow Diagram

  The following Mermaid diagram shows the primary user flow from arrival to exit. You can render this in GitHub or VS Code with a Mermaid extension.

  ```mermaid
  flowchart TD
    A[Customer arrives / Home] --> B{Select action}
    B -->|Park| C[Choose vehicle type]
    C --> D[Select slot]
    D --> E[Book slot & create Ticket]
    E --> F[Generate QR & PDF ticket]
    F --> G[Display token (token_success)]
    G --> H[Use token for checkout]
    H --> I[Calculate bill via Billing Service]
    I --> J[Complete payment / Refund]
    J --> K[Free slot & archive Ticket]

    subgraph Admin
      L[Admin panel] --> M[Configure floors, rates, slots]
      M --> N[Run init_parking_data]
    end
    N --> D
  ```

  If you prefer a PNG/SVG export of the diagram, I can generate and add it to `docs/`.

  ---

  ## Key Features
  - Real-time slot availability and visual slot grid
  - Multi-floor dynamic pricing and per-vehicle-type configuration
  - Thread-safe slot allocation supporting multiple gates
  - Tokenized booking with QR code generation and persistent media
  - PDF ticket generation (embedded QR) for easy printing/download
  - Admin management for floors, slots, and pricing

  ---

  ## Architecture & Important Files

  - `manage.py` — Django CLI entrypoint
  - `django_project/settings.py` — project settings (DB, media, email)
  - `parking/models.py` — core data models (Floor, Slot, ParkingConfig, Ticket)
  - `parking/views.py` — HTTP views and template rendering
  - `parking/urls.py` — URL routes for the app
  - `parking/services.py` — higher-level service helpers used by views
  - `services/slot_allocator.py` — slot allocation logic with DB locking
  - `services/billing.py` — billing calculations and refunds
  - `services/qr_generator.py` — QR code generation and storage
  - `services/pdf_generator.py` — PDF ticket creation (ReportLab or similar)
  - `templates/` — customer-facing pages (home, park, checkout, token, bill)
  - `media/qrcodes/` — stored QR images
  - `parking/management/commands/init_parking_data.py` — initializes floors & slots

  Each module is focused on a small responsibility so logic is testable and maintainable.

  ---

  ## Functions & Responsibilities (summary)

  - `services/slot_allocator.py` — `allocate()` / `release()` : find and reserve a slot using `select_for_update()` inside a transaction to prevent races.
  - `services/billing.py` — `calculate_total()` : compute base charge, additional hourly charges, and refund/due adjustments.
  - `services/qr_generator.py` — `generate_qr_for_ticket()` : create and save QR image for a `Ticket` instance.
  - `services/pdf_generator.py` — `ticket_to_pdf()` : compose a printable PDF embedding the QR and ticket details.
  - `parking/management/commands/init_parking_data.py` — populates floors and slots with proper vehicle-type segregation.

  ---

  ## Installation & Setup (Development)

  1. Create and activate a virtual environment (recommended):

  ```bash
  python -m venv .venv
  .\.venv\Scripts\activate
  ```

  2. Install dependencies:

  ```bash
  pip install -r requirements.txt
  ```

  3. Apply migrations and initialize data:

  ```bash
  python manage.py migrate
  python manage.py loaddata initial_data  # if provided
  python manage.py init_parking_data
  ```

  4. Create a superuser to access the admin panel:

  ```bash
  python manage.py createsuperuser
  ```

  5. Run the development server:

  ```bash
  python manage.py runserver
  ```

  Open http://127.0.0.1:8000/ to view the app.

  ---

  ## Configuration

  - `django_project/settings.py` holds local settings. For production, prefer environment variables for:
    - `SECRET_KEY`
    - `DATABASE_URL`
    - Email backend credentials for sending receipts
    - `MEDIA_ROOT` / `MEDIA_URL`

  - Example `.env` entries (use django-environ or similar):

  ```
  SECRET_KEY=changeme
  DATABASE_URL=sqlite:///db.sqlite3
  EMAIL_HOST=smtp.example.com
  EMAIL_USER=...
  EMAIL_PASSWORD=...
  ```

  ---

  ## Usage & Common Flows

  - Park a vehicle: Home → Select vehicle type → Choose slot → Confirm → Token page (QR)
  - Checkout: Enter token → Billing calculation → Payment → Slot released
  - Admin: Login to `/admin/` to change `ParkingConfig`, manage floors/slots, or re-run initialization

  ---

  ## Data Initialization

  Use the management command to seed floors/slots:

  ```bash
  python manage.py init_parking_data
  ```

  This will create the floor/slot records used by the app.

  ---

  ## Testing

  Run built-in Django tests:

  ```bash
  python manage.py test
  ```

  Add unit tests for `services/` modules to validate allocation, billing, and QR/pdf generation.

  ---

  ## Deployment Notes

  - Use Postgres for production and configure `DATABASES` accordingly.
  - Serve static files via CDN or via `collectstatic` behind a web server.
  - Serve media (QRs, PDFs) from cloud storage (S3) in production.
  - Use HTTPS and properly set `SECURE_*` Django settings.

  ---

  ## Troubleshooting

  - QR not readable: increase QR `box_size` in `services/qr_generator.py` and regenerate.
  - Slot double-booking: ensure DB transactions and `select_for_update()` are supported by your DB engine.
  - PDF download issues: check media URL configuration and file permissions.

  ---

