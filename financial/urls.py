from django.urls import path
from . import views

urlpatterns = [
    path('transactions/add/', views.TransactionCreateView.as_view(), name='transaction_add'),
    path('customers/', views.CustomerListView.as_view(), name='customer_list'),
    path('customers/add/', views.CustomerCreateView.as_view(), name='customer_add'),
    path('sales/add/', views.SaleCreateView.as_view(), name='sale_add'),
    path('installments/pending/', views.InstallmentListView.as_view(), name='installment_list'),
    path('installments/<int:pk>/pay/', views.PaymentCreateView.as_view(), name='payment_add'),
    path('debtors/', views.DebtorListView.as_view(), name='debtor_list'),
    path('transfers/add/', views.TransferCreateView.as_view(), name='transfer_add'),
    path('fixed-costs/', views.FixedCostListView.as_view(), name='fixedcost_list'),
    path('fixed-costs/add/', views.FixedCostCreateView.as_view(), name='fixedcost_add'),
    path('relatorios/evolucao/', views.EvolucaoView.as_view(), name='relatorio_evolucao'),
    path('relatorios/receita-distribuicao/', views.ReceitaDistribuicaoView.as_view(), name='relatorio_distribuicao'),
]
