"""
IAMKT - Image Hash Utilities
Sistema anti-repetição de imagens usando hash perceptual
"""
import imagehash
from PIL import Image
import logging
from io import BytesIO

logger = logging.getLogger(__name__)


def calculate_perceptual_hash(image_file, hash_size=16):
    """
    Calcula hash perceptual de uma imagem
    
    Args:
        image_file: Arquivo de imagem (File, BytesIO, ou path)
        hash_size: Tamanho do hash (padrão: 16 = 64 caracteres)
    
    Returns:
        str: Hash perceptual em formato hexadecimal
    
    Raises:
        Exception: Se houver erro ao processar a imagem
    """
    try:
        # Abrir imagem
        if isinstance(image_file, str):
            img = Image.open(image_file)
        else:
            # Se for um arquivo Django, precisamos ler o conteúdo
            if hasattr(image_file, 'read'):
                image_file.seek(0)  # Garantir que estamos no início
                img = Image.open(BytesIO(image_file.read()))
                image_file.seek(0)  # Resetar para uso posterior
            else:
                img = Image.open(image_file)
        
        # Calcular hash perceptual (pHash)
        # pHash é mais robusto que aHash para detectar imagens similares
        hash_value = imagehash.phash(img, hash_size=hash_size)
        
        logger.info(f"Hash perceptual calculado: {hash_value}")
        return str(hash_value)
        
    except Exception as e:
        logger.error(f"Erro ao calcular hash perceptual: {e}")
        raise


def calculate_average_hash(image_file, hash_size=8):
    """
    Calcula hash médio de uma imagem (mais rápido, menos preciso)
    
    Args:
        image_file: Arquivo de imagem
        hash_size: Tamanho do hash (padrão: 8)
    
    Returns:
        str: Hash médio em formato hexadecimal
    """
    try:
        if isinstance(image_file, str):
            img = Image.open(image_file)
        else:
            if hasattr(image_file, 'read'):
                image_file.seek(0)
                img = Image.open(BytesIO(image_file.read()))
                image_file.seek(0)
            else:
                img = Image.open(image_file)
        
        hash_value = imagehash.average_hash(img, hash_size=hash_size)
        return str(hash_value)
        
    except Exception as e:
        logger.error(f"Erro ao calcular hash médio: {e}")
        raise


def calculate_difference_hash(image_file, hash_size=8):
    """
    Calcula hash de diferença de uma imagem
    
    Args:
        image_file: Arquivo de imagem
        hash_size: Tamanho do hash
    
    Returns:
        str: Hash de diferença em formato hexadecimal
    """
    try:
        if isinstance(image_file, str):
            img = Image.open(image_file)
        else:
            if hasattr(image_file, 'read'):
                image_file.seek(0)
                img = Image.open(BytesIO(image_file.read()))
                image_file.seek(0)
            else:
                img = Image.open(image_file)
        
        hash_value = imagehash.dhash(img, hash_size=hash_size)
        return str(hash_value)
        
    except Exception as e:
        logger.error(f"Erro ao calcular hash de diferença: {e}")
        raise


def compare_hashes(hash1, hash2):
    """
    Compara dois hashes e retorna a diferença (distância de Hamming)
    
    Args:
        hash1: Primeiro hash (string)
        hash2: Segundo hash (string)
    
    Returns:
        int: Diferença entre os hashes (0 = idênticos, maior = mais diferentes)
    
    Exemplo:
        diff = compare_hashes("abc123...", "abc456...")
        if diff < 10:
            print("Imagens similares")
    """
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        
        # Distância de Hamming
        difference = h1 - h2
        
        logger.debug(f"Diferença entre hashes: {difference}")
        return difference
        
    except Exception as e:
        logger.error(f"Erro ao comparar hashes: {e}")
        return 999  # Retorna valor alto em caso de erro


def is_image_similar(new_hash, existing_hashes, threshold=10):
    """
    Verifica se uma imagem é similar a alguma das existentes
    
    Args:
        new_hash: Hash da nova imagem (string)
        existing_hashes: Lista de hashes existentes (list of strings)
        threshold: Limite de diferença para considerar similar (padrão: 10)
                  0 = idênticas
                  1-5 = muito similares
                  6-10 = similares
                  11-20 = pouco similares
                  >20 = diferentes
    
    Returns:
        tuple: (bool, str|None, int|None)
               - É similar?
               - Hash mais similar (se encontrado)
               - Diferença mínima encontrada
    
    Exemplo:
        is_similar, similar_hash, diff = is_image_similar(
            new_hash="abc123...",
            existing_hashes=["def456...", "ghi789..."],
            threshold=10
        )
        if is_similar:
            print(f"Imagem similar encontrada! Diferença: {diff}")
    """
    if not existing_hashes:
        return False, None, None
    
    min_difference = 999
    most_similar_hash = None
    
    for existing_hash in existing_hashes:
        try:
            diff = compare_hashes(new_hash, existing_hash)
            
            if diff < min_difference:
                min_difference = diff
                most_similar_hash = existing_hash
                
        except Exception as e:
            logger.warning(f"Erro ao comparar com hash {existing_hash}: {e}")
            continue
    
    is_similar = min_difference <= threshold
    
    if is_similar:
        logger.info(f"Imagem similar encontrada! Diferença: {min_difference}")
    else:
        logger.info(f"Imagem não é similar. Diferença mínima: {min_difference}")
    
    return is_similar, most_similar_hash, min_difference


def find_similar_images_in_queryset(new_image_file, queryset, threshold=10):
    """
    Busca imagens similares em um QuerySet de ReferenceImage
    
    Args:
        new_image_file: Arquivo da nova imagem
        queryset: QuerySet de ReferenceImage
        threshold: Limite de similaridade
    
    Returns:
        tuple: (bool, ReferenceImage|None, int|None)
               - Encontrou similar?
               - Objeto ReferenceImage mais similar
               - Diferença
    
    Exemplo:
        from apps.knowledge.models import ReferenceImage
        
        is_similar, similar_img, diff = find_similar_images_in_queryset(
            new_image_file=uploaded_file,
            queryset=ReferenceImage.objects.all(),
            threshold=10
        )
        
        if is_similar:
            return {
                'error': f'Imagem similar já existe: {similar_img.title}',
                'similar_image': similar_img,
                'difference': diff
            }
    """
    try:
        # Calcular hash da nova imagem
        new_hash = calculate_perceptual_hash(new_image_file)
        
        # Extrair hashes existentes
        existing_hashes = list(queryset.values_list('perceptual_hash', flat=True))
        
        # Verificar similaridade
        is_similar, similar_hash, min_diff = is_image_similar(
            new_hash, 
            existing_hashes, 
            threshold
        )
        
        if is_similar:
            # Encontrar o objeto correspondente
            similar_obj = queryset.filter(perceptual_hash=similar_hash).first()
            return True, similar_obj, min_diff
        
        return False, None, min_diff
        
    except Exception as e:
        logger.error(f"Erro ao buscar imagens similares: {e}")
        return False, None, None


def get_image_dimensions(image_file):
    """
    Retorna dimensões de uma imagem
    
    Args:
        image_file: Arquivo de imagem
    
    Returns:
        tuple: (width, height)
    """
    try:
        if isinstance(image_file, str):
            img = Image.open(image_file)
        else:
            if hasattr(image_file, 'read'):
                image_file.seek(0)
                img = Image.open(BytesIO(image_file.read()))
                image_file.seek(0)
            else:
                img = Image.open(image_file)
        
        return img.size  # (width, height)
        
    except Exception as e:
        logger.error(f"Erro ao obter dimensões da imagem: {e}")
        return None, None


def validate_image_file(image_file, max_size_mb=10, allowed_formats=None):
    """
    Valida arquivo de imagem
    
    Args:
        image_file: Arquivo de imagem
        max_size_mb: Tamanho máximo em MB (padrão: 10)
        allowed_formats: Lista de formatos permitidos (padrão: ['JPEG', 'PNG', 'GIF', 'WEBP'])
    
    Returns:
        tuple: (bool, str|None)
               - É válido?
               - Mensagem de erro (se inválido)
    """
    if allowed_formats is None:
        allowed_formats = ['JPEG', 'PNG', 'GIF', 'WEBP', 'BMP']
    
    try:
        # Verificar tamanho
        if hasattr(image_file, 'size'):
            size_mb = image_file.size / (1024 * 1024)
            if size_mb > max_size_mb:
                return False, f"Arquivo muito grande ({size_mb:.1f}MB). Máximo: {max_size_mb}MB"
        
        # Verificar formato
        if hasattr(image_file, 'read'):
            image_file.seek(0)
            img = Image.open(BytesIO(image_file.read()))
            image_file.seek(0)
        else:
            img = Image.open(image_file)
        
        if img.format not in allowed_formats:
            return False, f"Formato não permitido: {img.format}. Permitidos: {', '.join(allowed_formats)}"
        
        return True, None
        
    except Exception as e:
        return False, f"Erro ao validar imagem: {str(e)}"
