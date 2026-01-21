"""
Views de teste para visualizar páginas de erro em desenvolvimento
REMOVER EM PRODUÇÃO
"""
from django.shortcuts import render


def test_404(request):
    """
    View para testar página 404 em desenvolvimento (DEBUG=True)
    Acesse: /test-404/
    """
    return render(request, 'errors/404.html', status=404)
