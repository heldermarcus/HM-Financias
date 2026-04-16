from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def require_plus_plan(view_func):
    """
    Exige no mínimo plano Plus (ou Pro).
    Usuários Free são redirecionados para o Paywall de Assinaturas.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
            
        plan = getattr(request.user, 'plan', 'free')
        
        if plan in ['plus', 'pro']:
            return view_func(request, *args, **kwargs)
            
        messages.warning(request, "Esta funcionalidade requer o Plano Plus ou Pro. Faça upgrade para acessar.")
        return redirect('subscription')
    return _wrapped_view

def require_pro_plan(view_func):
    """
    Exige plano Pro.
    Usuários Free ou Plus são redirecionados para o Paywall de Assinaturas.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('account_login')
            
        plan = getattr(request.user, 'plan', 'free')
        
        if plan == 'pro':
            return view_func(request, *args, **kwargs)
            
        messages.warning(request, "Esta funcionalidade exclusiva requer o Plano Pro. Faça upgrade para acessar.")
        return redirect('subscription')
    return _wrapped_view
