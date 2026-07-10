"""Caller unificado do brain (Claude) — origem: os 3 skill_brain por org.

Fidelidade: mesmo padrao de chamada dos pipelines (anthropic max_retries=6,
system em blocks com cache ephemeral quando o caller quiser, extracao de texto
por blocos type='text'). parse_json/extract_usage sao os CANONICOS do
post_orchestrator (todxs/vb ja usavam; samsung migra do clone proprio —
mesmos precos $3/$15, sem cache => custo identico).

Nota de comportamento (melhoria consciente, nao silenciosa): o brain do
samsung chamava a API SEM max_retries — ao migrar para ca ele ganha
max_retries=6, alinhado ao fix de resiliencia a 529 do pipeline simples.
"""
import os


def cached_system_blocks(*texts, ttl='1h'):
    """Blocos de system com cache ephemeral (padrao todxs/vb)."""
    return [{'type': 'text', 'text': t,
             'cache_control': {'type': 'ephemeral', 'ttl': ttl}}
            for t in texts if t]


def call_brain(*, model, max_tokens, system, user_text, max_retries=6):
    """1 chamada Claude. `system`: str OU lista de blocks. Retorna (resp, raw)."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise RuntimeError('ANTHROPIC_API_KEY ausente no ambiente')
    import anthropic
    client = anthropic.Anthropic(api_key=api_key, max_retries=max_retries)
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{'role': 'user', 'content': user_text}],
    )
    raw = ''.join(
        blk.text for blk in resp.content if getattr(blk, 'type', None) == 'text')
    return resp, raw


def parse_json(text):
    """Parse tolerante de JSON (canonico do post_orchestrator)."""
    from apps.posts.services.post_orchestrator import _parse_json
    return _parse_json(text)


def extract_usage(resp, cache_ttl='5m'):
    """Tokens/custo incluindo cache (canonico do post_orchestrator)."""
    from apps.posts.services.post_orchestrator import _extract_usage
    return _extract_usage(resp, cache_ttl=cache_ttl)
