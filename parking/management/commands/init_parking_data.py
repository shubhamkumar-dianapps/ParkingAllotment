from django.core.management.base import BaseCommand
from parking.models import Floor, Slot, ParkingConfig, VehicleType


class Command(BaseCommand):
    help = "Initialize floors and slots"

    def handle(self, *args, **options):
        # Create Vehicle Types
        car_type, _ = VehicleType.objects.get_or_create(name="CAR")
        bike_type, _ = VehicleType.objects.get_or_create(name="BIKE")
        self.stdout.write(self.style.SUCCESS("Vehicle types ensured"))

        CAR_SECTIONS = ["A", "B", "C", "D"]
        BIKE_SECTIONS = ["E", "F", "G"]
        TOTAL_FLOORS = 10
        SLOTS_PER_SECTION = 50

        for floor_no in range(1, TOTAL_FLOORS + 1):
            floor, created = Floor.objects.get_or_create(
                number=floor_no, defaults={"price_increment": (floor_no - 1) * 5}
            )
            if created:
                self.stdout.write(f"Created Floor {floor_no}")

            for section in CAR_SECTIONS:
                for slot_no in range(1, SLOTS_PER_SECTION + 1):
                    Slot.objects.get_or_create(
                        floor=floor,
                        section=section,
                        slot_number=slot_no,
                        vehicle_type=car_type,
                        defaults={"is_available": True},
                    )

            for section in BIKE_SECTIONS:
                for slot_no in range(1, SLOTS_PER_SECTION + 1):
                    Slot.objects.get_or_create(
                        floor=floor,
                        section=section,
                        slot_number=slot_no,
                        vehicle_type=bike_type,
                        defaults={"is_available": True},
                    )

        self.stdout.write(self.style.SUCCESS("Data initialized"))

        # After creating slots...
        ParkingConfig.objects.get_or_create(
            vehicle_type=bike_type,
            defaults={"base_price": 30, "base_hours": 5, "extra_per_hour": 5},
        )
        ParkingConfig.objects.get_or_create(
            vehicle_type=car_type,
            defaults={"base_price": 50, "base_hours": 5, "extra_per_hour": 10},
        )
        self.stdout.write(self.style.SUCCESS("Parking configurations set"))
