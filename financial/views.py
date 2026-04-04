from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, ListView, TemplateView
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Transaction, Category, Customer, Sale, SaleInstallment, Payment, Transfer, FixedCost
import datetime

class TransactionCreateView(LoginRequiredMixin, CreateView):
    model = Transaction
    template_name = 'financial/transaction_form.html'
    fields = ['type', 'account', 'category', 'amount', 'date', 'payment_method', 'description']
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        
        # When a transaction is created, change the balance of the account
        response = super().form_valid(form)
        
        account = self.object.account
        if self.object.type == 'income':
            account.balance += self.object.amount
        elif self.object.type == 'expense':
            account.balance -= self.object.amount
        # Transfer type logic will be handled later
        account.save()
        
        return response

    def get_initial(self):
        initial = super().get_initial()
        # default to today
        from django.utils import timezone
        initial['date'] = timezone.now().date()
        return initial

class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = 'financial/customer_list.html'
    context_object_name = 'customers'

    def get_queryset(self):
        store = self.request.user.stores.first()
        if store:
            qs = Customer.objects.filter(store=store).prefetch_related('sales')
            q = self.request.GET.get('q')
            if q:
                from django.db.models import Q
                qs = qs.filter(Q(name__icontains=q) | Q(cpf__icontains=q))
            return qs
        return Customer.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = self.request.user.stores.first()
        if store:
            context['total_customers'] = Customer.objects.filter(store=store).count()
            context['customers_clean'] = Customer.objects.filter(store=store, total_debt=0).count()
            context['customers_debt'] = Customer.objects.filter(store=store, total_debt__gt=0).count()
            context['search_query'] = self.request.GET.get('q', '')
        return context

class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    template_name = 'financial/customer_form.html'
    fields = ['name', 'cpf', 'phone', 'address', 'notes']
    success_url = reverse_lazy('customer_list')

    def form_valid(self, form):
        store = self.request.user.stores.first()
        form.instance.store = store
        return super().form_valid(form)

class SaleCreateView(LoginRequiredMixin, CreateView):
    model = Sale
    template_name = 'financial/sale_form.html'
    fields = ['customer', 'total_amount', 'payment_type', 'installments_count', 'sale_date', 'first_due_date', 'notes']
    success_url = reverse_lazy('installment_list')

    def form_valid(self, form):
        form.instance.store = self.request.user.stores.first()
        return super().form_valid(form)

    def get_initial(self):
        initial = super().get_initial()
        from django.utils import timezone
        today = timezone.now().date()
        initial['sale_date'] = today
        initial['first_due_date'] = today
        initial['installments_count'] = 1
        return initial

class InstallmentListView(LoginRequiredMixin, ListView):
    model = SaleInstallment
    template_name = 'financial/installment_list.html'
    context_object_name = 'installments'

    def get_queryset(self):
        store = self.request.user.stores.first()
        if store:
            # PRD: pending installments
            from django.utils import timezone
            import datetime
            limit_date = timezone.now().date() + datetime.timedelta(days=7)
            return SaleInstallment.objects.filter(
                sale__store=store, 
                status__in=['pending', 'overdue'],
                due_date__lte=limit_date
            ).order_by('due_date')
        return SaleInstallment.objects.none()

class PaymentCreateView(LoginRequiredMixin, CreateView):
    model = Payment
    template_name = 'financial/payment_form.html'
    fields = ['amount', 'payment_date', 'payment_method', 'notes']
    
    def get_success_url(self):
        return reverse_lazy('installment_list')

    def form_valid(self, form):
        from django.shortcuts import get_object_or_404
        installment = get_object_or_404(SaleInstallment, id=self.kwargs['pk'])
        form.instance.installment = installment
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.shortcuts import get_object_or_404
        context['installment'] = get_object_or_404(SaleInstallment, id=self.kwargs['pk'])
        return context

    def get_initial(self):
        initial = super().get_initial()
        from django.utils import timezone
        from django.shortcuts import get_object_or_404
        initial['payment_date'] = timezone.now().date()
        installment = get_object_or_404(SaleInstallment, id=self.kwargs['pk'])
        initial['amount'] = installment.amount
        return initial

class DebtorListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = 'financial/debtor_list.html'
    context_object_name = 'debtors'

    def get_queryset(self):
        store = self.request.user.stores.first()
        if store:
            return Customer.objects.filter(store=store, total_debt__gt=0).order_by('-total_debt')
        return Customer.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import Sum
        context['total_owed'] = self.get_queryset().aggregate(Sum('total_debt'))['total_debt__sum'] or 0
        return context

class TransferCreateView(LoginRequiredMixin, CreateView):
    model = Transfer
    template_name = 'financial/transfer_form.html'
    fields = ['from_account', 'to_account', 'amount', 'transfer_type', 'description']
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        
        # update balances
        transfer = self.object
        transfer.from_account.balance -= transfer.amount
        transfer.from_account.save()
        
        transfer.to_account.balance += transfer.amount
        transfer.to_account.save()
        
        return response

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # restrict accounts to current store
        store = self.request.user.stores.first()
        if store:
            from core.models import Account
            form.fields['from_account'].queryset = Account.objects.filter(store=store)
            form.fields['to_account'].queryset = Account.objects.filter(store=store)
        return form

class FixedCostListView(LoginRequiredMixin, ListView):
    model = FixedCost
    template_name = 'financial/fixedcost_list.html'
    context_object_name = 'fixed_costs'

    def get_queryset(self):
        store = self.request.user.stores.first()
        if store:
            from core.models import Account
            accounts = Account.objects.filter(store=store)
            return FixedCost.objects.filter(account__in=accounts)
        return FixedCost.objects.none()

class FixedCostCreateView(LoginRequiredMixin, CreateView):
    model = FixedCost
    template_name = 'financial/fixedcost_form.html'
    fields = ['account', 'category', 'name', 'amount', 'due_day']
    success_url = reverse_lazy('fixedcost_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        store = self.request.user.stores.first()
        if store:
            from core.models import Account
            form.fields['account'].queryset = Account.objects.filter(store=store)
            # Only expense categories
            form.fields['category'].queryset = Category.objects.filter(type='expense')
        return form

# (imports moved to top of file)

MONTH_ABBR = {1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'}
MONTH_FULL = {1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'}

def get_month_range(date_obj):
    start = date_obj.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1) - datetime.timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1) - datetime.timedelta(days=1)
    return start, end

class EvolucaoView(LoginRequiredMixin, TemplateView):
    template_name = 'financial/evolucao.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = self.request.user.stores.first()
        if not store:
            return context
            
        today = timezone.now().date()
        labels, previsto, realizado = [], [], []
        
        for i in range(5, -1, -1):
            target_date = today.replace(day=1) - datetime.timedelta(days=30*i)
            start_date, end_date = get_month_range(target_date)
            
            labels.append(f"{MONTH_ABBR[start_date.month]}/{str(start_date.year)[2:]}")
            
            # Previsto: Installments due in this month
            from collections import defaultdict
            val_previsto = SaleInstallment.objects.filter(
                sale__store=store,
                due_date__range=[start_date, end_date]
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            # Realizado: Income transactions completed within this month
            val_realizado = Transaction.objects.filter(
                account__store=store,
                type='income',
                date__range=[start_date, end_date]
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            previsto.append(float(val_previsto))
            realizado.append(float(val_realizado))
            
        context['labels'] = labels
        context['data_previsto'] = previsto
        context['data_realizado'] = realizado
        
        # Monthly Cards Calculation
        context['mes_atual'] = MONTH_FULL[today.month]
        context['clientes_ativos'] = Customer.objects.filter(store=store, total_debt__gt=0).count()
        context['receita_prevista'] = previsto[-1] if previsto else 0
        
        # Evolução do realizado em percentual
        realizado_atual = realizado[-1] if realizado else 0
        realizado_anterior = realizado[-2] if len(realizado) > 1 else 0
        context['receita_confirmada'] = realizado_atual
        
        if realizado_anterior > 0:
            context['crescimento'] = round(((realizado_atual - realizado_anterior)/realizado_anterior)*100, 1)
        else:
            context['crescimento'] = 100 if realizado_atual > 0 else 0
            
        return context

class ReceitaDistribuicaoView(LoginRequiredMixin, TemplateView):
    template_name = 'financial/receita_distribuicao.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = self.request.user.stores.first()
        if not store:
            return context
            
        today = timezone.now().date()
        labels, realizado = [], []
        
        # Line chart: Last 6 months Income
        for i in range(5, -1, -1):
            target_date = today.replace(day=1) - datetime.timedelta(days=30*i)
            start_date, end_date = get_month_range(target_date)
            labels.append(f"{MONTH_ABBR[start_date.month]}")
            
            val_realizado = Transaction.objects.filter(
                account__store=store, type='income',
                date__range=[start_date, end_date]
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            realizado.append(float(val_realizado))
            
        context['line_labels'] = labels
        context['line_data'] = realizado
        
        # Donut Chart: Expense Distribution by Category for current month
        start_date, end_date = get_month_range(today)
        expenses = Transaction.objects.filter(
            account__store=store, type='expense', 
            date__range=[start_date, end_date]
        ).values('category__name').annotate(total=Sum('amount')).order_by('-total')
        
        pie_labels, pie_data = [], []
        for exp in expenses:
            if exp['category__name']:
                pie_labels.append(exp['category__name'])
                pie_data.append(float(exp['total']))
                
        if not pie_labels:
            pie_labels, pie_data = ['Sem despesas pendentes'], [1]
            
        context['pie_labels'] = pie_labels
        context['pie_data'] = pie_data
        
        # Bottom Summary Cards
        total_in = Transaction.objects.filter(account__store=store, type='income', date__range=[start_date, end_date]).aggregate(Sum('amount'))['amount__sum'] or 0
        total_out = sum(pie_data) if pie_data != [1] else 0
        
        context['lucro_liquido'] = total_in - total_out
        customers_with_sales = Sale.objects.filter(store=store).values('customer').distinct().count()
        context['ticket_medio'] = total_in / customers_with_sales if customers_with_sales > 0 else 0
        context['mes_atual'] = MONTH_FULL[today.month]
        
        return context
