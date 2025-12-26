from django.db import transaction
from parking.models import Slot


class SlotAllocator:
    @staticmethod
    @transaction.atomic
    def allocate(vehicle_type, floor, section):
        slot = (
            Slot.objects.select_for_update(skip_locked=True)
            .filter(
                vehicle_type=vehicle_type,
                floor=floor,
                section=section,
                is_available=True,
            )
            .order_by("slot_number")
            .first()
        )

        if not slot:
            return None

        slot.is_available = False
        slot.save(update_fields=["is_available"])

        return slot
