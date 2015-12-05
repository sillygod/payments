import binascii
import collections
import json
import hashlib
import copy
from urllib.parse import quote_plus, urlencode

from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect
from django.core.urlresolvers import reverse
from django.utils.translation import pgettext_lazy

from payments import BasicProvider
import requests

from cnpayments.allpay.forms import AllPayForm

from .exceptions import MissingParameter
from .exceptions import ParameterValueError


class AllPayProvider(BasicProvider):

    """
    DEBUG use test server

    ALL_PAY = {
        'MerchantID': '2000132',
        'HashKey': '5294y06JbISpM5x9',
        'HashIV': 'v77hoKGq4kWxNNIS',
        'TransURL': 'http://payment-stage.allpay.com.tw/Cashier/AioCheckOut',
        'QueryURL': 'http://payment-stage.allpay.com.tw/Cashier/QueryTradeInfo',
    }

    restricted by allpay rule, I think all create ... payment should return
    params which is needed by allpay not to generate a url -- differernt from
    alipay way.

    Instantiate BasicProvider with no params are special usage. Normally, this are
    for accessing some util method.

    """

    _action = "http://payment-stage.allpay.com.tw/Cashier/AioCheckOut"

    def __init__(self, MerchantID=None, HashKey=None, HashIV=None, endpoint=_action, **kwargs):
        self._MerchantID = MerchantID
        self._HashKey = HashKey
        self._HashIV = HashIV
        self._action = endpoint

        self._core_params = {
            'MerchantID': self._MerchantID,
            'PaymentType': 'aio',
            'ReturnURL': '',  # payment result notify
            'OrderResultURL': ''  # redirect to this url after pay complete..
        }

        # ReturnURL and OrderResultURL should be update in process_data

        super().__init__(kwargs.get('capture', True))  # Basic only accept a capture keyword arguement

        if not self._capture:
            raise ImproperlyConfigured(
                pgettext_lazy('allpay does not support pre-authorization')
            )

    def _check_params(self, params, requirements):
        """check params which are needed by allpay
        """
        if not all(k in params for k in requirements):
            raise MissingParameter('missing required parameters')

    def _generate_md5_check_value(self, params):
        """generate mac check value with md5
        """
        hash_code = self._encode_param(params)
        # ok.. in python3 string must be encode before hash
        result = hashlib.md5(hash_code.encode('utf-8')).hexdigest().upper()
        return result

    def _encode_param(self, params):
        """encoding param to a string

        sort the param -- dict
        split then with = and connect them with &
        prefix HashKey
        suffix HashIV
        """
        _params = copy.deepcopy(params)

        if 'CheckMacValue' in _params:
            _params.pop('CheckMacValue')

        ordered_params = collections.OrderedDict(
            sorted(_params.items(), key=lambda k: k[0]))

        encoding_lst = []
        encoding_lst.append('HashKey=%s&' % self._HashKey)
        encoding_lst.append(''.join(
            ['{}={}&'.format(key, value) for key,value in ordered_params.items()]))
        encoding_lst.append('HashIV=%s' % self._HashIV)

        safe_characters = '()!*'

        encoding_str = ''.join(encoding_lst)
        encoding_str = quote_plus(str(encoding_str),
            safe=safe_characters).lower()

        return encoding_str

    def verify_macValue(self, **kwargs):
        """we need to check mac value to prevent fake trade

        return true or false according to verify result
        """
        checkMacValue = kwargs.get('CheckMacValue', None)

        if checkMacValue is not None:
            value = self._generate_md5_check_value(kwargs)
            return checkMacValue == value

        else:
            raise MissingParameter('CheckMacValue')

    def create_cvs(self, **kwargs):
        """you can set StoreExpireDate if you want to set an expire time
        """
        params_required = ('ClientRedirectURL', )
        self._check_params(kwargs, params_required)

        fields = self._build_payment_fields('CVS', **kwargs)

        return fields

    def create_mobile_page_pay(self, **kwargs):
        """In doc page 18. it seems that I need to set ChoosePayment to ALL
        when I set DeviceSource to M
        """
        kwargs['DeviceSource'] = 'M'

        ignorePayments = ('Credit', 'WebATM', 'ATM', 'BARCODE', 'TopUpUsed',
            'CVS', 'Tenpay')
        kwargs['IgnorePayment'] = '#'.join(ignorePayments)
        fields = self._build_payment_fields('ALL', **kwargs)

        return fields

    def create_alipay(self, **kwargs):
        """In doc page. 21

        you need to use # to split items if you want to send multi item
        ex.
            you buy goods A and B

            AlipayItemName      A#B
            AlipayItemCounts    1#3
            AlipayItemPrice     20#30
        """
        params_required = ('AlipayItemName', 'AlipayItemCounts',
                           'AlipayItemPrice', 'Email', 'PhoneNo', 'UserName')
        self._check_params(kwargs, params_required)

        fields = self._build_payment_fields('Alipay', **kwargs)

        return fields

    def _build_payment_fields(self, method, **kwargs):
        """simply add ChoosePayment param and check some params needed

        In allpay, different pay method has different fields to post
        here I will check some core param ...

        method should be one of the follwing
         - Credit
         - WebATM
         - ATM
         - CVS
         - BARCODE
         - Alipay
         - Tenpay
         - TopUpUsed
         - ALL

        produce checkmacvalue here..
        """
        params_required = ('MerchantTradeNo', 'MerchantTradeDate',
                           'TotalAmount', 'TradeDesc', 'ItemName')

        self._check_params(kwargs, params_required)
        _params = self._core_params.copy()

        _params.update(kwargs)
        _params.update({'ChoosePayment': method})
        _params.update(
            {'CheckMacValue': self._generate_md5_check_value(_params)})

        return _params

    def get_form(self, payment, data=None):
        """change the payment status according to input data

        receive request data to generate form to post to allpay

        param: payment is Payment model
        waiting to input - means already choose pay method
        """
        if payment.status == 'waiting':
            payment.change_status('input')
        else:
            return None

        form = AllPayForm(data=data, provider=self, payment=payment)
        form.gateway = self._action

        return form

    def get_synchro_notify_url(self, request):
        """use django request to build the absolute uri for facade url
        which accept the response from cash flow merchandise
        """
        url = request.build_absolute_uri(reverse('web_api:cnpayments:allpay_synchro_notify'))
        return url

    def get_asynchro_notify_url(self, request):
        """get asynchronous notify url for allpay
        """
        url = request.build_absolute_uri(reverse('web_api:cnpayments:allpay_asynchro_notify'))
        return url

    def process_data(self, payment, request, **kwargs):
        """confirm the payment, set the status and return the form
        """
        # get datas needed from the payment
        self._core_params.update({
            'ReturnURL': self.get_asynchro_notify_url(request),
            'OrderResultURL': self.get_synchro_notify_url(request)
        })

        # use payment's get_purchased_items type python named tuple..
        # name, quantity, price, currency, sku
        # note...... allpay's price need to be integer
        items = payment.get_purchased_items()

        AlipayItemName = '#'.join([item.name for item in items])
        AlipayItemCounts = '#'.join([str(item.quantity) for item in items])
        AlipayItemPrice = '#'.join([str(int(item.price)) for item in items])

        params = {
            'MerchantTradeNo': payment.tradeNo,
            'MerchantTradeDate': payment.generateTradeDate().strftime('%Y/%m/%d %H:%M:%S'),
            'TotalAmount': int(payment.get_total_price().gross),
            'TradeDesc': 'lbstek',
            'ItemName': AlipayItemName,
            'AlipayItemName': AlipayItemName,
            'AlipayItemCounts': AlipayItemCounts,
            'AlipayItemPrice': AlipayItemPrice,
            'Email': payment.order.get_user_email(),
            'PhoneNo': payment.order.user.phone_number,
            'UserName': payment.billing_full_name(),
        }

        if request.user_agent.is_mobile:
            data = self.create_mobile_page_pay(**params)
        else:
            data = self.create_alipay(**params)

        form = self.get_form(data=data, payment=payment)

        return form
