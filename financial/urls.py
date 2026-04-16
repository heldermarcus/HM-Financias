from django.urls import path
from . import views, views_reports

urlpatterns = [
    path('transacoes/', views.TransactionListView.as_view(), name='transaction_list'),
    path('transacoes/add/', views.TransactionCreateView.as_view(), name='transaction_add'),
    path('transacoes/<int:pk>/edit/', views.TransactionUpdateView.as_view(), name='transaction_edit'),
    path('transacoes/<int:pk>/delete/', views.TransactionDeleteView.as_view(), name='transaction_delete'),
    path('transacoes/<int:pk>/historico/', views.transaction_history_api, name='transaction_history'),
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customers/add/', views.CustomerCreateView.as_view(), name='customer_add'),
    path('customers/<int:pk>/edit/', views.CustomerUpdateView.as_view(), name='customer_edit'),
    path('customers/<int:pk>/delete/', views.CustomerDeleteView.as_view(), name='customer_delete'),
    path('sales/', views.SaleListView.as_view(), name='sale_list'),
    path('sales/add/', views.SaleCreateView.as_view(), name='sale_add'),
    path('sales/<int:pk>/edit/', views.SaleUpdateView.as_view(), name='sale_edit'),
    path('sales/<int:pk>/delete/', views.SaleDeleteView.as_view(), name='sale_delete'),
    path('installments/pending/', views.InstallmentListView.as_view(), name='installment_list'),
    path('installments/<int:pk>/pay/', views.PaymentCreateView.as_view(), name='payment_add'),
    path('debtors/', views.DebtorListView.as_view(), name='debtor_list'),
    path('transfers/add/', views.TransferCreateView.as_view(), name='transfer_add'),
    path('fixed-costs/', views.FixedCostListView.as_view(), name='fixedcost_list'),
    path('fixed-costs/add/', views.FixedCostCreateView.as_view(), name='fixedcost_add'),
    
    # Relatórios
    path('relatorios/mensal/', views_reports.reports_monthly_view, name='reports_monthly'),
    path('relatorios/fluxo-caixa/', views_reports.reports_cash_flow_view, name='reports_cash_flow'),
    path('relatorios/dre/', views_reports.reports_dre_view, name='reports_dre'),
    path('relatorios/exportar/csv/', views_reports.reports_export_csv, name='reports_export_csv'),
]
