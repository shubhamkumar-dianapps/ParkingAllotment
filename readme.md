# Elite Parking Management System  
**Project Documentation**

**Version**: 1.0  
**Date**: December 14, 2025  
**Technology Stack**: Django 5+, Python 3.12, Bootstrap 5, SQLite.

## 1. Project Overview

Elite Parking is a modern, web-based multi-level parking management system designed for premium parking facilities. The system enables customers to:

- Select vehicle type (2-Wheeler or 4-Wheeler)
- View real-time available parking slots across multiple floors
- Visually select and book a specific slot
- Receive a unique, clear token upon successful booking
- Checkout using the token and receive a detailed bill with automatic refund or due amount calculation

The system supports concurrent bookings from multiple entry gates using database-level locking to prevent double allocation.

**Key Components**:
- **Views** — Handle HTTP requests and render templates
- **Models** — Define database schema and relationships
- **Services** — Contain core business logic (slot allocation, billing)
- **Utils** — Helper functions for reusable operations
- **Templates** — Responsive HTML with Bootstrap 5
- **Management Commands** — For system initialization and maintenance

## 3. Workflow Diagram (Text Representation)



## 4. Database Entities & Attributes

| Entity            | Attributes                                                                 | Description                                                                 |
|-------------------|----------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| **Floor**         | `number` (Integer, unique) <br> `price_increment` (Integer)                 | Represents a parking floor with incremental pricing (e.g., +₹5 per floor)   |
| **Slot**          | `floor` (ForeignKey → Floor) <br> `section` (Char: A-G) <br> `slot_number` (Integer: 1–50) <br> `vehicle_type` (CAR/BIKE) <br> `is_available` (Boolean, default=True) | Individual parking space; unique per floor/section/number                    |
| **ParkingConfig** | `vehicle_type` (CAR/BIKE, unique) <br> `base_price` (Integer) <br> `base_hours` (Integer, default=5) <br> `extra_per_hour` (Integer) | Configurable base rates and extra hour charges per vehicle type              |
| **Ticket**        | `id` (Auto-increment Primary Key) <br> `vehicle_number` (String) <br> `phone` (String) <br> `vehicle_type` (CAR/BIKE) <br> `slot` (ForeignKey → Slot) <br> `check_in` (DateTime, auto) <br> `check_out` (DateTime, nullable) <br> `initial_payment` (Integer) <br> `final_amount` (Integer, nullable) | Parking session record; `id` serves as customer-facing token number         |

**Total Slots**: 10 floors × 7 sections × 50 slots = **3,500 slots**  
- 4-Wheeler: 2,000 slots (Sections A–D)  
- 2-Wheeler: 1,500 slots (Sections E–G)

**Space Complexity** - 16kb for 3500 slots.
### For 1 Million Slots - 5mb.

## 5. Key Functions & Responsibilities

| Function / View                | One-Line Responsibility                                                                 |
|--------------------------------|-----------------------------------------------------------------------------------------|
| `home`                         | Renders the landing page with Park and Checkout options                                 |
| `select_vehicle`               | Displays premium vehicle type selection (2-Wheeler / 4-Wheeler)                         |
| `view_slots`                   | Shows real-time available slots with floor pagination and section grouping             |
| `vehicle_form`                 | Collects vehicle details and confirms booking with thread-safe slot allocation          |
| `checkout`                     | Processes token, calculates final bill, handles refund/due, and frees the slot          |
| `token_success`                | Dedicated full-screen page displaying the token number post-booking                     |
| `SlotAllocator.allocate()`     | Performs thread-safe slot allocation using `select_for_update` to support multiple gates|
| `BillingService.calculate()`   | Computes total charges, extra hours, refund, or due amount based on duration and rates  |
| `init_parking_data` (command)  | Initializes all 10 floors and 3,500 slots with correct vehicle-type segregation         |

## 6. Key Features Implemented

- Real-time slot availability with visual grid and section grouping
- Floor-wise dynamic pricing (admin-configurable base + per-floor increment)
- Concurrent-safe booking (supports multiple entry gates)
- Dedicated token display page for enhanced customer experience
- Automatic refund/overpayment handling at checkout
- Fully responsive, premium UI with animations and hover effects
- Complete admin panel for configuration (rates, floors, slots)
- Clean code architecture following SOLID principles

# Key Technical Decisions & Why They Are Good

- **Used qrcode library**  
  → Industry standard, reliable, high-quality output

- **Saved QR to model field**  
  → Persistent, can be shown anytime (token page, bill)

- **Embedded in PDF using ReportLab**  
  → Customer gets complete token with QR in one printable file

- **Used larger box_size (15)**  
  → Ensures QR is scannable even when printed or viewed on small screens

- **Base64 + JavaScript auto-download**  
  → PDF downloads immediately without page refresh

- **Media serving configured**  
  → QR images load correctly in browser


**Project Status**: Fully functional
