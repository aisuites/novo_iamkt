"""
Validadores avançados para imagens
Seguindo padrão do guia Django S3 - Validação de dimensões e qualidade
"""
from PIL import Image
from io import BytesIO
from typing import Tuple, Optional


class ImageValidator:
    """Validações avançadas de imagens"""
    
    # Dimensões mínimas por categoria
    MIN_DIMENSIONS = {
        'logos': (100, 100),
        'references': (200, 200),
        'posts': (200, 200),
    }
    
    # Dimensões máximas por categoria
    MAX_DIMENSIONS = {
        'logos': (10000, 10000),
        'references': (10000, 10000),
        'posts': (10000, 10000),
    }
    
    # Aspect ratios permitidos (largura/altura)
    # None = qualquer ratio permitido
    ALLOWED_RATIOS = {
        'logos': [(1, 1), (16, 9), (4, 3), (3, 2)],  # Quadrado, widescreen, etc
        'references': None,  # Qualquer ratio
        'posts': None,  # Qualquer ratio
    }
    
    @classmethod
    def validate_dimensions(
        cls,
        image_data: bytes,
        category: str
    ) -> Tuple[bool, Optional[str], Optional[dict]]:
        """
        Valida dimensões da imagem
        
        Args:
            image_data: Bytes da imagem
            category: Categoria (logos, references, posts)
            
        Returns:
            (is_valid, error_message, dimensions_info)
            dimensions_info = {'width': int, 'height': int, 'ratio': float}
        """
        try:
            # Abrir imagem
            img = Image.open(BytesIO(image_data))
            width, height = img.size
            
            # Info de dimensões
            dimensions_info = {
                'width': width,
                'height': height,
                'ratio': width / height if height > 0 else 0
            }
            
            # Validar dimensões mínimas
            min_dims = cls.MIN_DIMENSIONS.get(category)
            if min_dims:
                min_width, min_height = min_dims
                if width < min_width or height < min_height:
                    return False, (
                        f"Dimensões muito pequenas. "
                        f"Mínimo: {min_width}x{min_height}px"
                    ), dimensions_info
            
            # Validar dimensões máximas
            max_dims = cls.MAX_DIMENSIONS.get(category)
            if max_dims:
                max_width, max_height = max_dims
                if width > max_width or height > max_height:
                    return False, (
                        f"Dimensões muito grandes. "
                        f"Máximo: {max_width}x{max_height}px"
                    ), dimensions_info
            
            # Validar aspect ratio
            allowed_ratios = cls.ALLOWED_RATIOS.get(category)
            if allowed_ratios:
                ratio = width / height
                
                # Verificar se ratio está próximo de algum permitido (±10%)
                ratio_valid = False
                for allowed_width, allowed_height in allowed_ratios:
                    allowed_ratio = allowed_width / allowed_height
                    if abs(ratio - allowed_ratio) / allowed_ratio <= 0.1:
                        ratio_valid = True
                        break
                
                if not ratio_valid:
                    ratio_strings = [f"{w}:{h}" for w, h in allowed_ratios]
                    return False, (
                        f"Proporção da imagem não permitida. "
                        f"Permitidas: {', '.join(ratio_strings)}"
                    ), dimensions_info
            
            return True, None, dimensions_info
            
        except Exception as e:
            return False, f"Erro ao validar imagem: {str(e)}", None
    
    @classmethod
    def validate_image_quality(
        cls,
        image_data: bytes,
        min_dpi: int = 72
    ) -> Tuple[bool, Optional[str]]:
        """
        Valida qualidade da imagem (DPI)
        
        Args:
            image_data: Bytes da imagem
            min_dpi: DPI mínimo
            
        Returns:
            (is_valid, error_message)
        """
        try:
            img = Image.open(BytesIO(image_data))
            
            # Obter DPI (se disponível)
            dpi = img.info.get('dpi')
            
            if dpi:
                dpi_x, dpi_y = dpi
                avg_dpi = (dpi_x + dpi_y) / 2
                
                if avg_dpi < min_dpi:
                    return False, (
                        f"Qualidade da imagem muito baixa. "
                        f"DPI mínimo: {min_dpi}, detectado: {int(avg_dpi)}"
                    )
            
            return True, None
            
        except Exception as e:
            # Se não conseguir ler DPI, considerar válido
            return True, None
