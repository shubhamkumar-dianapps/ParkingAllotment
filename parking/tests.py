from decimal import Decimal
from django.test import TestCase, RequestFactory
from django.utils import timezone
from django.urls import reverse
from parking.models import Floor, VehicleType, ParkingConfig, Slot, Ticket
from services.billing import BillingService
from services.parking_manager import ParkingManager
from parking.views import vehicle_form, checkout


class SetupMixin:
    def setUp(self):
        # Create Vehicle Types
        self.car_type = VehicleType.objects.create(name="CAR")
        self.bike_type = VehicleType.objects.create(name="BIKE")

        # Create Configs
        ParkingConfig.objects.create(
            vehicle_type=self.car_type,
            base_price=Decimal("30.00"),
            base_hours=1,
            extra_per_hour=Decimal("10.00"),
        )
        ParkingConfig.objects.create(
            vehicle_type=self.bike_type,
            base_price=Decimal("10.00"),
            base_hours=1,
            extra_per_hour=Decimal("5.00"),
        )

        # Create Floors
        self.floor1 = Floor.objects.create(number=1, price_increment=Decimal("0.00"))

        # Create Slots
        self.slot1 = Slot.objects.create(
            floor=self.floor1,
            section="A",
            slot_number=1,
            vehicle_type=self.car_type,
            is_available=True,
        )


class BillingServiceTests(SetupMixin, TestCase):
    def test_calculate_base_price(self):
        ticket = Ticket.objects.create(
            vehicle_number="ABC-123",
            phone="1234567890",
            vehicle_type=self.car_type,
            slot=self.slot1,
            check_in=timezone.now() - timezone.timedelta(minutes=30),  # 0.5 hours
            initial_payment=Decimal("0.00"),
        )
        total, refund, due, hours = BillingService.calculate(ticket)
        self.assertEqual(total, Decimal("30.00"))  # Base price for CAR
        self.assertEqual(hours, 1)

    def test_calculate_extra_hours(self):
        ticket = Ticket.objects.create(
            vehicle_number="ABC-123",
            phone="1234567890",
            vehicle_type=self.car_type,
            slot=self.slot1,
            check_in=timezone.now()
            - timezone.timedelta(hours=3, minutes=1),  # 4 hours range
            initial_payment=Decimal("0.00"),
        )
        # 4 hours total. Base 1 hour = 30. Extra 3 hours * 10 = 30. Total Should be 60.
        total, refund, due, hours = BillingService.calculate(ticket)

        # Logic in service is: ceil(seconds/3600). 3h1m -> 4 hours.
        # if hours > base_hours (1): total += (hours - base) * extra
        # 30 + (4-1)*10 = 30 + 30 = 60.
        self.assertEqual(total, Decimal("60.00"))
        self.assertEqual(hours, 4)


class ParkingManagerTests(SetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()

    def test_book_vehicle_success(self):
        request = self.factory.get("/")
        form_data = type(
            "obj",
            (object,),
            {
                "save": lambda commit=True: Ticket(
                    vehicle_number="TEST-001", phone="999", email="test@example.com"
                )
            },
        )

        result = ParkingManager.book_vehicle(request, self.slot1.id, form_data)

        self.assertIsNotNone(result)
        self.assertEqual(result["ticket"].vehicle_number, "TEST-001")
        self.assertFalse(Slot.objects.get(id=self.slot1.id).is_available)

    def test_process_checkout(self):
        ticket = Ticket.objects.create(
            vehicle_number="OUT-001",
            phone="888",
            vehicle_type=self.car_type,
            slot=self.slot1,
            check_in=timezone.now() - timezone.timedelta(hours=2),
        )
        # Slot was taken
        self.slot1.is_available = False
        self.slot1.save()

        success, data = ParkingManager.process_checkout(ticket.id)

        self.assertTrue(success)
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.check_out)
        self.assertTrue(Slot.objects.get(id=self.slot1.id).is_available)


class ViewTests(SetupMixin, TestCase):
    def test_home_page(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)

    def test_select_vehicle(self):
        response = self.client.get(reverse("select_vehicle"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CAR")

    def test_view_slots(self):
        response = self.client.get(reverse("view_slots", args=[self.car_type.id]))
        self.assertEqual(response.status_code, 200)
        # Expect to see slot number "1"
        self.assertIn(b">1<", response.content.replace(b"\n", b"").replace(b" ", b""))
