from django.db import transaction
from parking.models import Slot


class SlotAllocator:
    @staticmethod
    @transaction.atomic
    def allocate(slot_id):
        """
        Atomically allocates a specific slot if it is available.
        Uses select_for_update with skip_locked to prevent race conditions.
        """
        slot = (
            Slot.objects.select_for_update(skip_locked=True)
            .filter(id=slot_id, is_available=True)
            .first()
        )

        if not slot:
            return None  # Slot is either not available or locked by another transaction

        slot.is_available = False
        slot.save(update_fields=["is_available"])

        return slot
