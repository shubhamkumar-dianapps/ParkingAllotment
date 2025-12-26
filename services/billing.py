import math
from django.utils import timezone
from django.core.cache import cache
from parking.models import ParkingConfig


class BillingService:
    CACHE_TTL = 86400  # 24 hours

    @staticmethod
    def _get_config(vehicle_type):
        """Retrieve ParkingConfig from cache or database."""
        cache_key = f"parking_config_{vehicle_type}"
        config = cache.get(cache_key)
        if not config:
            config = ParkingConfig.objects.get(vehicle_type=vehicle_type)
            cache.set(cache_key, config, BillingService.CACHE_TTL)
        return config

    @staticmethod
    def calculate(ticket):
        config = BillingService._get_config(ticket.vehicle_type)
        floor_increment = ticket.slot.floor.price_increment
        base_price = config.base_price + floor_increment

        hours = math.ceil((timezone.now() - ticket.check_in).total_seconds() / 3600)

        total = base_price
        if hours > config.base_hours:
            total += (hours - config.base_hours) * config.extra_per_hour

        refund = max(ticket.initial_payment - total, 0)
        due = max(total - ticket.initial_payment, 0)

        return total, refund, due, hours
