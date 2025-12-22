from django.db import models
from django.utils import timezone


class ParkingConfig(models.Model):
    VEHICLE_CHOICES = (
        ("BIKE", "2 Wheeler"),
        ("CAR", "4 Wheeler"),
    )

    vehicle_type = models.CharField(max_length=10, choices=VEHICLE_CHOICES, unique=True)
    base_price = models.IntegerField(default=30)
    base_hours = models.IntegerField(default=5)
    extra_per_hour = models.IntegerField(default=5)

    def __str__(self):
        return self.vehicle_type


class Floor(models.Model):
    number = models.IntegerField(unique=True)
    price_increment = models.IntegerField(default=0)  # +5 per floor

    def __str__(self):
        return f"Floor {self.number}"


class Slot(models.Model):
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE)
    section = models.CharField(max_length=1)
    slot_number = models.IntegerField()
    vehicle_type = models.CharField(max_length=10)
    is_available = models.BooleanField(default=True)

    class Meta:
        unique_together = ("floor", "section", "slot_number")

    def __str__(self):
        return f"{self.floor}-{self.section}-{self.slot_number}"


class Ticket(models.Model):
    qr_code = models.ImageField(upload_to="qrcodes/", blank=True, null=True)
    vehicle_number = models.CharField(max_length=20)
    phone = models.CharField(max_length=15)
    vehicle_type = models.CharField(max_length=10)
    slot = models.ForeignKey(Slot, on_delete=models.SET_NULL, null=True)
    check_in = models.DateTimeField(default=timezone.now)
    check_out = models.DateTimeField(null=True, blank=True)
    initial_payment = models.IntegerField(default=0)
    final_amount = models.IntegerField(null=True, blank=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"Token #{self.id}"
