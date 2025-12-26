from django import forms
import re


class VehicleDetailsForm(forms.Form):
    vehicle_number = forms.CharField(
        label="Vehicle Number",
        max_length=15,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    phone = forms.CharField(
        label="Phone Number",
        max_length=15,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    initial_payment = forms.IntegerField(
        label="Initial Payment (₹)",
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )

    def clean_vehicle_number(self):
        vehicle_number = self.cleaned_data.get("vehicle_number").upper()
        if not re.match(r"^[A-Z0-9- ]{3,15}$", vehicle_number):
            raise forms.ValidationError(
                "Enter a valid vehicle number (alphanumeric, 3-15 chars)."
            )
        return vehicle_number

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if not re.match(r"^\+?1?\d{9,15}$", phone):
            raise forms.ValidationError(
                "Enter a valid phone number (e.g., +919876543210)."
            )
        return phone

    def clean_email(self):
        return self.cleaned_data.get("email").lower()
