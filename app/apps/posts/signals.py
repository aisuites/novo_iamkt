from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Post, PostImage
from apps.core.services import S3Service
from PIL import Image
import boto3
import os
import time
from django.conf import settings


@receiver(pre_save, sender=Post)
def upload_image_to_s3(sender, instance, **kwargs):
    """
    Signal pre_save de Post — DESABILITADO.

    Uploads de imagem agora são tratados via PostImage (ver
    upload_post_image_to_s3 abaixo). Mantido como no-op para preservar a
    fiação do signal; o corpo antigo (upload direto no Post) foi removido.
    """
    return


@receiver(pre_save, sender=PostImage)
def upload_post_image_to_s3(sender, instance, **kwargs):
    """
    Signal executado ANTES de salvar um PostImage.
    Se image_file foi preenchido, faz upload para S3 e atualiza campos relacionados.
    """
    if instance.image_file and instance.image_file.name:
        try:
            # Abrir imagem para obter dimensões
            img = Image.open(instance.image_file)
            instance.width = img.width
            instance.height = img.height

            # Gerar nome do arquivo
            file_name = os.path.basename(instance.image_file.name)
            timestamp = int(time.time() * 1000)

            # Gerar chave S3
            s3_key = f"org-{instance.post.organization.id}/posts/generated/{timestamp}-{file_name}"

            # Upload direto para S3 usando boto3
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )

            # Fazer upload
            instance.image_file.seek(0)
            s3_client.put_object(
                Bucket=settings.AWS_BUCKET_NAME,
                Key=s3_key,
                Body=instance.image_file.read(),
                ContentType=instance.image_file.file.content_type or 'image/jpeg',
                ServerSideEncryption='AES256',
                StorageClass='INTELLIGENT_TIERING',
                Metadata={
                    'original-name': file_name,
                    'organization-id': str(instance.post.organization.id),
                    'category': 'posts',
                    'upload-timestamp': str(timestamp)
                }
            )

            # Atualizar campos do model
            instance.s3_key = s3_key
            instance.s3_url = S3Service.get_public_url(s3_key)

            # Limpar o campo image_file após upload
            instance.image_file = None

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao fazer upload de PostImage para S3: {str(e)}", exc_info=True)
