from django.contrib import admin
from .models import ParkingConfig, Floor, Slot, Ticket
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.register(ParkingConfig)
admin.site.register(Floor)
admin.site.register(Slot)
admin.site.register(Ticket)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("parking.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
