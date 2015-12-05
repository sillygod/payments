from django import forms

from payments.forms import PaymentForm
from payments.models import PAYMENT_STATUS_CHOICES


class AllPayForm(PaymentForm):

    """Baseclass's function is enough for us
    """

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data
