from django.shortcuts import render
from payments import provider_factory

from saleor.order.models import Payment

# Create your views here.

def direct_to_pay(request, token):
    """post to cash flow merchantdise with params needed

     - use token to get correspond payment model
     - all data needed are in payment
     - call process_data (a unify facade for transfering payment data to
       cash flow merchandise)

    """
    context = {
        'page': 'direct_to_pay'
    }

    if token is not None:
        payment = Payment.objects.filter(token=token).first()


    provider = provider_factory(payment.variant)
    form = provider.process_data(payment, request)

    context['form'] = form

    return render(request, 'payments/direct_to_pay.html', context)
