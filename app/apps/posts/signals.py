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
    Signal executado ANTES de salvar um Post.
    Se image_file foi preenchido, faz upload para S3 e atualiza campos relacionados.
    
    DESABILITADO: Agora usamos PostImage para uploads múltiplos.
    """
    # Signal desabilitado - usar PostImage inline no admin
    return
    
    if instance.image_file and instance.image_file.name:
        try:
            # Abrir imagem para obter dimensões
            img = Image.open(instance.image_file)
            instance.image_width = img.width
            instance.image_height = img.height
            
            # Gerar nome do arquivo
            file_name = os.path.basename(instance.image_file.name)
            file_extension = os.path.splitext(file_name)[1]
            timestamp = int(time.time() * 1000)
            
            # Gerar chave S3
            s3_key = f"org-{instance.organization.id}/posts/generated/{timestamp}-{file_name}"
            
            # Upload direto para S3 usando boto3
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            
            # Fazer upload
            instance.image_file.seek(0)  # Voltar ao início do arquivo
            s3_client.put_object(
                Bucket=settings.AWS_BUCKET_NAME,
                Key=s3_key,
                Body=instance.image_file.read(),
                ContentType=instance.image_file.file.content_type or 'image/jpeg',
                ServerSideEncryption='AES256',
                StorageClass='INTELLIGENT_TIERING',
                Metadata={
                    'original-name': file_name,
                    'organization-id': str(instance.organization.id),
                    'category': 'posts',
                    'upload-timestamp': str(timestamp)
                }
            )
            
            # Gerar URL pública
            s3_url = S3Service.get_public_url(s3_key)
            
            # Adicionar ao array de imagens geradas
            if not instance.generated_images:
                instance.generated_images = []
            
            instance.generated_images.append({
                's3_key': s3_key,
                's3_url': s3_url,
                'width': instance.image_width,
                'height': instance.image_height,
                'uploaded_at': timestamp
            })
            
            # Atualizar campos principais (primeira imagem ou última)
            instance.image_s3_key = s3_key
            instance.image_s3_url = s3_url
            instance.has_image = True
            
            # Limpar o campo image_file após upload (não precisamos mais dele)
            instance.image_file = None
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao fazer upload de imagem para S3: {str(e)}", exc_info=True)
            # Não bloquear o salvamento, apenas logar o erro


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
