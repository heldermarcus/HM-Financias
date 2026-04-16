from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum
from django.db.models.functions import TruncMonth, TruncDay
from datetime import timedelta
import calendar
import csv
from django.http import HttpResponse

from core.decorators import require_plus_plan, require_pro_plan
from financial.models import Transaction, Sale, Category

def get_base_context(request, title):
    return {
        'page_title': title,
        'current_month': timezone.now().strftime('%B/%Y').capitalize(),
    }

@require_plus_plan
def reports_monthly_view(request):
    """Relatório Mensal - Vendas vs Gastos com gráficos e detalhamento"""
    now = timezone.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    _, last_day_num = calendar.monthrange(now.year, now.month)
    last_day = now.replace(day=last_day_num, hour=23, minute=59, second=59)

    # Pegar as vendas do mês (pela data da venda `sale_date`)
    sales_total = Sale.objects.filter(
        store__user=request.user,
        sale_date__gte=first_day.date(),
        sale_date__lte=last_day.date()
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    # Pegar despesas do mês (`date`)
    expenses_total = Transaction.objects.filter(
        account__store__user=request.user,
        type='expense',
        date__gte=first_day.date(),
        date__lte=last_day.date()
    ).aggregate(total=Sum('amount'))['total'] or 0

    net_result = sales_total - expenses_total
    margin = (net_result / sales_total * 100) if sales_total > 0 else 0

    # Detalhamento por categoria
    expenses_by_cat = Transaction.objects.filter(
        account__store__user=request.user,
        type='expense',
        date__gte=first_day.date(),
        date__lte=last_day.date()
    ).values('category__name').annotate(total=Sum('amount')).order_by('-total')

    context = get_base_context(request, "Relatório Mensal")
    context.update({
        'sales_total': sales_total,
        'expenses_total': expenses_total,
        'net_result': net_result,
        'margin': round(margin, 2),
        'expenses_by_cat': expenses_by_cat,
    })
    return render(request, 'financial/reports_monthly.html', context)


@require_plus_plan
def reports_cash_flow_view(request):
    """Fluxo de Caixa - Visão dos últimos 6 meses"""
    now = timezone.now()
    six_months_ago = now - timedelta(days=180)
    first_day_six_months_ago = six_months_ago.replace(day=1)

    # Entradas por mês (transações income + pagamentos de vendas)
    # Por simplicidade, vamos usar as transações 'income' apenas como métrica de caixa
    incomes = Transaction.objects.filter(
        account__store__user=request.user,
        type='income',
        date__gte=first_day_six_months_ago.date()
    ).annotate(month=TruncMonth('date')).values('month').annotate(total=Sum('amount')).order_by('month')

    expenses = Transaction.objects.filter(
        account__store__user=request.user,
        type='expense',
        date__gte=first_day_six_months_ago.date()
    ).annotate(month=TruncMonth('date')).values('month').annotate(total=Sum('amount')).order_by('month')

    months_data = {}
    
    # Process inputs
    for inc in incomes:
        m = inc['month'].strftime('%m/%Y')
        if m not in months_data:
            months_data[m] = {'in': 0, 'out': 0, 'balance': 0}
        months_data[m]['in'] += float(inc['total'] or 0)

    for exp in expenses:
        m = exp['month'].strftime('%m/%Y')
        if m not in months_data:
            months_data[m] = {'in': 0, 'out': 0, 'balance': 0}
        months_data[m]['out'] += float(exp['total'] or 0)

    for m in months_data:
        months_data[m]['balance'] = months_data[m]['in'] - months_data[m]['out']

    context = get_base_context(request, "Fluxo de Caixa")
    context['months_data'] = months_data
    return render(request, 'financial/reports_cash_flow.html', context)


@require_pro_plan
def reports_dre_view(request):
    """DRE Simplificado - Receitas, Custos, Lucro Bruto, OP e Líquido"""
    now = timezone.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
    
    # Receita Bruta = Vendas do período
    sales = Sale.objects.filter(
        store__user=request.user,
        sale_date__gte=first_day
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    # Despesas = Tudo classificado como expense
    # Para fim didático da DRE, vamos separar "Custo do Produto" x "Despesa Operacional"
    # Na ausência de um campo explícito de CPV, vamos classificar categorias que tenham a palavra "estoque", "fornecedor" ou "produto" como CPV.
    cpv_amount = Transaction.objects.filter(
        account__store__user=request.user,
        type='expense',
        date__gte=first_day,
        category__name__icontains='fornecedor'
    ).aggregate(total=Sum('amount'))['total'] or 0

    op_expenses = Transaction.objects.filter(
        account__store__user=request.user,
        type='expense',
        date__gte=first_day
    ).exclude(category__name__icontains='fornecedor').aggregate(total=Sum('amount'))['total'] or 0

    lucro_bruto = sales - cpv_amount
    lucro_operacional = lucro_bruto - op_expenses
    lucro_liquido = lucro_operacional # S/ impostos ou outras despesas por enquanto

    context = get_base_context(request, "DRE Simplificado")
    context.update({
        'receita_bruta': sales,
        'cpv': cpv_amount,
        'lucro_bruto': lucro_bruto,
        'margem_bruta': (lucro_bruto / sales * 100) if sales > 0 else 0,
        'despesas_op': op_expenses,
        'lucro_operacional': lucro_operacional,
        'lucro_liquido': lucro_liquido,
        'margem_liquida': (lucro_liquido / sales * 100) if sales > 0 else 0,
    })
    return render(request, 'financial/reports_dre.html', context)


@require_pro_plan
def reports_export_csv(request):
    """Exportar relatórios em CSV"""
    response = HttpResponse(
        content_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename="export_mensal.csv"'},
    )
    
    writer = csv.writer(response)
    writer.writerow(['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor (R$)'])

    # Query despesas
    now = timezone.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
    
    transactions = Transaction.objects.filter(
        account__store__user=request.user,
        date__gte=first_day
    ).order_by('-date')

    for t in transactions:
        writer.writerow([
            t.date.strftime('%d/%m/%Y'),
            t.get_type_display(),
            t.category.name if t.category else 'Sem Categoria',
            t.description,
            t.amount
        ])

    return response
