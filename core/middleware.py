from django.shortcuts import redirect
from django.urls import reverse

class SubscriptionMiddleware:
    """
    Middleware que intercepta todas as requisições de usuários logados.
    Se o usuário não possuir assinatura ativa, redireciona para a página de Paywall.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info.lower()

        # Rotas que nunca devem ser bloqueadas para evitar redirect loops e permitir login/pagamento
        public_paths = [
            '/logout/',
            '/login/',
            '/admin/',
            '/paywall/',
            '/checkout/',
            '/payment-success/',
            '/payment-failed/',
            '/api/v1/webhooks/abacatepay/',
        ]

        # Ignorar media e static
        if path.startswith('/static/') or path.startswith('/media/'):
            return self.get_response(request)

        # Se for uma rota que contem algum termo público (ignorando se é exato ou começo)
        is_public = False
        for pp in public_paths:
            if path.startswith(pp) or path in ['/', '/contato', '/sobre']:
                is_public = True
                break

        if request.user.is_authenticated and not is_public:
            # O sistema todo é pago. O usuário precisa de assinatura ativa.
            has_sub = request.user.has_active_subscription
            
            if not has_sub:
                return redirect('paywall') # Nome da view do paywall

        response = self.get_response(request)
        return response
