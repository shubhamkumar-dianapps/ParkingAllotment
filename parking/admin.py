from django.contrib import admin
from .models import ParkingConfig, Floor, Slot, Ticket

admin.site.register(ParkingConfig)
admin.site.register(Floor)
admin.site.register(Slot)
admin.site.register(Ticket)
