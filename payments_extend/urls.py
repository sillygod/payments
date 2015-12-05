from django.conf.urls import url
from cnpayments.views import direct_to_pay

urlpatterns = [
    url(r'^direct_to_pay/(?P<token>.*)/$', direct_to_pay, name='direct_to_pay'),
]
