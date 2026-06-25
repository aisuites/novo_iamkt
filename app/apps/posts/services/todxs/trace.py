"""
Observabilidade do fluxo TODXS.

Sanitiza payloads para inspecao humana: remove base64 de imagens (troca por
descritor legivel) e preserva o resto (prompts, JSON cru dos LLMs). O trace
completo e gravado em Post.local_pipeline_context['todxs']['trace'].
"""


def image_descriptor(*, role: str, name: str, mime: str, n_bytes: int) -> dict:
    """Descritor curto de uma imagem enviada a um LLM (sem o base64)."""
    return {
        'tipo': 'imagem',
        'papel': role,
        'nome': name,
        'mime': mime,
        'bytes': int(n_bytes or 0),
    }


def strip_base64(obj, max_str: int = 20000):
    """
    Percorre dict/list recursivamente e substitui strings longas de base64
    (ex.: inlineData.data da resposta do Gemini) por um marcador curto.
    Trunca tambem qualquer string muito longa para o trace ficar legivel.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ('data', 'b64', 'base64', 'bytesBase64Encoded') and isinstance(v, str) and len(v) > 256:
                out[k] = f'<base64 {len(v)} chars omitido>'
            else:
                out[k] = strip_base64(v, max_str)
        return out
    if isinstance(obj, list):
        return [strip_base64(v, max_str) for v in obj]
    if isinstance(obj, str) and len(obj) > max_str:
        return obj[:max_str] + f'... <{len(obj) - max_str} chars omitidos>'
    return obj
