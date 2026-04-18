from django import forms
from .models import Transaction, Customer, Sale, Category
from core.models import Account

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['type', 'account', 'category', 'customer', 'sale', 'amount', 'date', 'payment_method', 'description']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            store = user.stores.first()
            if store:
                self.fields['account'].queryset = Account.objects.filter(store=store)
                self.fields['customer'].queryset = Customer.objects.filter(store=store)
                
                # Initially, if no customer is selected, show no sales or all open sales?
                # Better to show no sales or the one already selected (for update)
                if 'customer' in self.data:
                    try:
                        customer_id = int(self.data.get('customer'))
                        self.fields['sale'].queryset = Sale.objects.filter(customer_id=customer_id).exclude(status='paid')
                    except (ValueError, TypeError):
                        pass
                elif self.instance.pk and self.instance.customer:
                    self.fields['sale'].queryset = Sale.objects.filter(customer=self.instance.customer).exclude(status='paid')
                else:
                    self.fields['sale'].queryset = Sale.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        sale = cleaned_data.get('sale')
        amount = cleaned_data.get('amount')
        t_type = cleaned_data.get('type')

        if sale and t_type == 'income' and amount:
            # Check if amount exceeds remaining
            # Need to exclude current transaction if updating
            already_paid = Transaction.objects.filter(sale=sale, type='income')
            if self.instance.pk:
                already_paid = already_paid.exclude(pk=self.instance.pk)
            
            total_paid = sum(t.amount for t in already_paid)
            remaining = sale.total_amount - total_paid
            
            if amount > remaining:
                raise forms.ValidationError(f"O valor informado (R$ {amount}) é maior que o saldo devedor restante da venda (R$ {remaining}).")
        
        return cleaned_data
