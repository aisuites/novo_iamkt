"""
IAMKT - AWS S3 Utilities
Funções para upload, download e gerenciamento de arquivos no S3
"""
import boto3
import logging
from datetime import timedelta
from django.conf import settings
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class S3Manager:
    """Gerenciador de operações com AWS S3"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        self.bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    def upload_file(self, file_obj, s3_key, content_type=None, metadata=None):
        """
        Upload de arquivo para S3
        
        Args:
            file_obj: Arquivo ou BytesIO
            s3_key: Caminho/chave no S3 (ex: 'knowledge/fonts/font.ttf')
            content_type: MIME type do arquivo
            metadata: Dict com metadados adicionais
        
        Returns:
            dict: {'success': bool, 's3_key': str, 'url': str, 'error': str}
        """
        try:
            extra_args = {}
            
            if content_type:
                extra_args['ContentType'] = content_type
            
            if metadata:
                extra_args['Metadata'] = metadata
            
            # ACL privado por padrão
            extra_args['ACL'] = 'private'
            
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs=extra_args
            )
            
            logger.info(f"Arquivo enviado para S3: {s3_key}")
            
            return {
                'success': True,
                's3_key': s3_key,
                'url': f"s3://{self.bucket_name}/{s3_key}",
                'error': None
            }
            
        except ClientError as e:
            logger.error(f"Erro ao enviar arquivo para S3: {e}")
            return {
                'success': False,
                's3_key': s3_key,
                'url': None,
                'error': str(e)
            }
    
    def generate_signed_url(self, s3_key, expiration=3600):
        """
        Gera URL assinada para acesso temporário ao arquivo
        
        Args:
            s3_key: Chave do arquivo no S3
            expiration: Tempo de expiração em segundos (padrão: 1 hora)
        
        Returns:
            str: URL assinada ou None em caso de erro
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            
            logger.info(f"URL assinada gerada para: {s3_key}")
            return url
            
        except ClientError as e:
            logger.error(f"Erro ao gerar URL assinada: {e}")
            return None
    
    def delete_file(self, s3_key):
        """
        Remove arquivo do S3
        
        Args:
            s3_key: Chave do arquivo no S3
        
        Returns:
            bool: True se removido com sucesso
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            
            logger.info(f"Arquivo removido do S3: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Erro ao remover arquivo do S3: {e}")
            return False
    
    def file_exists(self, s3_key):
        """
        Verifica se arquivo existe no S3
        
        Args:
            s3_key: Chave do arquivo no S3
        
        Returns:
            bool: True se existe
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return True
            
        except ClientError:
            return False
    
    def get_file_size(self, s3_key):
        """
        Retorna tamanho do arquivo em bytes
        
        Args:
            s3_key: Chave do arquivo no S3
        
        Returns:
            int: Tamanho em bytes ou None
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return response['ContentLength']
            
        except ClientError as e:
            logger.error(f"Erro ao obter tamanho do arquivo: {e}")
            return None
    
    def list_files(self, prefix='', max_keys=1000):
        """
        Lista arquivos no S3 com determinado prefixo
        
        Args:
            prefix: Prefixo para filtrar (ex: 'knowledge/logos/')
            max_keys: Número máximo de resultados
        
        Returns:
            list: Lista de chaves S3
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            if 'Contents' not in response:
                return []
            
            return [obj['Key'] for obj in response['Contents']]
            
        except ClientError as e:
            logger.error(f"Erro ao listar arquivos: {e}")
            return []


# Instância global
s3_manager = S3Manager()


def upload_to_s3(file_obj, s3_key, content_type=None, metadata=None):
    """Atalho para upload de arquivo"""
    return s3_manager.upload_file(file_obj, s3_key, content_type, metadata)


def get_signed_url(s3_key, expiration=3600):
    """Atalho para gerar URL assinada"""
    return s3_manager.generate_signed_url(s3_key, expiration)


def delete_from_s3(s3_key):
    """Atalho para deletar arquivo"""
    return s3_manager.delete_file(s3_key)
