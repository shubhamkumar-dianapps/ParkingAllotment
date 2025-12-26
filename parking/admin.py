from django.contrib import admin
from .models import ParkingConfig, Floor, Slot, Ticket


@admin.register(Ticket)
class TicketModelAdmin(admin.ModelAdmin):
    search_fields = ("id", "vehicle_number", "phone", "email")
    list_display = (
        "id",
        "vehicle_number",
        "vehicle_type",
        "slot",
        "check_in",
        "check_out",
        "final_amount",
    )
    list_filter = ("vehicle_type", "check_in", "check_out", "slot__floor")


admin.site.register(ParkingConfig)
admin.site.register(Floor)
admin.site.register(Slot)
