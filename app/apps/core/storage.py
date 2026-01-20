"""
Storage backends customizados para diferentes tipos de arquivos no AWS S3.

Este módulo define classes de storage que separam vídeos (privados) de thumbnails (públicos),
permitindo controle granular de acesso via signed URLs.
"""
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class VideoAvatarStorage(S3Boto3Storage):
    """
    Storage PRIVADO para vídeos avatar no S3 com signed URLs.
    
    Características:
    - Vídeos são privados (não acessíveis diretamente)
    - URLs são assinadas e expiram em 1 hora
    - Estrutura de pastas: videos/avatar/2025/01/15/video_123.mp4
    
    Uso:
        video_file = models.FileField(
            upload_to='%Y/%m/%d/',
            storage=VideoAvatarStorage()
        )
    """
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    location = 'videos/avatar'
    file_overwrite = False
    default_acl = None
    querystring_auth = True
    querystring_expire = 3600  # 1 hora


class VideoThumbnailStorage(S3Boto3Storage):
    """
    Storage PÚBLICO para thumbnails de vídeos.
    
    Características:
    - Thumbnails são públicos (acesso direto via URL)
    - Não requerem signed URLs
    - Estrutura de pastas: videos/thumbnails/2025/01/15/thumb_123.jpg
    
    Uso:
        thumbnail = models.ImageField(
            upload_to='%Y/%m/%d/',
            storage=VideoThumbnailStorage()
        )
    """
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    location = 'videos/thumbnails'
    file_overwrite = False
    default_acl = None
    querystring_auth = False


class AvatarImageStorage(S3Boto3Storage):
    """
    Storage PÚBLICO para imagens de avatar enviadas pelos clientes.
    
    Características:
    - Imagens são públicas (usadas em thumbnails e previews)
    - Não contém informações sensíveis
    - Estrutura de pastas: videos/avatars/2025/01/15/avatar_123.jpg
    
    Uso:
        avatar_image = models.ImageField(
            upload_to='%Y/%m/%d/',
            storage=AvatarImageStorage()
        )
    """
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    location = 'videos/avatars'
    file_overwrite = False
    default_acl = None
    querystring_auth = False
