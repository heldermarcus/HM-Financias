from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.db import models
from core.models import Store, Account
from financial.models import Category

class LandingPageView(TemplateView):
    template_name = 'landing.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)

@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):
    template_name = 'dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request.user, 'onboarding_completed', False):
            return redirect('onboarding')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        store = self.request.user.stores.first()
        
        if not store:
            return context

        account = store.accounts.first()
        context['account'] = account
        
        from financial.models import Customer, Transaction, Sale, FixedCost, SpendingSettings
        from decimal import Decimal
        from django.db.models import Sum
        from django.utils import timezone
        import datetime
        from financial.views import MONTH_ABBR, MONTH_FULL, get_month_range

        today = timezone.now().date()
        start_date, end_date = get_month_range(today)
        context['mes_atual'] = MONTH_FULL[today.month]

        # Dashboard metrics
        can_spend_today = Decimal('0.00')
        if account:
            fixed_costs_sum = FixedCost.objects.filter(account=account, is_active=True).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
            settings, _ = SpendingSettings.objects.get_or_create(account=account, defaults={'reserve_percentage': 10})
            reserve_factor = settings.reserve_percentage / Decimal('100.00')
            available_after_fixed = account.balance - fixed_costs_sum
            if available_after_fixed > 0:
                reserve_amount = available_after_fixed * reserve_factor
                can_spend_today = available_after_fixed - reserve_amount
        context['can_spend_today'] = max(Decimal('0.00'), can_spend_today)

        context['total_customers'] = Customer.objects.filter(store=store).count()
        context['total_pending'] = Customer.objects.filter(store=store).aggregate(Sum('total_debt'))['total_debt__sum'] or Decimal('0.00')
        context['top_debtors'] = Customer.objects.filter(store=store, total_debt__gt=0).order_by('-total_debt')
        
        # Gráficos
        labels, realizado = [], []
        for i in range(5, -1, -1):
            target_date = today.replace(day=1) - datetime.timedelta(days=30*i)
            m_start, m_end = get_month_range(target_date)
            labels.append(f"{MONTH_ABBR[m_start.month]}")
            val_realizado = Transaction.objects.filter(
                account=account, type='income', date__range=[m_start, m_end]
            ).aggregate(Sum('amount'))['amount__sum'] or 0
            realizado.append(float(val_realizado))
        context['line_labels'] = labels
        context['line_data'] = realizado
        
        expenses = Transaction.objects.filter(
            account=account, type='expense', date__range=[start_date, end_date]
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
        
        total_in = Transaction.objects.filter(account=account, type='income', date__range=[start_date, end_date]).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        total_out = sum(pie_data) if pie_data != [1] else 0
        context['lucro_liquido'] = total_in - Decimal(str(total_out))
        
        customers_with_sales = Sale.objects.filter(store=store).values('customer').distinct().count()
        context['ticket_medio'] = total_in / Decimal(customers_with_sales) if customers_with_sales > 0 else Decimal('0.00')

        return context

@login_required
def onboarding_view(request):
    if request.user.onboarding_completed:
        return redirect('dashboard')

    if request.method == 'POST':
        store_name = request.POST.get('store_name')
        if store_name:
            store, _ = Store.objects.get_or_create(user=request.user, name=store_name)
            
            # Create single account for the store
            Account.objects.get_or_create(store=store, defaults={'name': 'Caixa Loja'})

            # Create default categories if they don't exist
            Category.objects.get_or_create(name='Vendas', type='income', is_default=True)
            Category.objects.get_or_create(name='Fornecedor', type='expense', is_default=True)
            Category.objects.get_or_create(name='Aluguel', type='expense', is_fixed_cost=True, is_default=True)
            Category.objects.get_or_create(name='Luz/Água', type='expense', is_fixed_cost=True, is_default=True)
            Category.objects.get_or_create(name='Funcionário', type='expense', is_fixed_cost=True, is_default=True)

            request.user.onboarding_completed = True
            request.user.save()

    return render(request, 'onboarding.html')

import os
import time
import json
import logging
from django.urls import reverse
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


# ==========================================
#  MÓDULO DE CONFIGURAÇÕES
# ==========================================

@login_required
def settings_view(request):
    store = request.user.stores.first()
    from core.forms import StoreForm, ProfileForm
    from django.contrib import messages

    # Inicializar formulários
    store_form = StoreForm(instance=store) if store else StoreForm()
    profile_form = ProfileForm(instance=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_store':
            store_form = StoreForm(request.POST, instance=store)
            if store_form.is_valid():
                saved_store = store_form.save(commit=False)
                saved_store.user = request.user
                saved_store.save()
                messages.success(request, "Dados da loja salvos com sucesso!")
                return redirect('settings')

        elif action == 'save_profile':
            profile_form = ProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Perfil atualizado com sucesso!")
                return redirect('settings')

        elif action == 'change_password':
            from django.contrib.auth import update_session_auth_hash
            current_pw = request.POST.get('current_password')
            new_pw = request.POST.get('new_password')
            confirm_pw = request.POST.get('confirm_password')

            if not request.user.check_password(current_pw):
                messages.error(request, "Senha atual incorreta.")
            elif new_pw != confirm_pw:
                messages.error(request, "As senhas não coincidem.")
            elif len(new_pw) < 8:
                messages.error(request, "A nova senha deve ter pelo menos 8 caracteres.")
            else:
                request.user.set_password(new_pw)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, "Senha alterada com sucesso!")
            return redirect('settings')

        elif action == 'update_balance':
            new_balance = request.POST.get('new_balance')
            if new_balance is not None and store:
                account = store.accounts.first()
                if account:
                    from decimal import Decimal
                    try:
                        account.balance = Decimal(new_balance.replace(',', '.'))
                        account.save()
                        messages.success(request, "Saldo atualizado com sucesso!")
                    except Exception as e:
                        messages.error(request, "Valor inválido para o saldo.")
            return redirect('settings')

    # Categorias do usuário
    categories = Category.objects.filter(
        models.Q(user=request.user) | models.Q(is_default=True)
    ).order_by('type', 'name')

    context = {
        'store_form': store_form,
        'profile_form': profile_form,
        'categories': categories,
        'store': store,
    }
    return render(request, 'settings.html', context)


@login_required
def category_create_api(request):
    """Criar categoria via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'msg': 'Método não permitido'}, status=405)

    name = request.POST.get('name', '').strip()
    cat_type = request.POST.get('type', 'expense')
    if not name:
        return JsonResponse({'status': 'error', 'msg': 'Nome é obrigatório'})

    cat = Category.objects.create(
        user=request.user,
        name=name,
        type=cat_type,
        is_default=False
    )
    return JsonResponse({
        'status': 'ok',
        'id': cat.id,
        'name': cat.name,
        'type': cat.get_type_display(),
        'type_raw': cat.type
    })


@login_required
def category_edit_api(request, pk):
    """Editar categoria via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'msg': 'Método não permitido'}, status=405)

    try:
        cat = Category.objects.get(pk=pk, user=request.user, is_default=False)
    except Category.DoesNotExist:
        return JsonResponse({'status': 'error', 'msg': 'Categoria não encontrada ou não editável'})

    name = request.POST.get('name', '').strip()
    cat_type = request.POST.get('type', cat.type)
    if not name:
        return JsonResponse({'status': 'error', 'msg': 'Nome é obrigatório'})

    cat.name = name
    cat.type = cat_type
    cat.save()
    return JsonResponse({
        'status': 'ok',
        'id': cat.id,
        'name': cat.name,
        'type': cat.get_type_display(),
        'type_raw': cat.type
    })


@login_required
def category_delete_api(request, pk):
    """Deletar categoria via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'msg': 'Método não permitido'}, status=405)

    try:
        cat = Category.objects.get(pk=pk, user=request.user, is_default=False)
    except Category.DoesNotExist:
        return JsonResponse({'status': 'error', 'msg': 'Categoria não encontrada ou não pode ser deletada'})

    cat.delete()
    return JsonResponse({'status': 'ok'})
