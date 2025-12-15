import math
import uuid
from django.utils import timezone


class TokenService:
    @staticmethod
    def generate_token():
        return str(uuid.uuid4())[:8].upper()


class BillingService:
    BASE_HOURS = 5
    CAR_BASE_PRICE = 50
    BIKE_BASE_PRICE = 30
    CAR_EXTRA = 10
    BIKE_EXTRA = 5

    @classmethod
    def calculate_bill(cls, ticket):
        end_time = timezone.now()
        hours = math.ceil((end_time - ticket.check_in_time).total_seconds() / 3600)

        if ticket.vehicle_type == "CAR":
            base = cls.CAR_BASE_PRICE
            extra_rate = cls.CAR_EXTRA
        else:
            base = cls.BIKE_BASE_PRICE
            extra_rate = cls.BIKE_EXTRA

        total = base
        if hours > cls.BASE_HOURS:
            total += (hours - cls.BASE_HOURS) * extra_rate

        return {
            "hours": hours,
            "total": total,
            "refund": max(ticket.paid_amount - total, 0),
            "due": max(total - ticket.paid_amount, 0),
        }
