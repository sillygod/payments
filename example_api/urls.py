from django.conf.urls import url
from web_api.cnpayments.views import AsynchroNotify
from web_api.cnpayments.views import SynchroNotify
from web_api.cnpayments.views import PaymentProcess
from web_api.cnpayments.views import AllPayAsynchroNotify
from web_api.cnpayments.views import AllPaySynchroNotify
from web_api.cnpayments.views import PayPalSynchroNotify

urlpatterns = [
    url(r'payment_process', PaymentProcess.as_view(), name='payment_process'),
    url(r'alipay_asynchro_notify', AsynchroNotify.as_view(), name='alipay_asynchro_notify'),
    url(r'alipay_synchro_notify', SynchroNotify.as_view(), name='alipay_synchro_notify'),
    url(r'allpay_asynchro_notify', AllPayAsynchroNotify.as_view(), name='allpay_asynchro_notify'),
    url(r'allpay_synchro_notify', AllPaySynchroNotify.as_view(), name='allpay_synchro_notify'),
    url(r'paypal_synchro_notify/(?P<payment_token>.+)/', PayPalSynchroNotify.as_view(), name='paypal_synchro_notify'),
]
