from django import forms
from .models import Ticket
import re
import logging

# Get the logger instance
logger = logging.getLogger(__name__)


class VehicleDetailsForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["vehicle_number", "phone", "email", "initial_payment"]
        widgets = {
            "vehicle_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. RJ14-CC-1234"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "+91XXXXXXXXXX"}
            ),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "initial_payment": forms.NumberInput(attrs={"class": "form-control"}),
        }
        labels = {
            "vehicle_number": "Vehicle Number",
            "phone": "Phone Number",
            "email": "Email Address",
            "initial_payment": "Initial Payment (₹)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["initial_payment"].required = False
        self.fields["initial_payment"].initial = 0

    def clean_vehicle_number(self):
        val = self.cleaned_data.get("vehicle_number").strip().upper()
        # Regular expression for a standard vehicle plate
        if not re.match(r"^[A-Z0-9- ]{3,15}$", val):
            # LOG: Audit trail for invalid input
            logger.warning(
                f"Form Validation Error: Invalid Vehicle Number entered: '{val}'"
            )

            # MESSAGE: Shown to the user in the template
            raise forms.ValidationError(
                "Invalid format. Use 3-15 alphanumeric characters, spaces, or hyphens."
            )
        return val

    def clean_phone(self):
        val = self.cleaned_data.get("phone").strip()
        # Regex for international phone format
        if not re.match(r"^\+?1?\d{9,15}$", val):
            # LOG: Capture suspicious or malformed phone numbers
            logger.warning(
                f"Form Validation Error: Invalid Phone Number entered: '{val}'"
            )

            # MESSAGE: Shown to the user in the template
            raise forms.ValidationError(
                "Enter a valid phone number. It must be 9-15 digits and can start with '+'."
            )
        return val

    def clean_email(self):
        email = self.cleaned_data.get("email").strip().lower()
        # EmailField already does basic validation, but you can add custom logic here
        return email
