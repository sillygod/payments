import json

from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.http import Http404
from django.shortcuts import redirect
from django.conf import settings
from django.db import transaction

from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_jwt.authentication import JSONWebTokenAuthentication

from saleor.order.models import Order
from saleor.order.models import Payment
from saleor.order.models import get_ip
from payments import provider_factory

from cnpayments.alipay import AliPayProvider
from cnpayments.allpay import AllPayProvider
from cnpayments.models import CashFlowLog

from .authentications import EnableExternalRequest


class PaymentProcess(APIView):

    """Accept pay mehtod and order token to redirect to pay site

    before create payment, we need to check some info
    start to create payment..
    direct to correspond pay site according to pay methdo

    """

    permission_classes = (permissions.AllowAny, )
    authentication_classes = (JSONWebTokenAuthentication, )

    def get(self, request):
        """grab query params and create payment

        accept url like. /../payment_process?token=jfeifjeifje&method=allpay
        """

        data = request.query_params

        if data['token'] is not None:
            order = Order.objects.filter(token=data['token']).first()
            # start to check order total number is consistent with sum of all items
            price_consistent = True

            if not price_consistent:

                return HttpResponse('price is not consistent')
        else:
            return HttpResponse('could not find order')

        # start to create a payment
        billing = order.billing_address
        total = order.get_total()
        variant = data['method']

        defaults = {
            'total': total.gross,
            'tax': total.tax,
            'currency': total.currency,
            'delivery': order.get_delivery_total().gross,
            'billing_first_name': billing.first_name,
            'billing_last_name': billing.last_name,
            'billing_city': billing.city,
            'billing_country_code': billing.country,
            'billing_email': order.get_user_email(),
            'description': 'test description',
            'billing_country_area': billing.country_area,
            'customer_ip_address': get_ip(request)
        }

        if not variant in [v for v, n in settings.CHECKOUT_PAYMENT_CHOICES]:
            raise Http404('{} is not a valid payment variant'.format(variant))

        with transaction.atomic():
            order.change_status('payment-pending')
            payment, _created = Payment.objects.get_or_create(
                variant=variant,
                status='waiting',
                order=order,
                defaults=defaults
            )


        # I think I should redirect with a payment token
        return redirect('cnpayments:direct_to_pay', token=payment.token)


class AsynchroNotify(APIView):

    """Receive the notify_url from the Alipay..

    note. we need to use csrf_exempt and log
    """

    permissions = (permissions.AllowAny, )
    authentication_classes = (EnableExternalRequest, )

    def post(self, request):
        """log the request first, and then process the cash flow response
        """
        alipay = AliPayProvider()  # special use, no param given, just call some method
        data = request.data

        if alipay.verify_notify(**data):
            # verify pass, TODO: do some process here ex. payment processing and logging

            return HttpResponse('success')
        else:
            # this request may be faked which made by cracker..
            pass


        return HttpResponse('fail')


class SynchroNotify(APIView):

    """This view handle the notify after aplipay payment complete
    """

    permissions = (permissions.AllowAny, )
    authentication_classes = (EnableExternalRequest, )

    def get(self, request):
        """process the trade info returned from alipay and then redirect to
        the order view page if it's verified. Otherwise, redirect to
        """

        alipay = AliPayProvider()
        data = request.query_params

        if alipay.verify_notify(**data):
            # TODO: same as above

            return HttpResponseRedirect('')
        else:


            return HttpResponseRedirect('/')

# above APIs are fro alipay


class AllPayAsynchroNotify(APIView):

    """This view handle the notify after allpay payment complete

    check the checkMacValue

    """

    permissions = (permissions.AllowAny, )
    authentication_classes = (EnableExternalRequest, )

    def post(self, request):
        """
        """

        allpay = provider_factory('allpay')
        data = request.data

        cash_flow_log = CashFlowLog.objects.create(
            json_res=json.dumps(data),
            source_device=request.META['HTTP_USER_AGENT'],
            source_ip=get_ip(request),
        )

        data = json.loads(json.dumps(data))

        if allpay.verify_macValue(**data):

            RtnCode = int(data['RtnCode'])

            if RtnCode in [1, 800]:
                tradeNo = data['MerchantTradeNo']
                payment = Payment.objects.filter(tradeNo=tradeNo).first()
                payment.logs = cash_flow_log.pk
                payment.attrs.PaymentDate = data['PaymentDate']

                payment.change_status('confirmed')
            else:
                return HttpResponse('0|ErrorMessage')

            return HttpResponse('1|OK')
        else:

            return HttpResponse('0|ErrorMessage')


class AllPaySynchroNotify(APIView):

    """
    """

    permissions = (permissions.AllowAny, )
    authentication_classes = (EnableExternalRequest, )

    def post(self, request):
        """
        """
        allpay = provider_factory('allpay')
        data = request.data

        cashFlowLog = CashFlowLog.objects.create(
            json_res=json.dumps(data),
            source_device=request.META['HTTP_USER_AGENT'],
            source_ip=get_ip(request),
        )

        tradeNo = data['MerchantTradeNo']
        payment = Payment.objects.filter(tradeNo=tradeNo).first()
        payment.logs = cashFlowLog.pk
        payment.save()

        data = json.loads(json.dumps(data))

        if allpay.verify_macValue(**data):

            return HttpResponseRedirect('/profile/orderList/')

        else:
            return HttpResponseRedirect('/')


class PayPalSynchroNotify(APIView):

    """ TODO: need to check paypal use post or get method to
    return url..
    """

    permissions = (permissions.AllowAny, )
    authentication_classes = (EnableExternalRequest, )

    def _addLogForCashFlow(self, payment, data):
        """
        """
        cashFlowLog = CashFlowLog.objects.create(
            json_res=json.dumps(data),
            source_device=self.request.META['HTTP_USER_AGENT'],
            source_ip=get_ip(self.request),
        )
        payment.logs = cashFlowLog.pk
        payment.save()


    def get(self, request, payment_token):
        """
        we will get something like this
        <QueryDict: {'token': ['EC-4P809628KK1823013'], 'PayerID': ['MBKAY3Q6GMASN']}>

        PayerID is need for capture payment
        """
        data = request.query_params
        paypal = provider_factory('paypal')

        # import pdb
        # pdb.set_trace()

        _params = {
            'TOKEN': data['token'],
        }

        cashFlowLog = CashFlowLog.objects.create(
            json_res=json.dumps(data),
            source_device=request.META['HTTP_USER_AGENT'],
            source_ip=get_ip(request),
        )

        payment = Payment.objects.filter(token=payment_token).first()
        payment.logs = cashFlowLog.pk
        payment.save()


        # call GetExpressCheckoutDetail api
        url = paypal.getExpressCheckoutDetails(**_params)
        res = paypal.get_nvp_response(url)
        self._addLogForCashFlow(payment, res)

        if res['ACK'][0] == 'Failure':
            return HttpResponseRedirect('/')
        else:
            # go on DoExpressCheckoutPayment..
            # auto confirm?
            doExpress_data = {
                'TOKEN': res['TOKEN'][0],
                'PAYERID': res['PAYERID'][0],
                'PAYMENTREQUEST_0_PAYMENTACTION': 'Sale',
                'PAYMENTREQUEST_0_AMT': payment.get_total_price().gross,
            }

            url = paypal.doExpressCheckoutPayment(**doExpress_data)
            res = paypal.get_nvp_response(url)
            self._addLogForCashFlow(payment, res)

            if res['ACK'][0] == 'Failure':
                return HttpResponseRedirect('/')
            else:
                # start to change payment status
                # change order status, note Order model line 45
                # it will automatically check whether order is full paid or not
                # and then change order status when I change the payment status

                payment.change_status('confirmed')


        return HttpResponseRedirect('/profile/orderList/')
