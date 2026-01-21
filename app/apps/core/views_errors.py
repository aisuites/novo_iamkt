"""
Views para páginas de erro customizadas
"""
from django.shortcuts import render


def custom_404(request, exception=None):
    """
    View customizada para erro 404 (Página não encontrada)
    """
    return render(request, 'errors/404.html', status=404)
