from django.urls import path
from . import views

urlpatterns = [
    path('', views.LandingPageView.as_view(), name='landing'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('onboarding/', views.onboarding_view, name='onboarding'),
    path('subscription/', views.subscription_view, name='subscription'),
    path('checkout/<str:plan>/', views.create_checkout, name='create_checkout'),
    path('webhook/abacatepay/', views.webhook_abacatepay, name='webhook_abacatepay'),
    path('switch-account/<str:type_code>/', views.switch_account_view, name='switch_account'),
]
