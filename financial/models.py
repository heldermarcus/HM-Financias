from django.db import models
from django.conf import settings
from core.models import User, Store, Account

class Category(models.Model):
    TYPE_CHOICES = (
        ('income', 'Entrada'),
        ('expense', 'Saída'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    is_fixed_cost = models.BooleanField(default=False)
    icon = models.CharField(max_length=50, null=True, blank=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class Customer(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=200, verbose_name="Nome")
    cpf = models.CharField(max_length=14, null=True, blank=True, verbose_name="CPF")
    phone = models.CharField(max_length=20, null=True, blank=True, verbose_name="Telefone")
    address = models.TextField(null=True, blank=True, verbose_name="Endereço")
    total_debt = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_blocked = models.BooleanField(default=False)
    notes = models.TextField(null=True, blank=True, verbose_name="Observações")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Transaction(models.Model):
    TYPE_CHOICES = (
        ('income', 'Entrada'),
        ('expense', 'Saída'),
        ('transfer', 'Transferência'),
    )
    PAYMENT_METHOD_CHOICES = (
        ('pix', 'Pix'),
        ('dinheiro', 'Dinheiro'),
        ('cartao_debito', 'Cartão no Débito'),
        ('cartao_credito', 'Cartão no Crédito'),
        ('check', 'Cheque'),
        ('promissory', 'Promissória'),
        ('boleto', 'Boleto'),
        ('transferencia', 'Transferência Bancária'),
        ('installment', 'Parcelamento'),
    )
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, verbose_name="Tipo")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=500, blank=True)
    date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    sale = models.ForeignKey('Sale', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')

    def __str__(self):
        return f"{self.type} - {self.amount} - {self.date}"

class Sale(models.Model):
    PAYMENT_TYPE_CHOICES = (
        ('pix', 'Pix'),
        ('dinheiro', 'Dinheiro'),
        ('cartao_debito', 'Cartão no Débito'),
        ('cartao_credito', 'Cartão no Crédito'),
        ('check', 'Cheque'),
        ('promissory', 'Promissória'),
        ('boleto', 'Boleto'),
        ('transferencia', 'Transferência Bancária'),
        ('installment', 'Parcelamento'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pendente'),
        ('partial', 'Parcial'),
        ('paid', 'Pago'),
        ('overdue', 'Atrasado'),
    )
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='sales')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales', verbose_name="Cliente")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Total")
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2)
    installments_count = models.IntegerField(default=1, verbose_name="Número de Parcelas")
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, verbose_name="Tipo de Pagamento")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sale_date = models.DateField(verbose_name="Data da Venda")
    first_due_date = models.DateField(verbose_name="Data da Primeira Parcela")
    notes = models.TextField(null=True, blank=True, verbose_name="Observações")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.remaining_amount = self.total_amount - self.paid_amount
        if self.remaining_amount <= 0:
            self.status = 'paid'
        super().save(*args, **kwargs)

class SaleInstallment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pendente'),
        ('paid', 'Pago'),
        ('overdue', 'Atrasado'),
    )
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='installments')
    installment_number = models.IntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Payment(models.Model):
    installment = models.ForeignKey(SaleInstallment, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

class FixedCost(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='fixed_costs')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_day = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class SpendingSettings(models.Model):
    account = models.OneToOneField(Account, on_delete=models.CASCADE)
    reserve_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=10)
    updated_at = models.DateTimeField(auto_now=True)

class Transfer(models.Model):
    TRANSFER_TYPE_CHOICES = (
        ('pro_labore', 'Pró-Labore'),
        ('investment', 'Investimento'),
        ('withdrawal', 'Retirada'),
    )
    from_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transfers_out')
    to_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transfers_in')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transfer_type = models.CharField(max_length=20, choices=TRANSFER_TYPE_CHOICES)
    description = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

# Signals
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from dateutil.relativedelta import relativedelta

@receiver(post_save, sender=Sale)
def create_sale_installments(sender, instance, created, **kwargs):
    if created and instance.installments_count > 0:
        installment_amount = instance.total_amount / instance.installments_count
        for i in range(instance.installments_count):
            due_date = instance.first_due_date + relativedelta(months=i)
            SaleInstallment.objects.create(
                sale=instance,
                installment_number=i + 1,
                amount=installment_amount,
                due_date=due_date,
                status='pending'
            )

@receiver(post_save, sender=Payment)
def update_installment_and_sale(sender, instance, created, **kwargs):
    if created:
        installment = instance.installment
        installment.status = 'paid'
        installment.paid_date = instance.payment_date
        installment.payment_method = instance.payment_method
        installment.save()

        sale = installment.sale
        sale.paid_amount += instance.amount
        sale.save() # This triggers Sale.save() which recalculates remaining_amount and status

@receiver(post_save, sender=Sale)
def update_customer_debt(sender, instance, created, **kwargs):
    customer = instance.customer
    if not customer:
        return
    from django.db.models import Sum
    total = customer.sales.aggregate(Sum('remaining_amount'))['remaining_amount__sum'] or 0
    if hasattr(customer, 'total_debt') and customer.total_debt != total:
        customer.total_debt = total
        customer.save(update_fields=['total_debt'])

@receiver(post_delete, sender=Sale)
def update_customer_debt_on_delete(sender, instance, **kwargs):
    customer = instance.customer
    if not customer:
        return
    from django.db.models import Sum
    total = customer.sales.aggregate(Sum('remaining_amount'))['remaining_amount__sum'] or 0
    if hasattr(customer, 'total_debt') and customer.total_debt != total:
        customer.total_debt = total
        customer.save(update_fields=['total_debt'])

class TransactionHistory(models.Model):
    transaction_reference_id = models.IntegerField(verbose_name="ID da Transação Original")
    field_changed = models.CharField(max_length=100)
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    edited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-edited_at']

    def __str__(self):
        return f"Rev {self.id} (Trans: {self.transaction_reference_id}) - {self.field_changed}"
@receiver(post_save, sender=Transaction)
def update_sale_on_transaction(sender, instance, created, **kwargs):
    if instance.sale and instance.type == 'income':
        # Re-calcula o total pago baseado em todas as transações vinculadas a essa venda
        from django.db.models import Sum
        total_paid = Transaction.objects.filter(sale=instance.sale, type='income').aggregate(Sum('amount'))['amount__sum'] or 0
        instance.sale.paid_amount = total_paid
        instance.sale.save() # Isso já atualiza status e remaining_amount via Sale.save()

@receiver(post_delete, sender=Transaction)
def update_sale_on_transaction_delete(sender, instance, **kwargs):
    if instance.sale and instance.type == 'income':
        from django.db.models import Sum
        total_paid = Transaction.objects.filter(sale=instance.sale, type='income').aggregate(Sum('amount'))['amount__sum'] or 0
        instance.sale.paid_amount = total_paid
        instance.sale.save()
