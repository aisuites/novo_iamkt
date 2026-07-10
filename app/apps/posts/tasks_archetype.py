"""
Revisao por IA no PORTAO dos pipelines de arquetipo (C1.4 do redesenho).

Duas intents INDEPENDENTES (limite de 1 revisao cada, contado no ctx):
  - kind='text':  reescreve os textos das zonas/legenda a partir dos ATUAIS
                  (incluindo edicoes manuais) + o pedido do usuario. NUNCA
                  re-sorteia arquetipo nem cor — revisao incremental.
  - kind='image': reescreve a DESCRICAO da imagem (post.image_prompt). So se
                  aplica quando a foto sera GERADA por IA (com upload/ref do
                  usuario o portao nem oferece a opcao).

Generico para todxs/vb/samsung: opera sobre content/gate_map/caption ja
persistidos pela Etapa A — nao re-roda o skill brain da org.
"""
import json
import logging

from celery import shared_task
from django.utils import timezone as dj_tz

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-4-6'
MAX_TOKENS = 1500

TEMPLATE_REVISION_LIMIT = 1   # por kind (text e image separados)

_ORG_CTX_KEY = {'todxs': 'todxs', 'vb': 'vb', 'samsung': 'samsung'}

_TEXT_SYSTEM = """Você é revisor de textos de posts de rede social de uma marca.
Receberá os TEXTOS ATUAIS de um post (zonas de um template fixo), a legenda,
as hashtags e um PEDIDO do usuário. Reescreva APENAS o que o pedido exige,
mantendo o resto igual.

REGRAS:
- Responda SÓ com JSON: {"content": {<MESMAS chaves recebidas>}, "caption": "...", "hashtags": ["..."]}
- NUNCA adicione/remova chaves de content; mantenha comprimentos SEMELHANTES
  aos atuais (o layout é fixo — texto muito maior não cabe na arte).
- Português brasileiro; siga o tom de voz e as palavras recomendadas/evitadas.
- Não mencione que você é uma IA; não use aspas desnecessárias."""

_IMAGE_SYSTEM = """Você revisa a DESCRIÇÃO (prompt) da imagem de fundo de um post.
Receberá a descrição ATUAL (em inglês, formato de prompt de geração de imagem)
e um PEDIDO do usuário em português. Reescreva a descrição incorporando o
pedido, PRESERVANDO as restrições técnicas existentes (enquadramento, áreas
livres, proibições de texto/logo, formato vertical etc.).

Responda SÓ com JSON: {"image_prompt": "..."}"""


@shared_task(bind=True, max_retries=1, default_retry_delay=20)
def revise_template_gate_task(self, post_id: int, kind: str, message: str):
    """Revisa texto OU descricao de imagem no portao; volta o post a 'pending'."""
    from apps.posts.models import Post
    from apps.posts.tasks import _record_ai_usage
    from apps.posts.services.artkit.brain import call_brain, parse_json, extract_usage

    post = Post.objects.get(id=post_id)
    org_key = _ORG_CTX_KEY.get(post.pipeline_used or '')
    ctx = post.local_pipeline_context or {}
    org_ctx = ctx.get(org_key) or {}

    def _back_to_pending(applied: bool, error: str = ''):
        rev = ctx.get('template_revisions') or {}
        if applied:
            rev[kind] = int(rev.get(kind) or 0) + 1
        ctx['template_revisions'] = rev
        trace = org_ctx.get('trace') or []
        trace.append({'etapa': 'portao_revisao_ia', 'kind': kind,
                      'message': message, 'applied': applied, 'error': error,
                      'at': dj_tz.now().isoformat()})
        org_ctx['trace'] = trace
        if org_key:
            ctx[org_key] = org_ctx
        post.local_pipeline_context = ctx
        post.status = 'pending'
        post.save()

    try:
        if kind == 'image':
            current = (post.image_prompt or '').strip()
            if not current:
                _back_to_pending(False, 'sem descricao de imagem (foto do usuario?)')
                return {'success': False, 'error': 'no_image_prompt'}
            user_text = (f'DESCRIÇÃO ATUAL:\n{current}\n\n'
                         f'PEDIDO DO USUÁRIO:\n{message}')
            resp, raw = call_brain(model=MODEL, max_tokens=MAX_TOKENS,
                                   system=_IMAGE_SYSTEM, user_text=user_text)
            parsed = parse_json(raw) or {}
            new_prompt = (parsed.get('image_prompt') or '').strip()
            _record_ai_usage(post, step='text_generation', model=MODEL,
                             usage_dict=extract_usage(resp),
                             purpose='template_revision_image')
            if not new_prompt:
                _back_to_pending(False, 'parse falhou')
                return {'success': False, 'error': 'parse'}
            post.image_prompt = new_prompt
            _back_to_pending(True)
            return {'success': True, 'kind': kind}

        # ---- kind == 'text' ----
        content = dict(org_ctx.get('content') or {})
        # base = textos ATUAIS do Post (ja com edicoes manuais), via gate_map
        gm = org_ctx.get('gate_map') or {}
        if gm.get('title') and (post.title or '').strip():
            content[gm['title']] = post.title.strip()
        if gm.get('subtitle') and (post.subtitle or '').strip():
            content[gm['subtitle']] = post.subtitle.strip()
        # 'ilustracao' (vb) e afins nao sao texto editavel — fora do payload
        editable = {k: v for k, v in content.items()
                    if isinstance(v, (str, list)) and k != 'ilustracao'}
        kb = None
        try:
            from apps.knowledge.models import KnowledgeBase
            kb = KnowledgeBase.objects.filter(organization=post.organization).first()
        except Exception:
            pass
        brand_bits = {
            'tom_voz': getattr(kb, 'tom_voz_externo', '') or '',
            'palavras_recomendadas': getattr(kb, 'palavras_recomendadas', []) or [],
            'palavras_evitar': getattr(kb, 'palavras_evitar', []) or [],
        }
        user_text = (
            f'TEXTOS ATUAIS (zonas do template):\n{json.dumps(editable, ensure_ascii=False)}\n\n'
            f'LEGENDA ATUAL:\n{post.caption or org_ctx.get("caption") or ""}\n\n'
            f'HASHTAGS ATUAIS:\n{json.dumps(post.hashtags or org_ctx.get("hashtags") or [], ensure_ascii=False)}\n\n'
            f'MARCA (tom de voz e vocabulário):\n{json.dumps(brand_bits, ensure_ascii=False)}\n\n'
            f'PEDIDO DO USUÁRIO:\n{message}'
        )
        resp, raw = call_brain(model=MODEL, max_tokens=MAX_TOKENS,
                               system=_TEXT_SYSTEM, user_text=user_text)
        parsed = parse_json(raw) or {}
        _record_ai_usage(post, step='text_generation', model=MODEL,
                         usage_dict=extract_usage(resp),
                         purpose='template_revision_text')
        new_content = parsed.get('content') or {}
        if not isinstance(new_content, dict) or not new_content:
            _back_to_pending(False, 'parse falhou')
            return {'success': False, 'error': 'parse'}
        # aplica so as chaves que ja existiam (revisor nao inventa zona)
        for k, v in new_content.items():
            if k in editable and v:
                content[k] = v
        org_ctx['content'] = content
        # espelha nos campos do portao (o que o usuario ve/edita)
        if gm.get('title') and content.get(gm['title']):
            post.title = str(content[gm['title']]).replace('\n', ' ')
        if gm.get('subtitle') and content.get(gm['subtitle']):
            post.subtitle = str(content[gm['subtitle']])
        if parsed.get('caption'):
            post.caption = parsed['caption']
            org_ctx['caption'] = parsed['caption']
        if parsed.get('hashtags'):
            post.hashtags = parsed['hashtags']
            org_ctx['hashtags'] = parsed['hashtags']
        _back_to_pending(True)
        return {'success': True, 'kind': kind}

    except Exception as exc:
        logger.exception('[template_revision] falhou post=%s kind=%s', post_id, kind)
        try:
            _back_to_pending(False, str(exc)[:200])
        except Exception:
            pass
        return {'success': False, 'error': str(exc)[:200]}
