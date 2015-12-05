from django import forms

from payments.forms import PaymentForm
from payments.models import PAYMENT_STATUS_CHOICES


class PayPalForm(PaymentForm):

    """
    """

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data
