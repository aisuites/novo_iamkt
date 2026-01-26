"""
Backend de autenticação customizado para permitir login com email
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Backend de autenticação que permite login com email.
    
    Permite que usuários façam login usando email ao invés de username.
    Mantém compatibilidade com autenticação por username também.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Autentica usuário usando email ou username.
        
        Args:
            request: HttpRequest object
            username: Email ou username do usuário
            password: Senha do usuário
            
        Returns:
            User object se autenticação bem-sucedida, None caso contrário
        """
        if username is None or password is None:
            return None
        
        try:
            # Tentar buscar por email primeiro
            user = User.objects.get(email=username)
        except User.DoesNotExist:
            try:
                # Se não encontrar por email, tentar por username
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                # Executar hasher padrão para evitar timing attack
                User().set_password(password)
                return None
        
        # Verificar senha
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None
