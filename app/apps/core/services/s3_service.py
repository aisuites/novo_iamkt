"""
S3 Service - Upload seguro de arquivos usando Presigned URLs
Versão 2.0 - Seguindo guia Django S3 completo
Features:
- Templates flexíveis de nomenclatura
- Validação separada (SOLID)
- StorageClass INTELLIGENT_TIERING
- Método get_public_url() (nome mais claro)
"""

import boto3
import secrets
import time
import re
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from apps.core.utils.file_validators import FileValidator


class S3Service:
    """
    Service centralizado para operações S3 com Presigned URLs
    Versão 2.0 - Seguindo padrão do guia Django S3
    """
    
    # ============================================
    # TEMPLATES DE NOMENCLATURA (FLEXÍVEIS)
    # ============================================
    
    DEFAULT_TEMPLATES = {
        'logos': 'org-{org_id}/{category}/{timestamp}-{random}-{name}.{ext}',
        'references': 'org-{org_id}/{category}/{timestamp}-{random}-{name}.{ext}',
        'fonts': 'org-{org_id}/{category}/{name}.{ext}',  # Sem timestamp para fontes
        'documents': 'org-{org_id}/{category}/{date}/{timestamp}-{random}.{ext}',
        'posts': 'org-{org_id}/posts/{date}/{random}.{ext}',
        # Brandguides: cada upload vai para uma "pasta" propria identificada por timestamp
        # Permite multiplas versoes do brandguide e organiza as paginas geradas
        'brandguides': 'org-{org_id}/brandguides/{timestamp}/original.{ext}',
    }
    
    # Tempo de expiração das URLs (segundos)
    PRESIGNED_URL_EXPIRATION = 300  # 5 minutos para upload
    DOWNLOAD_URL_EXPIRATION = 3600  # 1 hora para download/preview
    
    _s3_client = None  # Cache do cliente S3
    
    # ============================================
    # MÉTODOS PRINCIPAIS
    # ============================================
    
    @classmethod
    def _get_s3_client(cls):
        """Retorna cliente S3 configurado (cached)"""
        if cls._s3_client is None:
            config = Config(
                region_name=settings.AWS_REGION,
                signature_version='s3v4',
                retries={'max_attempts': 3, 'mode': 'standard'}
            )
            
            cls._s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                config=config
            )
        
        return cls._s3_client
    
    @classmethod
    def generate_secure_filename(
        cls,
        original_name: str,
        file_type: str,
        category: str,
        organization_id: int,
        template: Optional[str] = None,
        custom_data: Optional[Dict] = None
    ) -> str:
        """
        Gera nome único e seguro para arquivo usando template flexível
        
        Args:
            original_name: Nome original do arquivo
            file_type: MIME type
            category: Categoria (logos, references, fonts, documents, posts)
            organization_id: ID da organização
            template: Template customizado (opcional)
            custom_data: Dados customizados para o template (opcional)
            
        Variáveis Disponíveis:
            {org_id}    - ID da organização
            {category}  - Categoria do arquivo
            {timestamp} - Timestamp em milissegundos
            {random}    - String aleatória (32 chars)
            {ext}       - Extensão do arquivo
            {name}      - Nome sanitizado do arquivo
            {date}      - Data YYYYMMDD
            {datetime}  - Data e hora YYYYMMDDHHmmss
            + Qualquer chave em custom_data
            
        Examples:
            # Logo padrão
            generate_secure_filename('logo.png', 'image/png', 'logos', 1)
            # → org-1/logos/1706356800000-abc123def456-logo.png
            
            # Fonte com nome específico
            generate_secure_filename(
                'Roboto.ttf', 'font/ttf', 'fonts', 1,
                template='org-{org_id}/fontes/{font_name}_{variant}.{ext}',
                custom_data={'font_name': 'Roboto', 'variant': 'Bold'}
            )
            # → org-1/fontes/Roboto_Bold.ttf
        
        Returns:
            Caminho completo do arquivo no S3
        """
        # Obter extensão
        extension = FileValidator.get_extension(file_type, category)
        if not extension:
            extension = 'bin'
        
        # Sanitizar nome original
        sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', original_name)
        name_without_ext = sanitized.rsplit('.', 1)[0][:50]
        
        # Preparar variáveis disponíveis
        now = datetime.now()
        variables = {
            'org_id': organization_id,
            'category': category,
            'timestamp': int(time.time() * 1000),
            'random': secrets.token_hex(16),  # 32 chars
            'ext': extension,
            'name': name_without_ext,
            'date': now.strftime('%Y%m%d'),
            'datetime': now.strftime('%Y%m%d%H%M%S'),
        }
        
        # Adicionar variáveis customizadas
        if custom_data:
            variables.update(custom_data)
        
        # Usar template customizado ou padrão da categoria
        if template is None:
            template = cls.DEFAULT_TEMPLATES.get(
                category,
                'org-{org_id}/{category}/{timestamp}-{random}-{name}.{ext}'
            )
        
        # Substituir variáveis no template
        try:
            filename = template.format(**variables)
        except KeyError as e:
            raise ValueError(
                f"Variável '{e.args[0]}' não encontrada. "
                f"Disponíveis: {', '.join(variables.keys())}"
            )
        
        # Validar caminho gerado (segurança)
        if '..' in filename or '//' in filename:
            raise ValueError("Path gerado contém caracteres suspeitos")
        
        return filename
    
    @classmethod
    def generate_presigned_upload_url(
        cls,
        file_name: str,
        file_type: str,
        file_size: int,
        category: str,
        organization_id: int,
        template: Optional[str] = None,
        custom_data: Optional[Dict] = None
    ) -> Dict[str, any]:
        """
        Gera Presigned URL para upload de arquivo
        
        Args:
            file_name: Nome do arquivo
            file_type: MIME type
            file_size: Tamanho em bytes
            category: Categoria (logos, references, fonts, documents, posts)
            organization_id: ID da organização
            template: Template customizado para nomenclatura (opcional)
            custom_data: Dados customizados para template (opcional)
            
        Returns:
            {
                'upload_url': str,  # URL para fazer PUT
                's3_key': str,      # Chave do arquivo no S3
                'expires_in': int   # Segundos até expirar
            }
            
        Raises:
            ValueError: Se validação falhar
            Exception: Se erro ao gerar URL
        """
        # Validar arquivo usando FileValidator (SOLID)
        is_valid, error_msg = FileValidator.validate_file(
            file_type, file_size, category
        )
        if not is_valid:
            raise ValueError(error_msg)
        
        # Gerar nome seguro com template
        s3_key = cls.generate_secure_filename(
            original_name=file_name,
            file_type=file_type,
            category=category,
            organization_id=organization_id,
            template=template,
            custom_data=custom_data
        )
        
        # Obter cliente S3
        s3_client = cls._get_s3_client()

        # CRITICAL: timestamp precisa ser o MESMO na assinatura e nos headers enviados.
        # Duas chamadas separadas a time.time() podiam divergir em 1s e quebrar a assinatura (403).
        upload_timestamp = str(int(time.time()))

        try:
            # Gerar Presigned URL com INTELLIGENT_TIERING
            presigned_url = s3_client.generate_presigned_url(
                ClientMethod='put_object',
                Params={
                    'Bucket': settings.AWS_BUCKET_NAME,
                    'Key': s3_key,
                    'ContentType': file_type,
                    'ServerSideEncryption': 'AES256',
                    'StorageClass': 'INTELLIGENT_TIERING',  # ← Economia de custos
                    'Metadata': {
                        'original-name': file_name,
                        'organization-id': str(organization_id),
                        'category': category,
                        'upload-timestamp': upload_timestamp
                    }
                },
                ExpiresIn=cls.PRESIGNED_URL_EXPIRATION,
                HttpMethod='PUT'
            )

            # Headers que devem ser enviados no PUT request
            signed_headers = {
                'x-amz-server-side-encryption': 'AES256',
                'x-amz-storage-class': 'INTELLIGENT_TIERING',
                'x-amz-meta-original-name': file_name,
                'x-amz-meta-organization-id': str(organization_id),
                'x-amz-meta-category': category,
                'x-amz-meta-upload-timestamp': upload_timestamp
            }
            
            return {
                'upload_url': presigned_url,
                's3_key': s3_key,
                'expires_in': cls.PRESIGNED_URL_EXPIRATION,
                'signed_headers': signed_headers
            }
            
        except ClientError as e:
            raise Exception(f"Erro AWS ao gerar URL: {str(e)}")
        except Exception as e:
            raise Exception(f"Erro ao gerar URL de upload: {str(e)}")
    
    @classmethod
    def generate_presigned_download_url(
        cls,
        s3_key: str,
        expires_in: Optional[int] = None,
        bucket: Optional[str] = None
    ) -> str:
        """
        Gera Presigned URL para download/visualização
        
        Args:
            s3_key: Chave do arquivo no S3
            expires_in: Tempo de expiração em segundos (padrão: 1 hora)
            bucket: Nome do bucket (opcional, usa AWS_BUCKET_NAME se não fornecido)
            
        Returns:
            URL temporária para download
            
        Raises:
            Exception: Se erro ao gerar URL
        """
        if expires_in is None:
            expires_in = cls.DOWNLOAD_URL_EXPIRATION
        
        if bucket is None:
            bucket = settings.AWS_BUCKET_NAME
        
        s3_client = cls._get_s3_client()
        
        try:
            return s3_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': bucket,
                    'Key': s3_key
                },
                ExpiresIn=expires_in,
                HttpMethod='GET'
            )
        except ClientError as e:
            raise Exception(f"Erro AWS ao gerar URL de download: {str(e)}")
    
    @classmethod
    def delete_file(cls, s3_key: str) -> bool:
        """
        Deleta arquivo do S3

        Args:
            s3_key: Chave do arquivo no S3

        Returns:
            True se deletado com sucesso, False caso contrário
        """
        s3_client = cls._get_s3_client()

        try:
            s3_client.delete_object(
                Bucket=settings.AWS_BUCKET_NAME,
                Key=s3_key
            )
            return True
        except ClientError:
            return False

    @classmethod
    def delete_prefix(cls, prefix: str) -> int:
        """
        Deleta TODOS os objetos cujo Key comeca com o prefixo.

        CUIDADO: passar um prefixo correto e restrito. Idealmente algo como
        'org-{id}/brandguides/{timestamp}/' para evitar deletes em excesso.

        Args:
            prefix: prefixo do S3 (ex: 'org-23/brandguides/1776292563/')

        Returns:
            Numero de objetos deletados.
        """
        if not prefix or '/' not in prefix:
            # Guard contra prefixos muito abertos (ex: 'org-23')
            raise ValueError('delete_prefix requer um prefixo com pelo menos um /')

        s3_client = cls._get_s3_client()
        deleted_count = 0

        paginator = s3_client.get_paginator('list_objects_v2')
        try:
            for page in paginator.paginate(
                Bucket=settings.AWS_BUCKET_NAME,
                Prefix=prefix,
            ):
                objects = page.get('Contents', [])
                if not objects:
                    continue

                # delete_objects aceita ate 1000 keys por chamada
                batch = [{'Key': obj['Key']} for obj in objects]
                for i in range(0, len(batch), 1000):
                    chunk = batch[i:i + 1000]
                    resp = s3_client.delete_objects(
                        Bucket=settings.AWS_BUCKET_NAME,
                        Delete={'Objects': chunk, 'Quiet': True},
                    )
                    deleted_count += len(chunk) - len(resp.get('Errors', []))
        except ClientError:
            # Retornar o que foi possivel deletar; caller decide o que fazer
            return deleted_count

        return deleted_count
    
    @classmethod
    def get_public_url(cls, s3_key: str) -> str:
        """
        Retorna URL pública do arquivo (para armazenar no banco)
        
        Args:
            s3_key: Chave do arquivo no S3
            
        Returns:
            URL pública (não temporária)
        """
        return (
            f"https://{settings.AWS_BUCKET_NAME}.s3."
            f"{settings.AWS_REGION}.amazonaws.com/{s3_key}"
        )
    
    @classmethod
    def validate_organization_access(
        cls,
        s3_key: str,
        organization_id: int
    ) -> bool:
        """
        Valida que organização tem acesso ao arquivo
        
        Args:
            s3_key: Chave do arquivo
            organization_id: ID da organização
            
        Returns:
            True se acesso permitido
            
        Raises:
            ValueError: Se acesso negado
        """
        expected_prefix = f"org-{organization_id}/"
        
        if not s3_key.startswith(expected_prefix):
            raise ValueError(
                f"Acesso negado: arquivo não pertence à organização {organization_id}. "
                f"Esperado prefixo '{expected_prefix}', recebido '{s3_key}'"
            )
        
        return True
