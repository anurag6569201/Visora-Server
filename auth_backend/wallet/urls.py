# wallet/urls.py
from django.urls import path
from .views import (
    WalletBalanceView,
    RequestWithdrawalView,
    AdminWithdrawalActionView,
    UserWithdrawalHistoryView,
)

app_name = 'wallet'

urlpatterns = [
    # User facing endpoints
    path('balance/', WalletBalanceView.as_view(), name='wallet-balance'),
    path('request-withdrawal/', RequestWithdrawalView.as_view(), name='request-withdrawal'),
    path('history/', UserWithdrawalHistoryView.as_view(), name='withdrawal-history'),

    # Admin action endpoint (consider placing under an /admin/ prefix in your main urls.py)
    path('admin/withdrawal/<uuid:request_uuid>/action/', AdminWithdrawalActionView.as_view(), name='admin-withdrawal-action'),
]