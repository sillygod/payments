from django.db import models
from django.utils import timezone

# Create your models here.


class CashFlowLog(models.Model):

    """record the post message from cash flow merchant

    Basically, we can get some info from django request.META

    HTTP_USER_AGENT
    REMOTE_ADDR
    """

    json_res = models.TextField(default='')
    source_device = models.CharField(max_length=255)
    source_ip = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)
