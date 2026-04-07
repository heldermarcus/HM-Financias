from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, ListView, TemplateView, UpdateView, DeleteView
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Transaction, Category, Customer, Sale, SaleInstallment, Payment, Transfer, FixedCost
import datetime
from django.contrib import messages

class TransactionCreateView(LoginRequiredMixin, CreateView):
    model = Transaction
    template_name = 'financial/transaction_form.html'
    fields = ['type', 'account', 'category', 'amount', 'date', 'payment_method', 'description']
    success_url = reverse_lazy('transaction_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            from core.models import Account
            form.fields['account'].queryset = Account.objects.filter(store=store, account_type=active_type)
        return form

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
        
        active_type = self.request.session.get('active_account_type', 'PJ')
        from financial.models import TransactionHistory
        TransactionHistory.objects.create(
            transaction_reference_id=self.object.pk,
            account_type=active_type,
            field_changed='Criação Inicial',
            old_value='-',
            new_value='Transação criada',
            edited_by=self.request.user
        )
        
        return response

    def get_initial(self):
        initial = super().get_initial()
        # default to today
        from django.utils import timezone
        initial['date'] = timezone.now().date()
        return initial

class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'financial/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 30

    def get_queryset(self):
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        if not store:
            return Transaction.objects.none()
            
        qs = Transaction.objects.filter(account__store=store, account__account_type=active_type).order_by('-date', '-created_at')
        
        t_type = self.request.GET.get('type')
        if t_type:
            qs = qs.filter(type=t_type)
            
        category_id = self.request.GET.get('category')
        if category_id:
            qs = qs.filter(category_id=category_id)
            
        payment_method = self.request.GET.get('payment_method')
        if payment_method:
            qs = qs.filter(payment_method=payment_method)
            
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            qs = qs.filter(date__range=[start_date, end_date])
            
        min_amount = self.request.GET.get('min_amount')
        max_amount = self.request.GET.get('max_amount')
        if min_amount:
            qs = qs.filter(amount__gte=min_amount)
        if max_amount:
            qs = qs.filter(amount__lte=max_amount)
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            context['categories'] = Category.objects.filter(Q(account_type=active_type) | Q(account_type='both'))
        
        context['search_params'] = self.request.GET
        return context

class TransactionUpdateView(LoginRequiredMixin, UpdateView):
    model = Transaction
    template_name = 'financial/transaction_form.html'
    fields = ['type', 'account', 'category', 'amount', 'date', 'payment_method', 'description']
    success_url = reverse_lazy('transaction_list')

    def get_queryset(self):
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        return Transaction.objects.filter(account__store=store, account__account_type=active_type)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            from core.models import Account
            form.fields['account'].queryset = Account.objects.filter(store=store, account_type=active_type)
        return form

    def form_valid(self, form):
        old_obj = Transaction.objects.get(pk=self.object.pk)
        
        old_account = old_obj.account
        if old_obj.type == 'income':
            old_account.balance -= old_obj.amount
        elif old_obj.type == 'expense':
            old_account.balance += old_obj.amount
        old_account.save()

        active_type = self.request.session.get('active_account_type', 'PJ')
        from financial.models import TransactionHistory
        for field in form.changed_data:
            old_val = getattr(old_obj, field)
            new_val = form.cleaned_data[field]
            TransactionHistory.objects.create(
                transaction_reference_id=self.object.pk,
                account_type=active_type,
                field_changed=field,
                old_value=str(old_val),
                new_value=str(new_val),
                edited_by=self.request.user
            )

        response = super().form_valid(form)
        
        new_account = self.object.account
        if self.object.type == 'income':
            new_account.balance += self.object.amount
        elif self.object.type == 'expense':
            new_account.balance -= self.object.amount
        new_account.save()
        
        messages.success(self.request, "Transação atualizada com sucesso.")
        return response

class TransactionDeleteView(LoginRequiredMixin, DeleteView):
    model = Transaction
    template_name = 'financial/transaction_confirm_delete.html'
    success_url = reverse_lazy('transaction_list')

    def get_queryset(self):
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        return Transaction.objects.filter(account__store=store, account__account_type=active_type)

    def form_valid(self, form):
        transaction = self.get_object()
        account = transaction.account
        if transaction.type == 'income':
            account.balance -= transaction.amount
        elif transaction.type == 'expense':
            account.balance += transaction.amount
        account.save()

        active_type = self.request.session.get('active_account_type', 'PJ')
        from financial.models import TransactionHistory
        TransactionHistory.objects.create(
            transaction_reference_id=transaction.pk,
            account_type=active_type,
            field_changed='Status',
            old_value='Ativa',
            new_value='Excluída',
            edited_by=self.request.user
        )

        messages.success(self.request, "Transação excluída com sucesso.")
        return super().form_valid(form)

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def transaction_history_api(request, pk):
    active_type = request.session.get('active_account_type', 'PJ')
    from financial.models import TransactionHistory
    logs = TransactionHistory.objects.filter(
        transaction_reference_id=pk, 
        account_type=active_type
    ).order_by('-edited_at')
    
    data = []
    for log in logs:
        ed_name = log.edited_by.get_full_name() or log.edited_by.email if log.edited_by else 'Sistema'
        data.append({
            'field': log.field_changed,
            'old': log.old_value,
            'new': log.new_value,
            'date': log.edited_at.strftime('%d/%m/%Y %H:%M'),
            'user': ed_name
        })
    return JsonResponse({'status': 'ok', 'logs': data})

class CustomerListView(LoginRequiredMixin, ListView):
    model = Customer
    template_name = 'financial/customer_list.html'
    context_object_name = 'customers'

    def get_queryset(self):
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            qs = Customer.objects.filter(store=store, account_type=active_type).prefetch_related('sales')
            q = self.request.GET.get('q')
            if q:
                from django.db.models import Q
                qs = qs.filter(Q(name__icontains=q) | Q(cpf__icontains=q))
            return qs
        return Customer.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            context['total_customers'] = Customer.objects.filter(store=store, account_type=active_type).count()
            context['customers_clean'] = Customer.objects.filter(store=store, account_type=active_type, total_debt=0).count()
            context['customers_debt'] = Customer.objects.filter(store=store, account_type=active_type, total_debt__gt=0).count()
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
        form.instance.account_type = self.request.session.get('active_account_type', 'PJ')
        return super().form_valid(form)

    def get_initial(self):
        initial = super().get_initial()
        dup_id = self.request.GET.get('duplicate_id')
        if dup_id:
            store = self.request.user.stores.first()
            try:
                base_cust = Customer.objects.get(id=dup_id, store=store)
                initial['name'] = f"{base_cust.name} (Cópia)"
                initial['cpf'] = base_cust.cpf
                initial['phone'] = base_cust.phone
                initial['address'] = base_cust.address
                initial['notes'] = base_cust.notes
            except Customer.DoesNotExist:
                pass
        return initial

class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    template_name = 'financial/customer_form.html'
    fields = ['name', 'cpf', 'phone', 'address', 'notes']
    success_url = reverse_lazy('customer_list')

    def get_queryset(self):
        active_type = self.request.session.get('active_account_type', 'PJ')
        return Customer.objects.filter(store=self.request.user.stores.first(), account_type=active_type)

class CustomerDeleteView(LoginRequiredMixin, DeleteView):
    model = Customer
    template_name = 'financial/customer_confirm_delete.html'
    success_url = reverse_lazy('customer_list')

    def get_queryset(self):
        active_type = self.request.session.get('active_account_type', 'PJ')
        return Customer.objects.filter(store=self.request.user.stores.first(), account_type=active_type)

    def form_valid(self, form):
        customer = self.get_object()
        if customer.sales.count() > 0:
            messages.error(self.request, "Não é possível excluir este cliente pois existem vendas vinculadas. Remova as vendas primeiro.")
            return redirect('customer_list')
            
        messages.success(self.request, "Cliente excluído com sucesso!")
        return super().form_valid(form)

class SaleListView(LoginRequiredMixin, ListView):
    model = Sale
    template_name = 'financial/sale_list.html'
    context_object_name = 'sales'

    def get_queryset(self):
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            qs = Sale.objects.filter(store=store, account_type=active_type).order_by('-sale_date', '-created_at')
            q = self.request.GET.get('q')
            if q:
                from django.db.models import Q
                qs = qs.filter(Q(id__icontains=q) | Q(customer__name__icontains=q))
            statusFilter = self.request.GET.get('status')
            if statusFilter:
                qs = qs.filter(status=statusFilter)
            return qs
        return Sale.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            from django.db.models import Sum
            context['total_sales'] = Sale.objects.filter(store=store, account_type=active_type).count()
            context['total_to_receive'] = Sale.objects.filter(store=store, account_type=active_type).aggregate(Sum('remaining_amount'))['remaining_amount__sum'] or 0
            context['search_query'] = self.request.GET.get('q', '')
        return context

class SaleCreateView(LoginRequiredMixin, CreateView):
    model = Sale
    template_name = 'financial/sale_form.html'
    fields = ['customer', 'total_amount', 'payment_type', 'installments_count', 'sale_date', 'first_due_date', 'notes']
    success_url = reverse_lazy('sale_list')

    def form_valid(self, form):
        form.instance.store = self.request.user.stores.first()
        form.instance.account_type = self.request.session.get('active_account_type', 'PJ')
        return super().form_valid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            form.fields['customer'].queryset = Customer.objects.filter(store=store, account_type=active_type)
        return form

    def get_initial(self):
        initial = super().get_initial()
        from django.utils import timezone
        today = timezone.now().date()
        initial['sale_date'] = today
        initial['first_due_date'] = today
        initial['installments_count'] = 1

        dup_id = self.request.GET.get('duplicate_id')
        if dup_id:
            store = self.request.user.stores.first()
            try:
                base_sale = Sale.objects.get(id=dup_id, store=store)
                initial['customer'] = base_sale.customer
                initial['total_amount'] = base_sale.total_amount
                initial['payment_type'] = base_sale.payment_type
                initial['installments_count'] = base_sale.installments_count
                initial['notes'] = base_sale.notes
            except Sale.DoesNotExist:
                pass

        return initial

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy('sale_list')

class SaleUpdateView(LoginRequiredMixin, UpdateView):
    model = Sale
    template_name = 'financial/sale_form.html'
    fields = ['customer', 'total_amount', 'payment_type', 'installments_count', 'sale_date', 'first_due_date', 'notes']
    success_url = reverse_lazy('sale_list')

    def get_queryset(self):
        active_type = self.request.session.get('active_account_type', 'PJ')
        return Sale.objects.filter(store=self.request.user.stores.first(), account_type=active_type)

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy('sale_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Venda atualizada com sucesso!")
        return response

class SaleDeleteView(LoginRequiredMixin, DeleteView):
    model = Sale
    template_name = 'financial/sale_confirm_delete.html'
    
    def get_success_url(self):
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url:
            return next_url
        return reverse_lazy('sale_list')

    def get_queryset(self):
        active_type = self.request.session.get('active_account_type', 'PJ')
        return Sale.objects.filter(store=self.request.user.stores.first(), account_type=active_type)

    def form_valid(self, form):
        sale = self.get_object()
        if sale.installments.filter(status='paid').exists():
            messages.error(self.request, "Erro: Esta venda já possui parcelas pagas. Desfaça os pagamentos antes de excluir.")
            next_url = self.request.POST.get('next') or self.request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('sale_list')
            
        messages.success(self.request, "Venda excluída com sucesso!")
        return super().form_valid(form)

class InstallmentListView(LoginRequiredMixin, ListView):
    model = SaleInstallment
    template_name = 'financial/installment_list.html'
    context_object_name = 'installments'

    def get_queryset(self):
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            from django.utils import timezone
            import datetime
            limit_date = timezone.now().date() + datetime.timedelta(days=7)
            return SaleInstallment.objects.filter(
                sale__store=store, 
                sale__account_type=active_type,
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
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            return Customer.objects.filter(store=store, account_type=active_type, total_debt__gt=0).order_by('-total_debt')
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
        # restrict accounts to current store and active type
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            from core.models import Account
            form.fields['from_account'].queryset = Account.objects.filter(store=store, account_type=active_type)
            form.fields['to_account'].queryset = Account.objects.filter(store=store, account_type=active_type)
        return form

class FixedCostListView(LoginRequiredMixin, ListView):
    model = FixedCost
    template_name = 'financial/fixedcost_list.html'
    context_object_name = 'fixed_costs'

    def get_queryset(self):
        store = self.request.user.stores.first()
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            from core.models import Account
            accounts = Account.objects.filter(store=store, account_type=active_type)
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
        active_type = self.request.session.get('active_account_type', 'PJ')
        if store:
            from core.models import Account
            form.fields['account'].queryset = Account.objects.filter(store=store, account_type=active_type)
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
        active_type = self.request.session.get('active_account_type', 'PJ')
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
                sale__account_type=active_type,
                due_date__range=[start_date, end_date]
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            
            # Realizado: Income transactions completed within this month
            val_realizado = Transaction.objects.filter(
                account__store=store,
                account__account_type=active_type,
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
        context['clientes_ativos'] = Customer.objects.filter(store=store, account_type=active_type, total_debt__gt=0).count()
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


