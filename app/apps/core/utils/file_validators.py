"""
Validadores de arquivo reutilizáveis
Seguindo padrão do guia Django S3 - Separação de responsabilidades (SOLID)
"""
from typing import Tuple, Optional


class FileValidator:
    """Validações de arquivo centralizadas"""
    
    # Tipos de arquivo permitidos por categoria
    ALLOWED_TYPES = {
        'logos': {
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'image/svg+xml': 'svg',
            'image/webp': 'webp',
        },
        'references': {
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'image/gif': 'gif',
            'image/webp': 'webp',
        },
        'fonts': {
            'font/ttf': 'ttf',
            'font/otf': 'otf',
            'font/woff': 'woff',
            'font/woff2': 'woff2',
            'application/x-font-ttf': 'ttf',
            'application/x-font-otf': 'otf',
        },
        'documents': {
            'application/pdf': 'pdf',
        },
        'posts': {
            'image/jpeg': 'jpg',
            'image/png': 'png',
            'image/webp': 'webp',
        },
        'brandguides': {
            'application/pdf': 'pdf',
        },
    }

    # Tamanhos máximos por categoria (em MB)
    MAX_FILE_SIZES = {
        'logos': 5,
        'references': 10,
        'fonts': 2,
        'documents': 20,
        'posts': 10,
        'brandguides': 50,  # Brandguides PDF podem ser grandes
    }
    
    @classmethod
    def validate_file_type(
        cls,
        file_type: str,
        category: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Valida tipo de arquivo para categoria
        
        Args:
            file_type: MIME type do arquivo
            category: Categoria (logos, references, fonts, documents, posts)
        
        Returns:
            (is_valid, error_message)
        """
        allowed_types = cls.ALLOWED_TYPES.get(category, {})
        
        if not allowed_types:
            return False, f"Categoria inválida: {category}"
        
        if file_type not in allowed_types:
            allowed_list = ', '.join(allowed_types.keys())
            return False, (
                f"Tipo '{file_type}' não permitido para {category}. "
                f"Aceitos: {allowed_list}"
            )
        
        return True, None
    
    @classmethod
    def validate_file_size(
        cls,
        file_size: int,
        category: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Valida tamanho do arquivo
        
        Args:
            file_size: Tamanho em bytes
            category: Categoria do arquivo
            
        Returns:
            (is_valid, error_message)
        """
        max_size_mb = cls.MAX_FILE_SIZES.get(category, 10)
        max_size_bytes = max_size_mb * 1024 * 1024
        
        if file_size > max_size_bytes:
            return False, (
                f"Arquivo muito grande. "
                f"Máximo para {category}: {max_size_mb}MB"
            )
        
        if file_size <= 0:
            return False, "Arquivo vazio"
        
        return True, None
    
    @classmethod
    def get_extension(cls, file_type: str, category: str) -> Optional[str]:
        """
        Retorna extensão para o tipo de arquivo
        
        Args:
            file_type: MIME type
            category: Categoria
            
        Returns:
            Extensão do arquivo (ex: 'png', 'jpg') ou None
        """
        allowed_types = cls.ALLOWED_TYPES.get(category, {})
        return allowed_types.get(file_type)
    
    @classmethod
    def validate_file(
        cls,
        file_type: str,
        file_size: int,
        category: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validação completa de arquivo
        
        Args:
            file_type: MIME type
            file_size: Tamanho em bytes
            category: Categoria
        
        Returns:
            (is_valid, error_message)
        """
        # Validar tipo
        is_valid, error = cls.validate_file_type(file_type, category)
        if not is_valid:
            return False, error
        
        # Validar tamanho
        is_valid, error = cls.validate_file_size(file_size, category)
        if not is_valid:
            return False, error
        
        return True, None
