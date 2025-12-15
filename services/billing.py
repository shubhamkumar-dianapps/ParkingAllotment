import math
from django.utils import timezone
from parking.models import ParkingConfig


class BillingService:
    @staticmethod
    def calculate(ticket):
        config = ParkingConfig.objects.get(vehicle_type=ticket.vehicle_type)
        floor_increment = ticket.slot.floor.price_increment
        base_price = config.base_price + floor_increment

        hours = math.ceil((timezone.now() - ticket.check_in).total_seconds() / 3600)

        total = base_price
        if hours > config.base_hours:
            total += (hours - config.base_hours) * config.extra_per_hour

        refund = max(ticket.initial_payment - total, 0)
        due = max(total - ticket.initial_payment, 0)

        return total, refund, due, hours
