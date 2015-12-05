import binascii
import collections
import hashlib
import json
import copy
from urllib.parse import quote_plus, urlencode

from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect
from django.utils.translation import pgettext_lazy

from payments import BasicProvider
import requests

from .exceptions import MissingParameter
from .exceptions import ParameterValueError
from .exceptions import TokenAuthorizationError


class AliPayProvider(BasicProvider):

    """the document rule the version must be 1.0
    """

    _version = '1.0'
    _action = 'https://mapi.alipay.com/gateway.do'

    def __init__(self, vendor=None, app_id=None, secret_key=None, endpoint=_action, **kwargs):
        self._vendor = vendor  # partner_id ?
        self._app_id = app_id  # seller_id ?
        self._secret_key = secret_key
        self._action = endpoint

        self._core_params = {
            '_input_charset': 'utf-8',
            'partner': self._vendor,
            'payment_type': '1'  # goods trade
        }

        if self._app_id is not None:
            self._core_params['seller_id'] = seller_id

        super().__init__(**kwargs)
        if not self._capture:
            raise ImproperlyConfigured(
                pgettext_lazy('alipay does not support pre-authorization')
            )

    def _check_params(self, params, requirements):
        """be used for checking params which is needed by
        action method.
        """
        if not all(k in params for k in requirements):
            raise MissingParameter('missing required parameters')

    def _generate_md5_sign(self, param, private_key):
        """implement encrypt by md5 algorithm
        """
        data = self._encode_param(param)
        result = hashlib.md5(data + private_key).hexdigest()
        return result

    def _generate_rsa_sign(self, param, private_key):
        """I have no idea whether the sign_type must be
        rsa or not...
        """
        pass

    def _encode_param(self, param):
        """encode the param before use md5 or RSA algorithm.

        we need to pop key sign to go on encoding process

        ref: https://b.alipay.com/order/techService.htm?src=nsf05/
        """
        _param = copy.deepcopy(param)
        keys_needed_pop = ['sign', 'sign_type']

        for key in keys_needed_pop:
            if key in _param:
                _param.pop(key)

        sorted_items = sorted(_param.items())
        result = '&'.join(['{}={}'.format(key, value) for key, value in sorted_items if value != ''])

        return result

    def _generate_sign(self, sign_type, param):
        """according to the sign_type return the correspond encrypt algorithm
        result
        """
        name = '_generate_{}_sign'.format(sign_type).lower()
        signGenerator = getattr(self, name, None)

        if signGenerator is None:
            raise NotImplementedError(
                "there is no method named {}".format(name)
            )

        return signGenerator(param, self._secret_key)

    def _get_notify_url(self, notify_id):
        """generate the notify url.
        we'll request a check url to verify this is fake or not.
        """
        payload = {'service': 'notify_verify', 'partner': self._app_id, 'notify_id': notify_id}

        return self._action + '?' + urlencode(payload)

    # two step verify... local and remote
    def _check_is_alipay_notify_or_not(self, notify_id):
        """Check whether it is valid or not.
        In page 9.
        """
        result = requests.get(self._get_notify_url(notify_id), headers={'connection': 'close'}).text
        return result == 'true'

    def verify_notify(self, **kwargs):
        """check the sign from alipay whether is consistent or not.
        """
        sign_returned_by_alipay = kwargs.get('sign', None)
        sign_type = kwargs.get('sign_type', None)
        if sign_type is not None:
            sign = self._generate_sign(sign_type, kwargs)
            if sign == sign_returned_by_alipay:
                notify_id = kwargs.get('notify_id')
                return self._check_is_alipay_notify_or_not(notify_id)
            else:
                return False
        else:
            raise MissingParameter('sign_type is missing')


    def _build_service_url(self, service, **kwargs):
        """In Alipay, service means api service. Every of them has its own gateway.
        """
        _params = self._core_params.copy()
        _params['service'] = service
        _params.update(kwargs)

        # use md5 to generate sign if there is not a sign_typ in _params
        sign_type = _params.get('sign_type', None)
        if sign_type is not None:
            _params.update({'sign': self._generate_sign(sign_type, _params)})
        else:
            _params.update({'sign_type': 'MD5', 'sign': self._generate_sign('MD5', _params)})

        url = '{}?{}'.format(self._action, urlencode(_params))

        return url

    def create_direct_pay_by_user_url(self, **kwargs):
        """alipay method -- direct_pay_by_user

        In alipay, give the service name to let it know which kind of
        api you want to request.
        """
        params_required = ('out_trade_no', 'subject')
        self._check_params(kwargs, params_required)

        # In doc page. 13 (price & quantity) can replace total_fee
        if kwargs.get('total_fee', None) is None and \
            (kwargs.get('quantity', None) is None or kwargs.get('price', None) is None):

            raise ParameterValueError(
                pgettext_lazy('alipay create_direct_pay_by_user',
                    'total_fee or (price and quantity) must have one')
            )

        url = self._build_service_url('create_direct_pay_by_user', **kwargs)
        return url

    def get_hidden_fields(self, payment):
        """emmit a request
        """
        pass

    def process_data(self, payment, request):
        """process the receive request
        """
        pass
