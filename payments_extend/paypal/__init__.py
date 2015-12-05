import binascii
import collections
import json
import hashlib
import copy
from urllib.parse import quote_plus, urlencode
from urllib.parse import parse_qs

from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect
from django.core.urlresolvers import reverse
from django.utils.translation import pgettext_lazy

from payments import BasicProvider
import requests

from .forms import PayPalForm

from .exceptions import MissingParameter
from .exceptions import ParameterValueError


class PayPalExpressCheckoutProvider(BasicProvider):

    """Implement paypal Express checkout payment.

    there are some steps we need to implement..

    1. request SetExpresscheckout
    2. use token redirect to paypal login page
    3. request GetExpressCheckoutDetails with token when we redirect back to our
       site
    4. DoExpressCheckoutPayment
    """

    _action = "https://api-3t.sandbox.paypal.com/nvp"
    _version = "124"
    _cmd_gateway = 'https://www.paypal.com/cgi-bin/webscr'

    def __init__(self, user, pwd, signature, version=_version, endpoint=_action,
        cmd_gateway=_cmd_gateway):
        self._user = user
        self._pwd = pwd
        self._signature = signature
        self._version = version
        self._action = endpoint
        self._cmd_gateway = cmd_gateway

        self._core_params = {
            "USER": self._user,
            "PWD": self._pwd,
            "SIGNATURE": self._signature,
            "VERSION": self._version,
        }

    def _check_params(self, params, requirements):
        """check params which are needed by paypal express checkout
        """
        if not all([k in params for k in requirements]):
            raise MissingParameter('missing parameters')

    def getExpressCheckoutDetails(self, **kwargs):
        """it seems that call this api when paypal redirect to our
        page...

        response
            ACK success or failure
        """
        params_required = ('TOKEN', )
        self._check_params(kwargs, params_required)
        url = self._build_express_api_url('GetExpressCheckoutDetails', **kwargs)

        return url

    def doExpressCheckoutPayment(self, **kwargs):
        """final step to make a deal
        """
        params_required = ('TOKEN', 'PAYERID', 'PAYMENTREQUEST_0_PAYMENTACTION',
            'PAYMENTREQUEST_0_AMT')
        self._check_params(kwargs, params_required)
        url = self._build_express_api_url('DoExpressCheckoutPayment', **kwargs)

        return url

    def setExpressCheckout(self, **kwargs):
        """express checkout method -- setExpressCheckout

        this is the first step of flow of ExpressCheck process
        """
        params_required = (
            'PAYMENTREQUEST_0_AMT',
            'PAYMENTREQUEST_0_PAYMENTACTION',
            'RETURNURL',
            'CANCELURL',
            'REQCONFIRMSHIPPING',
            'NOSHIPPING',
            'ADDROVERRIDE')
        # noshipping 1
        # reqconfirmshipping 0
        # addroverride 0 -- not display shipping address
        # PAYMENTREQUEST_0_PAYMENTACTION -- SALE

        # https://developer.paypal.com/docs/classic/api/merchant/SetExpressCheckout_API_Operation_NVP/
        self._check_params(kwargs, params_required)
        url = self._build_express_api_url('SetExpressCheckout', **kwargs)
        return url

    def _build_express_api_url(self, method, **kwargs):
        """generate express checkout api url
        """
        _params = self._core_params.copy()
        _params['METHOD'] = method
        _params.update(kwargs)

        url = '{}?{}'.format(self._action, urlencode(_params))

        return url

    def get_synchro_notify_url(self, request, payment_token):
        """build the aboslute uri for facade url which will be redirect to
        by paypal
        """
        url = request.build_absolute_uri(
            reverse('web_api:cnpayments:paypal_synchro_notify',
                kwargs={'payment_token': payment_token}))
        return url

    def get_cancel_url(self, request):
        """where to redirect to? Did I need to cancel the payment? or just
        ignore it
        """
        url = request.build_absolute_uri(reverse('product_introduction'))
        return url

    def get_nvp_response(self, url):
        """an util function for getting response of nvp api
        """
        r = requests.get(url)
        res = parse_qs(r.text)
        return res

    def get_form(self, payment, data=None):
        """call setExpressCheckout api to get token and redirect to
        paypal login page with it
        """
        if payment.status == 'waiting':
            payment.change_status('input')
        else:
            return None

        form = PayPalForm(data=data, provider=self, payment=payment)
        form.gateway = self._cmd_gateway

        return form


    def process_data(self, payment, request, **kwargs):
        """process the data and fill them to paypal form...

        note. PAYMENTREQUEST_n_TRANSACTIONID is only returned after a
        successful transaction for DoExpressCheckout..

        So we need to think a way for capture a payment.. when step 2 and 3.
        Currently, I think use django url pattern to match a token param..
        """

        items = payment.get_purchased_items()

        itemName = '#'.join([item.name for item in items])
        itemCounts = '#'.join([str(item.quantity) for item in items])
        itemPrice = '#'.join([str(int(item.price)) for item in items])

        # set params needed by setExpressCheckout api

        _params = {
            'PAYMENTREQUEST_0_AMT': int(payment.get_total_price().gross),
            'PAYMENTREQUEST_0_PAYMENTACTION': 'Sale',
            'RETURNURL': self.get_synchro_notify_url(request, payment.token),
            'CANCELURL': self.get_cancel_url(request),
            'REQCONFIRMSHIPPING': '0',
            'NOSHIPPING': '1',
            'ADDROVERRIDE': '0',
            'LOCALECODE': 'C2',  # set country
            'LANDINGPAGE': 'Billing',
            # 'SOLUTIONTYPE': 'Sole',
            # 'USERSELECTEDFUNDINGSOURCE': 'ChinaUnionPay'
            # PAYMENTREQUEST_0_CURRENCYCODE

        }

        url = self.setExpressCheckout(**_params)  # first step
        res = self.get_nvp_response(url)
        # about the response, go to see the doc
        # https://developer.paypal.com/docs/classic/api/merchant/SetExpressCheckout_API_Operation_NVP/

        if res['ACK'][0] == 'Failure':
            raise ParameterValueError("parameters error")
        else:
            token = res['TOKEN'][0]

        data = {
            'token': token,
            'cmd': '_express-checkout'
        }
        # doc https://developer.paypal.com/docs/classic/express-checkout/integration-guide/ECGettingStarted/#id084RM05055Z

        form = self.get_form(data=data, payment=payment)
        # form for redirecting to paypal

        return form
