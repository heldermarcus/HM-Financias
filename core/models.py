from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    PLAN_CHOICES = (
        ('plus', 'Plus'),
        ('pro', 'Pro'),
    )
    PLAN_STATUS_CHOICES = (
        ('active', 'Ativo'),
        ('cancelled', 'Cancelado'),
        ('suspended', 'Suspenso'),
    )

    phone = models.CharField(max_length=20, blank=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='plus')
    plan_status = models.CharField(max_length=20, choices=PLAN_STATUS_CHOICES, default='active')
    abacatepay_customer_id = models.CharField(max_length=100, null=True, blank=True)
    abacatepay_subscription_id = models.CharField(max_length=100, null=True, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    onboarding_completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username or self.email

class Store(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stores')
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class Account(models.Model):
    ACCOUNT_TYPES = (
        ('PF', 'Pessoa Física'),
        ('PJ', 'Pessoa Jurídica'),
    )
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='accounts')
    account_type = models.CharField(max_length=2, choices=ACCOUNT_TYPES)
    name = models.CharField(max_length=100)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.get_account_type_display()} ({self.store.name})"
