"""
Script para testar envio de emails de posts
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/opt/iamkt/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.posts.models import Post
from apps.posts.utils import _notify_image_request_email, _notify_revision_request
from django.contrib.auth import get_user_model

User = get_user_model()

def test_emails():
    print("=" * 60)
    print("TESTE DE EMAILS DE POSTS")
    print("=" * 60)
    
    # Buscar um post existente
    post = Post.objects.select_related('organization', 'user').first()
    
    if not post:
        print("❌ Nenhum post encontrado no banco de dados")
        return
    
    print(f"\n📝 Post selecionado:")
    print(f"   ID: {post.id}")
    print(f"   Título: {post.title or 'Sem título'}")
    print(f"   Organização: {post.organization.name if post.organization else 'Sem organização'}")
    print(f"   Usuário: {post.user.email if post.user else 'Sem usuário'}")
    
    # Criar objeto request fake
    class FakeRequest:
        def __init__(self, user):
            self.user = user
    
    fake_request = FakeRequest(post.user)
    
    # Teste 1: Email de solicitação inicial
    print("\n" + "=" * 60)
    print("TESTE 1: Email de Solicitação Inicial de Imagem")
    print("=" * 60)
    try:
        _notify_image_request_email(post, request=fake_request)
        print("✅ Email de solicitação inicial enviado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao enviar email de solicitação inicial: {e}")
        import traceback
        traceback.print_exc()
    
    # Teste 2: Email de solicitação de alteração
    print("\n" + "=" * 60)
    print("TESTE 2: Email de Solicitação de Alteração")
    print("=" * 60)
    message = """
Por favor, altere a imagem do post com as seguintes modificações:

1. Adicionar mais cores vibrantes
2. Incluir o logotipo da empresa no canto superior direito
3. Ajustar o texto para ficar mais legível

Obrigado!
    """.strip()
    
    try:
        _notify_revision_request(
            post=post,
            message=message,
            user=post.user,
            request=fake_request
        )
        print("✅ Email de solicitação de alteração enviado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao enviar email de alteração: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("TESTE CONCLUÍDO")
    print("=" * 60)
    print("\n📧 Verifique a caixa de entrada de: lusato11@gmail.com")
    print("   - Email 1: 🎨 Nova solicitação de imagem")
    print("   - Email 2: 🔄 Solicitação de alteração de imagem")

if __name__ == '__main__':
    test_emails()
