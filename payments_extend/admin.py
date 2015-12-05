from django.contrib import admin

from cnpayments.models import CashFlowLog


class CashFlowLogAdmin(admin.ModelAdmin):

    list_display = ('source_ip', 'created_at')


admin.site.register(CashFlowLog, CashFlowLogAdmin)
