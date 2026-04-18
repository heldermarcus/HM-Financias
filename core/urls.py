from django.urls import path
from . import views

urlpatterns = [
    path('', views.LandingPageView.as_view(), name='landing'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('onboarding/', views.onboarding_view, name='onboarding'),
    path('paywall/', views.paywall_view, name='paywall'),
    path('checkout/', views.create_checkout, name='create_checkout'),
    path('payment-success/', views.PaymentSuccessView.as_view(), name='payment_success'),
    path('payment-failed/', views.PaymentFailedView.as_view(), name='payment_failed'),
    path('api/v1/webhooks/abacatepay/', views.webhook_abacatepay, name='webhook_abacatepay'),
    # Configurações
    path('settings/', views.settings_view, name='settings'),
    path('settings/category/add/', views.category_create_api, name='category_create'),
    path('settings/category/<int:pk>/edit/', views.category_edit_api, name='category_edit'),
    path('settings/category/<int:pk>/delete/', views.category_delete_api, name='category_delete'),
]
