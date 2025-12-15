import heapq
from django.db import transaction
from parking.models import Slot


class SlotAllocator:
    @staticmethod
    @transaction.atomic
    def allocate(vehicle_type, floor, section):
        available_slots = list(
            Slot.objects.select_for_update()
            .filter(
                vehicle_type=vehicle_type,
                floor=floor,
                section=section,
                is_available=True,
            )
            .values_list("slot_number", flat=True)
        )

        if not available_slots:
            return None

        heapq.heapify(
            available_slots
        )  # Min-heap for optimized allocation (smallest slot first)
        slot_no = heapq.heappop(available_slots)

        slot = Slot.objects.get(
            vehicle_type=vehicle_type, floor=floor, section=section, slot_number=slot_no
        )
        slot.is_available = False
        slot.save()

        return slot
