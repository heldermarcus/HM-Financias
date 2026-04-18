from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefone")
    cpf = models.CharField(max_length=14, blank=True, verbose_name="CPF")
    
    # Integramos com a nova tabela Subscription (abaixo), porém mantemos referências mínimas se necessário
    # ou podemos usar os related_names.
    abacatepay_customer_id = models.CharField(max_length=100, null=True, blank=True)
    onboarding_completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def has_active_subscription(self):
        from django.utils import timezone
        active_sub = self.subscriptions.filter(
            status='active',
            expiry_date__gt=timezone.now()
        ).first()
        return active_sub is not None

    def __str__(self):
        return self.username or self.email

class Store(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stores')
    name = models.CharField(max_length=200, verbose_name="Nome da Loja")
    cnpj = models.CharField(max_length=18, blank=True, verbose_name="CNPJ")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefone da Loja")
    address = models.TextField(blank=True, verbose_name="Endereço")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class Account(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField(max_length=100)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.store.name})"


class Subscription(models.Model):
    STATUS_CHOICES = (
        ('active', 'Ativa'),
        ('expired', 'Expirada'),
        ('cancelled', 'Cancelada'),
        ('pending', 'Pendente'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    subscription_id = models.CharField(max_length=255, unique=True, verbose_name="ID Assinatura (AbacatePay)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=49.90)
    currency = models.CharField(max_length=3, default='BRL')
    billing_cycle = models.CharField(max_length=20, default='monthly')
    started_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField()
    next_billing_date = models.DateTimeField(null=True, blank=True)
    payment_method = models.CharField(max_length=50, default='abacatepay')
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Sub {self.subscription_id} - {self.user.username} - {self.status}"


class PaymentWebhook(models.Model):
    event_type = models.CharField(max_length=100)
    subscription_id = models.CharField(max_length=255)
    payload = models.JSONField(null=True, blank=True)
    processed = models.BooleanField(default=True)
    processed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Webhook {self.event_type} - {self.subscription_id}"
