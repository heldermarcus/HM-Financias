from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
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
        if store:
            pf_acc = store.accounts.filter(account_type='PF').first()
            pj_acc = store.accounts.filter(account_type='PJ').first()
            context['pf_account'] = pf_acc
            context['pj_account'] = pj_acc
            
            # F003 / F010: "Quanto posso gastar hoje?"
            can_spend_today = 0
            if pj_acc:
                from financial.models import FixedCost, SpendingSettings
                from django.db.models import Sum
                from decimal import Decimal

                fixed_costs_sum = FixedCost.objects.filter(account=pj_acc, is_active=True).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
                
                settings, _ = SpendingSettings.objects.get_or_create(account=pj_acc, defaults={'reserve_percentage': 10})
                reserve_factor = settings.reserve_percentage / Decimal('100.00')
                
                # Formula: Saldo PJ - (Soma Custos Fixos)
                # O restante sofre desconto da Reserva %
                available_after_fixed = pj_acc.balance - fixed_costs_sum
                
                if available_after_fixed > 0:
                    reserve_amount = available_after_fixed * reserve_factor
                    can_spend_today = available_after_fixed - reserve_amount
                    
            context['can_spend_today'] = max(Decimal('0.00'), can_spend_today)

            from financial.models import Customer
            context['total_customers'] = Customer.objects.filter(store=store).count()
            context['total_pending'] = Customer.objects.filter(store=store).aggregate(Sum('total_debt'))['total_debt__sum'] or Decimal('0.00')

            # F003: Inadimplentes Dashboard list
            context['top_debtors'] = Customer.objects.filter(store=store, total_debt__gt=0).order_by('-total_debt')

        return context

@login_required
def onboarding_view(request):
    if request.user.onboarding_completed:
        return redirect('dashboard')

    if request.method == 'POST':
        store_name = request.POST.get('store_name')
        if store_name:
            store, _ = Store.objects.get_or_create(user=request.user, name=store_name)
            
            # Create PF and PJ accounts
            Account.objects.get_or_create(store=store, account_type='PF', defaults={'name': f'Pessoal {request.user.username}'})
            Account.objects.get_or_create(store=store, account_type='PJ', defaults={'name': 'Caixa Loja'})

            # Create default categories if they don't exist
            Category.objects.get_or_create(name='Vendas', type='income', account_type='PJ', is_default=True)
            Category.objects.get_or_create(name='Salário/Pró-labore', type='income', account_type='PF', is_default=True)
            Category.objects.get_or_create(name='Fornecedor', type='expense', account_type='PJ', is_default=True)
            Category.objects.get_or_create(name='Aluguel', type='expense', account_type='PJ', is_fixed_cost=True, is_default=True)
            Category.objects.get_or_create(name='Luz/Água', type='expense', account_type='PJ', is_fixed_cost=True, is_default=True)
            Category.objects.get_or_create(name='Funcionário', type='expense', account_type='PJ', is_fixed_cost=True, is_default=True)
            Category.objects.get_or_create(name='Pessoal', type='expense', account_type='PF', is_default=True)

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

@login_required
def subscription_view(request):
    return render(request, 'subscription.html')

@login_required
def create_checkout(request, plan):
    """
    Gera uma cobrança no AbacatePay e redireciona o usuário para o checkout.
    
    Fluxo:
    1. Valida o plano (basic/pro)
    2. Monta o payload correto com Product + CustomerMetadata
    3. Chama billing.create() do SDK
    4. Salva o billing_id no usuário
    5. Redireciona para a URL de pagamento
    """
    if plan not in ['basic', 'pro']:
        from django.contrib import messages
        messages.error(request, "Plano inválido.")
        return redirect('subscription')
    
    price = 2900 if plan == 'basic' else 4900
    plan_name = "Plano Básico HMF" if plan == 'basic' else "Plano PRO HMF"
    
    # Proteção anti-duplicata: checar se já existe cobrança recente (últimos 60s)
    last_billing_id = request.user.abacatepay_subscription_id
    cache_key = f"checkout_{request.user.id}_{plan}"
    from django.core.cache import cache
    if cache.get(cache_key):
        logger.warning(f"Checkout duplicado bloqueado para user={request.user.id} plan={plan}")
        from django.contrib import messages
        messages.warning(request, "Aguarde, sua cobrança anterior ainda está sendo processada.")
        return redirect('subscription')
    
    try:
        from abacatepay import AbacatePay
        from abacatepay.products import Product
        from abacatepay.customers import CustomerMetadata
        
        api_key = os.environ.get('ABACATEPAY_API_KEY')
        if not api_key:
            raise ValueError("ABACATEPAY_API_KEY não definida nas variáveis de ambiente.")
        
        abacate = AbacatePay(api_key)
        
        # Build URLs — AbacatePay SDK Pydantic valida formato HttpUrl
        host = request.get_host()
        scheme = request.scheme
        base_url = f"{scheme}://{host}"
        
        # Em localhost, usar um domínio placeholder válido
        # (em produção, base_url será o domínio real)
        if '127.0.0.1' in host or 'localhost' in host:
            base_url = "https://hmfinancas.com.br"
        
        return_url = base_url + reverse('subscription')
        completion_url = base_url + reverse('dashboard') + "?upgraded=true"
        
        # Gerar external_id único para este checkout (anti-duplicata)
        external_id = f"hmf-{request.user.id}-{plan}-{int(time.time())}"
        
        # Montar produto com todos os campos obrigatórios do SDK
        product = Product(
            external_id=external_id,
            name=plan_name,
            description=f"Assinatura {plan_name} - HM de Financias",
            quantity=1,
            price=price  # em centavos
        )
        
        # Montar dados do cliente com todos os campos obrigatórios
        user = request.user
        customer_name = user.get_full_name() or user.username or user.email.split('@')[0]
        customer_email = user.email
        customer_phone = getattr(user, 'phone', '') or '(00) 00000-0000'
        customer_taxid = '000.000.000-00'  # placeholder — em produção, coletar CPF real
        
        customer_data = CustomerMetadata(
            name=customer_name,
            email=customer_email,
            cellphone=customer_phone,
            tax_id=customer_taxid,
        )
        
        logger.info(
            f"Preparando checkout AbacatePay | user={user.id} | plan={plan} | "
            f"price={price} | external_id={external_id}"
        )
        
        # Bug 422: A API rejeita customerId=null. 
        # Solução: Criar cliente primeiro e usar o ID retornado.
        customer_id = user.abacatepay_customer_id
        if not customer_id:
            logger.info(f"Criando novo cliente no AbacatePay para user={user.id}")
            created_customer = abacate.customers.create(customer_data)
            customer_id = created_customer.id
            user.abacatepay_customer_id = customer_id
            user.save(update_fields=['abacatepay_customer_id'])
        
        # Marcar anti-duplicata (expira em 60s)
        cache.set(cache_key, True, 60)
        
        # Chamar SDK usando apenas o customer_id (evita enviar customer: {} ou null)
        billing = abacate.billing.create(
            frequency="ONE_TIME",
            methods=["PIX"],
            products=[product],
            customer_id=customer_id,
            return_url=return_url,
            completion_url=completion_url,
        )
        
        # billing é instância de Billing com .id e .url
        logger.info(
            f"Billing criado com sucesso | billing_id={billing.id} | "
            f"url={billing.url} | user={user.id}"
        )
        
        # Salvar billing_id no usuário
        user.abacatepay_subscription_id = billing.id
        user.save(update_fields=['abacatepay_subscription_id'])
        
        # Redirecionar para checkout do AbacatePay
        return redirect(billing.url)
        
    except ValueError as e:
        logger.error(f"Erro de configuração AbacatePay: {e}")
        from django.contrib import messages
        messages.error(request, f"Erro de configuração: {e}")
        return redirect('subscription')
    
    except Exception as e:
        # Tentar extrair response body se for erro da API
        error_detail = str(e)
        if hasattr(e, 'response'):
            try:
                resp = e.response
                error_detail = f"HTTP {resp.status_code} | Body: {resp.text}"
            except Exception:
                pass
        
        logger.exception(
            f"Erro ao criar billing AbacatePay | user={request.user.id} | "
            f"plan={plan} | error_type={type(e).__name__} | detail={error_detail}"
        )
        from django.contrib import messages
        messages.error(request, f"Erro ao gerar cobrança: {error_detail}")
        return redirect('subscription')

@csrf_exempt
def webhook_abacatepay(request):
    """
    Recebe notificações de pagamento do AbacatePay.
    Eventos tratados: billing.paid
    """
    if request.method != 'POST':
        return HttpResponse(status=405)
        
    try:
        payload = json.loads(request.body)
        event = payload.get('event')
        data = payload.get('data', {})
        
        logger.info(f"Webhook AbacatePay recebido | event={event} | data_keys={list(data.keys())}")
        
        if event == 'billing.paid':
            billing_id = data.get('id')
            amount = data.get('amount', 0)
            
            # Encontrar usuário pelo billing_id salvo
            from core.models import User
            user = User.objects.filter(abacatepay_subscription_id=billing_id).first()
            
            if not user:
                # Fallback: buscar pelo email do customer
                customer_email = data.get('customer', {}).get('email')
                if customer_email:
                    user = User.objects.filter(email=customer_email).first()
            
            if user:
                user.plan = 'pro' if amount > 3000 else 'basic'
                user.plan_status = 'active'
                user.save(update_fields=['plan', 'plan_status'])
                logger.info(
                    f"Assinatura ativada via webhook | user={user.id} | "
                    f"plan={user.plan} | billing_id={billing_id}"
                )
            else:
                logger.warning(
                    f"Webhook billing.paid: usuário não encontrado | "
                    f"billing_id={billing_id}"
                )
                
        return HttpResponse(status=200)
        
    except json.JSONDecodeError:
        logger.error("Webhook AbacatePay: payload JSON inválido")
        return HttpResponse(status=400)
    except Exception as e:
        logger.exception(f"Webhook AbacatePay erro: {e}")
        return HttpResponse(status=400)
