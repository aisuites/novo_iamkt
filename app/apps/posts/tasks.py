"""
Celery tasks da pipeline interna de geracao de post.

Substitui os workflows N8N (gerar-post-appiamkt e gerarimagem-appiamkt)
quando o usuario clica em "Enviar Fluxo interno" no modal.

Tasks:
    - generate_post_text_task(post_id): gera texto via Claude Sonnet 4.5
    - generate_post_image_task(post_id, message): gera imagem via Gemini 3 Pro
"""

import logging
from decimal import Decimal

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_post_text_task(self, post_id: int):
    """
    Gera o texto do post (title, subtitle, image_prompt, caption, hashtags,
    visual_brief, cta_text) via Claude Sonnet 4.5. Atualiza o Post no banco.

    Substitui o N8N workflow 'gerar-post-appiamkt'. Disparada quando o user
    clica em 'Enviar Fluxo interno' no modal.

    Fluxo:
        1. Carrega Post + KB
        2. Monta resumo da KB (preferindo n8n_compilation)
        3. Chama Claude via service
        4. Salva campos do Post (caption, hashtags, title, subtitle,
           image_prompt, visual_brief, cta)
        5. Loga em AIUsageLog
        6. Status final: 'awaiting_image' (user pode disparar imagem depois)
    """
    from apps.posts.models import Post
    from apps.posts.services.claude_post_generator import generate_post_text

    logger.info('[posts.local] generate_post_text_task iniciada post_id=%s', post_id)

    try:
        post = Post.objects.select_related(
            'organization', 'post_format'
        ).get(id=post_id)
    except Post.DoesNotExist:
        logger.error('[posts.local] Post %s nao existe', post_id)
        return {'success': False, 'error': 'post_not_found'}

    # Marca em progresso
    post.status = 'generating'
    post.save(update_fields=['status'])

    # ============================================================
    # PIPELINE 2-AGENTES (copywriter + designer-orquestrador)
    # Coexiste com o pipeline antigo via env POST_USE_NEW_PIPELINE.
    # ============================================================
    import os as _os_env
    use_new_pipeline = _os_env.environ.get(
        'POST_USE_NEW_PIPELINE', '').lower() in ('1', 'true', 'yes')
    if use_new_pipeline:
        try:
            return _run_new_pipeline_phase1(post)
        except Exception:
            logger.exception(
                '[posts.local] pipeline novo falhou no post %s — '
                'caindo no pipeline antigo (fallback)', post_id,
            )
            # cai pro pipeline antigo abaixo

    # Resumo da KB (igual ao fallback do N8N)
    kb_summary = _build_kb_summary(post.organization)

    # Formato (PostFormat ou dict legado)
    formato = _format_to_dict(post.post_format) if post.post_format else {
        'name': post.formats[0] if post.formats else 'feed',
        'aspect_ratio': '1:1',
    }

    # Logos da KB (filtrados pelos selecionados, se houver)
    logo_urls = list(_logos_from_org(post.organization, post=post))

    # Reference images do Post (PostReferenceImage) + descricao geral
    reference_images = list(_reference_images_from_post(post))
    ctx = post.local_pipeline_context or {}
    refs_usage_general = ctx.get('references_usage_description', '') or ''

    # Anexa observacao geral como linha extra na primeira referencia, OU
    # passa via knowledge_base_summary se nao houver refs (mais facil para o LLM)
    if refs_usage_general:
        kb_summary = (
            f'{kb_summary}\n\n'
            f'== Observacao sobre uso das referencias visuais ==\n'
            f'{refs_usage_general}'
        )

    try:
        result = generate_post_text(
            knowledge_base_summary=kb_summary,
            rede_social=post.social_network,
            formato=formato,
            tema=post.requested_theme,
            cta_requested=post.cta_requested,
            is_carousel=post.is_carousel,
            image_count=post.image_count,
            reference_images=reference_images,
            logo_urls=logo_urls,
        )
    except Exception as exc:
        logger.exception('[posts.local] Falha Claude post_id=%s', post_id)
        post.status = 'failed'
        post.save(update_fields=['status'])
        raise self.retry(exc=exc)

    structured = result['structured']
    usage = result['usage']

    # Normaliza hashtags: garante prefixo '#' em cada item (Claude as vezes esquece)
    raw_hashtags = structured.get('hashtags') or []
    normalized_hashtags = [
        h if str(h).startswith('#') else f'#{str(h).lstrip("#").strip()}'
        for h in raw_hashtags if h
    ]
    structured['hashtags'] = normalized_hashtags

    # Aplica resultado no Post
    if post.is_carousel and isinstance(structured.get('slides'), list):
        # Carrossel: salva slides em campo dedicado (se existir) ou em caption
        slides = structured['slides']
        post.caption = structured.get('caption') or ''
        post.hashtags = structured.get('hashtags') or []
        post.cta = structured.get('cta_text') or ''
        # Slides ficam disponiveis para o gerador de imagem via primeiro slide
        if slides:
            first = slides[0]
            post.title = first.get('title', '')
            post.subtitle = first.get('subtitle', '')
            post.image_prompt = first.get('image_prompt', '')
            post.visual_brief = first.get('visual_brief', '')
        # Guarda todos os slides no JSON do post para a etapa de imagem
        post.slides_data = slides
    else:
        post.title = structured.get('title', '')
        post.subtitle = structured.get('subtitle', '')
        post.image_prompt = structured.get('image_prompt', '')
        post.visual_brief = structured.get('visual_brief', '')
        post.caption = structured.get('caption', '')
        post.hashtags = structured.get('hashtags') or []
        post.cta = structured.get('cta_text', '')

    post.ia_provider = 'anthropic'
    post.ia_model_text = result['model']
    # Status final 'pending' segue mesma semantica do callback N8N:
    # texto pronto, aguardando user clicar em "Gerar Imagem" depois.
    post.status = 'pending'
    post.save()

    # Loga custo
    _log_usage(post, result['model'], usage, purpose='generate_post_text')

    logger.info(
        '[posts.local] generate_post_text_task OK post_id=%s tokens_in=%s tokens_out=%s cost=$%s',
        post_id, usage.get('input_tokens'), usage.get('output_tokens'),
        usage.get('cost_usd'),
    )

    return {
        'success': True,
        'post_id': post_id,
        'model': result['model'],
        'usage': usage,
    }


# ---- Helpers ----------------------------------------------------------------


def _build_kb_summary(organization) -> str:
    """
    Constroi resumo textual da KB usado como contexto no prompt.
    Prefere `n8n_compilation.marketing_input_summary`; se vazio, monta string
    com 6 campos da KB.
    """
    from apps.knowledge.models import KnowledgeBase

    kb = KnowledgeBase.objects.filter(organization=organization).first()
    if not kb:
        return f'(Organizacao {organization.name} sem base de conhecimento)'

    # n8n_compilation pode ser dict (atual) ou string (legado)
    compilation = getattr(kb, 'n8n_compilation', None)
    summary_text = ''
    if isinstance(compilation, dict):
        summary_text = (compilation.get('marketing_input_summary') or '').strip()
    elif isinstance(compilation, str):
        summary_text = compilation.strip()
    if summary_text and len(summary_text) > 50:
        return summary_text

    # Fallback manual
    parts = [
        f'Empresa: {kb.nome_empresa or organization.name}',
    ]
    if kb.missao:
        parts.append(f'Missao: {kb.missao}')
    if kb.posicionamento:
        parts.append(f'Posicionamento: {kb.posicionamento}')
    if kb.tom_voz_externo:
        parts.append(f'Tom de voz: {kb.tom_voz_externo}')
    if kb.publico_externo:
        parts.append(f'Publico-alvo: {kb.publico_externo}')
    if kb.proposta_valor:
        parts.append(f'Proposta de valor: {kb.proposta_valor}')
    return '\n'.join(parts)


def _format_to_dict(post_format) -> dict:
    return {
        'name': post_format.name,
        'width': post_format.width,
        'height': post_format.height,
        'aspect_ratio': post_format.aspect_ratio,
    }


def _logos_from_org(organization, post=None):
    """
    Retorna URLs dos logos cadastrados na KB da org.
    Se post tiver local_pipeline_context.selected_logo_ids, filtra.
    """
    from apps.knowledge.models import KnowledgeBase, Logo
    kb = KnowledgeBase.objects.filter(organization=organization).first()
    if not kb:
        return []
    qs = Logo.objects.filter(knowledge_base=kb)
    if post is not None:
        ctx = post.local_pipeline_context or {}
        selected_ids = ctx.get('selected_logo_ids') or []
        if selected_ids:
            qs = qs.filter(id__in=selected_ids)
    return [l.s3_url for l in qs if l.s3_url]


def _reference_images_from_post(post):
    """Retorna lista de dicts com URL e descricao de uso de cada PostReferenceImage."""
    from apps.posts.models import PostReferenceImage
    refs = PostReferenceImage.objects.filter(post=post).order_by('order', 'id')
    out = []
    for ref in refs:
        out.append({
            'url': ref.s3_url,
            's3_key': ref.s3_key,
            'name': ref.original_name,
            'usage_description': getattr(ref, 'usage_description', '') or '',
            'aspects_to_use': getattr(ref, 'aspects_to_use', '') or '',
            'usage_type': getattr(ref, 'usage_type', '') or '',
        })
    return out


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def generate_post_image_task(self, post_id: int, message: str = ''):
    """
    Gera a imagem do post via Gemini 3 Pro Image e salva no S3.

    Substitui o N8N workflow 'gerarimagem-appiamkt'. Disparada quando o user
    clica em 'Gerar Imagem' no detalhe do post (para posts com pipeline=local).

    Fluxo:
        1. Carrega Post + KB
        2. Coleta paleta, tipografia, referencias (logos, ref_kb, ref_post)
        3. Gera presigned URLs (24h) para todas as referencias
        4. Chama Gemini via service (multimodal: prompt + inline_data das refs)
        5. Faz upload do PNG no S3
        6. Atualiza Post (post_images, image_s3_url, status='image_ready')
        7. Loga em AIUsageLog
    """
    from apps.knowledge.models import KnowledgeBase
    from apps.posts.models import Post
    from apps.posts.services.gemini_image_generator import generate_post_image

    logger.info('[posts.local] generate_post_image_task iniciada post_id=%s', post_id)

    try:
        post = Post.objects.select_related(
            'organization', 'post_format', 'user'
        ).get(id=post_id)
    except Post.DoesNotExist:
        logger.error('[posts.local] Post %s nao existe', post_id)
        return {'success': False, 'error': 'post_not_found'}

    post.status = 'image_generating'
    post.save(update_fields=['status'])

    # KB + dados de design
    kb = KnowledgeBase.objects.filter(organization=post.organization).first()
    paleta = _kb_colors(kb)
    tipografia = _kb_typography(kb)
    publico_alvo = (kb.publico_externo if kb else '') or ''
    marketing_input_summary = _kb_summary_marketing(kb)
    formato_px = _formato_px(post)

    ctx = post.local_pipeline_context or {}
    refs_usage_general = ctx.get('references_usage_description', '') or ''

    # text_render_mode determinado AGORA (precisa antes de _collect_references
    # para decidir se inclui logo ou nao)
    import os as _os
    text_render_mode = (
        ctx.get('text_render_mode')
        or _os.environ.get('POST_TEXT_RENDER_MODE', 'pillow')
    ).lower()

    # Coleta logos + uploads como image_parts (refs KB NAO sao mais
    # incluidas — viram dossie textual lido de visual_analysis, ver abaixo)
    references = _collect_references(kb=kb, post=post, text_render_mode=text_render_mode)

    # ============================================================
    # DOSSIE DAS REFS DA KB — lookup puro (sem reanalise por Vision)
    # ============================================================
    # Le o dossie visual ja gravado em ReferenceImage.visual_analysis das
    # refs selecionadas. Gatilho 3: se alguma ainda nao foi analisada,
    # analisa inline AGORA e persiste (a info fica garantida para sempre).
    # O dossie + a intencao do user vao para o ORCHESTRATOR, que decide o
    # quanto de cada aspecto entra no prompt final do Gemini. kb_translations
    # so e usado como fallback quando o orchestrator nao roda.
    kb_dossiers = _collect_kb_dossiers(kb=kb, post=post)
    kb_translations = []

    # Adiciona references_usage_description ao marketing_input_summary
    if refs_usage_general:
        marketing_input_summary = (
            f'{marketing_input_summary}\n\n'
            f'OBSERVACAO sobre uso das imagens de referencia anexadas: '
            f'{refs_usage_general}'
        )

    # Etapa 4.16: desativado o Claude Vision em favor de dereferenciacao
    # simples por imagem
    product_analyses = []

    # brand_keywords: usado em mode='sanitized'
    brand_keywords = _brand_keywords_from_kb(kb)

    # ============================================================
    # PIPELINE NOVO (2 agentes): se POST_USE_NEW_PIPELINE=true E post tem
    # designer_payload preenchido pela Fase 1 nova, usa diretamente o plano
    # do designer. Pula o orquestrador velho.
    # ============================================================
    use_new_pipeline = _os.environ.get(
        'POST_USE_NEW_PIPELINE', '').lower() in ('1', 'true', 'yes')
    spatial_instructions = ''
    layout_document = None
    orchestrator_image_prompt = ''
    orchestration_output = None

    # ── Pipeline novo — caminho preferencial quando Fase 1 rodou ──────────────
    # Usa prompt_designer (prompt Gemini) + layout_engine (elementos Pillow).
    # Ativado quando copy_payload tem _strategic_payload (Fase 1 nova).
    if use_new_pipeline and (post.copy_payload or {}).get('_strategic_payload'):
        try:
            from apps.posts.services.prompt_designer import build_prompt as _build_img_prompt
            from apps.posts.services.layout_engine import build_elements as _build_elements

            _sp = post.copy_payload['_strategic_payload']
            _cp = post.copy_payload
            _canvas_w, _canvas_h = _parse_formato_px(formato_px)

            # 1. Prompt Gemini via prompt_designer
            _prompt_result = _build_img_prompt(
                strategic_payload=_sp,
                copy_payload=_cp,
                canvas_w=_canvas_w,
                canvas_h=_canvas_h,
                kb_dossiers=kb_dossiers,
            )
            if _prompt_result:
                orchestrator_image_prompt = _prompt_result.get('prompt', '')

            # 2. Elementos de layout via layout_engine
            _pillow_kw = _prepare_pillow_overlay(post, kb, formato_px)
            _font_map = {
                'titulo':    _pillow_kw.get('pillow_title_font_path'),
                'subtitulo': _pillow_kw.get('pillow_subtitle_font_path'),
                'cta':       _pillow_kw.get('pillow_title_font_path'),
            }
            _bg_color = _dominant_bg_from_dossiers(kb_dossiers)
            _modal_for_engine = {'logo_position': ctx.get('logo_position') or 'bottom-right'}
            _elements = _build_elements(
                strategic_payload=_sp,
                copy_payload=_cp,
                canvas_w=_canvas_w,
                canvas_h=_canvas_h,
                paleta=paleta,
                fonts=_font_map,
                modal_choices=_modal_for_engine,
                bg_color=_bg_color,
            )
            layout_document = {'elements': _elements}
            pillow_kwargs = {**_pillow_kw}
            # Persiste elementos para o overlay HTML do frontend
            _dp = post.designer_payload or {}
            _dp['_layout_elements'] = _elements
            post.designer_payload = _dp
            post.save(update_fields=['designer_payload'])
            text_render_mode = 'pillow'
            orchestration_output = {
                'image_prompt_final': orchestrator_image_prompt,
                'layout_document': layout_document,
                'text_render_mode': 'pillow',
                '_from': 'layout_engine',
            }
            logger.info(
                '[posts.local][new] layout_engine: %d elementos bg=%s prompt=%d chars',
                len(_elements), _bg_color or 'auto', len(orchestrator_image_prompt),
            )
        except Exception:
            logger.exception('[posts.local][new] layout_engine falhou — fallback designer_payload')
            layout_document = None
            orchestration_output = None

    # Fallback: designer_payload com wireframe_plan (caminho antigo)
    if use_new_pipeline and layout_document is None and (post.designer_payload or {}).get('wireframe_plan'):
        layout_document, orchestrator_image_prompt = _consume_designer_payload(
            post, references, ctx,
        )
        orchestration_output = {
            'image_prompt_final': orchestrator_image_prompt,
            'layout_document': layout_document,
            'text_render_mode': 'pillow',
            '_from': 'designer_agent',
        }
        text_render_mode = 'pillow'
        logger.info(
            '[posts.local][new] usando designer_payload (%d elementos)',
            len(layout_document.get('elements', [])),
        )

    # ============================================================
    # ORCHESTRATOR — analisa briefing + imagens e produz prompt otimizado
    # + layout_plan + spatial_instructions
    # ============================================================
    orchestrator_disabled = _os.environ.get('POST_DISABLE_ORCHESTRATOR', '').lower() in ('1', 'true', 'yes')
    # Pula orquestrador velho se o pipeline novo ja produziu plano
    # Orchestrator roda quando ha imagens (logos/uploads) OU dossies de refs
    # da KB selecionadas — ele e quem filtra os dossies pela intencao do user.
    if not orchestrator_disabled and (references or kb_dossiers) and not layout_document:
        try:
            from apps.posts.services.post_orchestrator import orchestrate_post
            aspect = (post.post_format.aspect_ratio if post.post_format else '') or ''
            orch_result = orchestrate_post(
                post=post,
                references=references,
                kb_summary=marketing_input_summary,
                paleta=paleta,
                tipografia=tipografia,
                references_usage_description=ctx.get('references_usage_description', '') or '',
                formato_px=formato_px,
                aspect_ratio=aspect,
                kb_dossiers=kb_dossiers,
            )
            if orch_result:
                orchestration_output = orch_result['orchestration']
                # Persiste para auditoria
                ctx['orchestration'] = orchestration_output
                ctx['orchestration_usage'] = orch_result.get('usage', {})
                post.local_pipeline_context = ctx
                post.save(update_fields=['local_pipeline_context'])
                # Loga custo do orquestrador no ai_usage_log
                _record_ai_usage(
                    post,
                    step='text_generation',
                    model=orch_result.get('model', 'claude-sonnet-4-6'),
                    usage_dict=orch_result.get('usage') or {},
                    purpose='orchestrator',
                )

                # Aplica decisoes do orchestrator.
                # NAO sobrescreve post.image_prompt (que e a descricao da Fase 1
                # aprovada pelo user). A versao do orquestrador eh canalizada
                # como override pro Gemini SEM persistir no post.
                orchestrator_image_prompt = orchestration_output.get(
                    'image_prompt_final', ''
                ) or ''
                mode_decided = orchestration_output.get('text_render_mode')
                if mode_decided in ('inline', 'sanitized', 'pillow'):
                    text_render_mode = mode_decided
                spatial_instructions = orchestration_output.get(
                    'spatial_instructions_for_gemini', ''
                ) or ''
                # layout_document = "divs" do texto decididas pelo diretor de arte
                # (base do canvas editavel). Se presente, o texto vai via Pillow.
                ld = orchestration_output.get('layout_document') or None
                if ld and ld.get('elements'):
                    layout_document = ld
                    text_render_mode = 'pillow'
                logger.info(
                    '[posts.local] orchestrator -> mode=%s, layout_doc_els=%s, spatial_len=%d',
                    text_render_mode,
                    len((layout_document or {}).get('elements', [])),
                    len(spatial_instructions),
                )
        except Exception:
            logger.exception('[orchestrator] falhou — segue com prompt cru')

    # Fallback (orchestrator off/falhou): injeta dossies como directives
    # textuais no prompt do Gemini, SEM IA extra (lookup puro).
    if kb_dossiers and orchestration_output is None:
        kb_translations = _dossiers_to_translations(kb_dossiers)

    # Se ha uma ref marcada com aspecto 'layout_composicao', queremos replicar
    # o layout dela com as FONTES da KB — isso exige modo pillow.
    layout_dossier = _layout_dossier(kb_dossiers)
    if layout_dossier:
        text_render_mode = 'pillow'
    # ============================================================

    # Smart Pillow overlay — prepara layout_spec, fonts e logo se mode='pillow'
    # Ordem de precedencia (modal vence): brand_spec (base) < orchestrator <
    # dossie do aspecto 'layout_composicao' selecionado no modal.
    pillow_kwargs = {}
    if text_render_mode == 'pillow':
        pillow_kwargs = _prepare_pillow_overlay(post, kb, formato_px)
        # Sobrescreve layout_spec com layout_plan do orchestrator (se houver)
        layout_plan = (orchestration_output or {}).get('layout_plan') or {}
        if layout_plan:
            pillow_kwargs['pillow_layout_spec'] = _layout_plan_to_spec(
                layout_plan, fallback=pillow_kwargs.get('pillow_layout_spec', {}),
            )
        # OVERRIDE final — dossie da ref de layout vence (alinhamento por bloco,
        # zonas %, peso/caixa). Fontes e cores continuam vindo da KB.
        if layout_dossier:
            dossier_spec = _dossier_to_layout_spec(layout_dossier, paleta=paleta)
            # Adaptacao inteligente de formato (LLM) quando a ref de layout
            # nasceu num aspect ratio diferente do post (ex: 1:1 -> 9:16).
            src_ar = layout_dossier.get('_source_ar')
            tgt_ar = _aspect_ratio_to_float(
                post.post_format.aspect_ratio if post.post_format else ''
            )
            if src_ar and tgt_ar and abs(float(src_ar) - tgt_ar) / max(float(src_ar), tgt_ar) > 0.15:
                try:
                    from apps.posts.services.post_orchestrator import adapt_layout_spec
                    adapted = adapt_layout_spec(dossier_spec, float(src_ar), tgt_ar, formato_px)
                    if adapted:
                        dossier_spec = adapted
                        logger.info('[posts.local] layout adaptado AR %s -> %s', src_ar, tgt_ar)
                except Exception:
                    logger.exception('[posts.local] adaptacao de layout falhou — usa spec original')
            pillow_kwargs['pillow_layout_spec'] = {
                **(pillow_kwargs.get('pillow_layout_spec') or {}),
                **dossier_spec,
            }

        # Posicao do logo escolhida no modal vence — cadeia de prioridade:
        # user > orquestrador (layout_document) > dossie/spec legado.
        user_logo_pos = (ctx.get('logo_position') or '').strip()
        if user_logo_pos:
            # spec legado (caminho sem layout_document)
            _spec = pillow_kwargs.get('pillow_layout_spec') or {}
            _spec['logo_position'] = user_logo_pos
            pillow_kwargs['pillow_layout_spec'] = _spec
            # layout_document do orquestrador: sobrepoe o elemento 'logo'
            if layout_document:
                _coords = _logo_pos_to_coords(user_logo_pos)
                if _coords:
                    elements = layout_document.get('elements') or []
                    for el in elements:
                        if (el.get('role') or '').lower() == 'logo':
                            el['x_pct'] = _coords['x_pct']
                            el['y_pct'] = _coords['y_pct']
                            break
                    else:
                        elements.append({
                            'role': 'logo', **_coords, 'width_pct': 15,
                        })
                    layout_document['elements'] = elements
                    logger.info(
                        '[posts.local] logo_position do user (%s) sobreposto no layout_document',
                        user_logo_pos,
                    )

    # Grafismos DETERMINISTICOS (fideis ao dossie): para cada KB ref com
    # aspecto 'grafismos', constroi elementos role='grafismo' usando posicoes
    # exatas de grid.zonas + cores reais de assets_grafismos + faixa branca de
    # logo_na_referencia. Remove quaisquer grafismos emitidos pelo orquestrador.
    if layout_document and kb_dossiers:
        deterministic_grafismos = []
        for d in kb_dossiers:
            if 'grafismos' in (d.get('aspects') or []):
                deterministic_grafismos.extend(
                    _grafismos_from_dossier(d.get('dossier') or {})
                )
        if deterministic_grafismos:
            elements = layout_document.get('elements') or []
            elements = [
                e for e in elements
                if (e.get('role') or '').lower() != 'grafismo'
            ]
            layout_document['elements'] = deterministic_grafismos + elements
            logger.info(
                '[posts.local] %d grafismos deterministicos injetados',
                len(deterministic_grafismos),
            )

    # === EXPERIMENT: enviar ref KB de layout/grafismos ao Gemini (start) ===
    # Anexa a imagem da ref KB com aspecto layout_composicao/grafismos como
    # input visual do Gemini. O "o que utilizar" e o proprio DOSSIE que ja
    # extraimos (fatiado pelo aspecto), convertido em brief estruturado.
    # Facil de reverter: deletar este bloco (start..end) restaura comportamento.
    if kb_dossiers:
        try:
            from apps.core.services.s3_service import S3Service
            from apps.knowledge.models import ReferenceImage
            for _d in kb_dossiers:
                _aspects = _d.get('aspects') or []
                if not any(a in _aspects for a in ('layout_composicao', 'grafismos')):
                    continue
                _kb_ref = ReferenceImage.objects.filter(id=_d.get('id')).first()
                if not _kb_ref or not _kb_ref.s3_key:
                    continue
                try:
                    _url = S3Service.generate_presigned_download_url(
                        _kb_ref.s3_key, expires_in=86400
                    )
                except Exception:
                    continue
                _brief = _dossier_to_gemini_brief(
                    _d.get('dossier') or {}, _aspects,
                )
                if not _brief:
                    continue
                references.append({
                    'tipo': 'referencia_layout',
                    'url': _url,
                    'usage_description': _brief,
                })
                logger.info(
                    '[posts.local][EXP] ref KB %s anexada ao Gemini como '
                    'referencia_layout', _kb_ref.id,
                )
        except Exception:
            logger.exception('[posts.local][EXP] falha ao anexar ref KB ao Gemini')
    # === EXPERIMENT: enviar ref KB de layout/grafismos ao Gemini (end) ===

    try:
        result = generate_post_image(
            post=post,
            references=references,
            paleta=paleta,
            tipografia=tipografia,
            publico_alvo=publico_alvo,
            marketing_input_summary=marketing_input_summary,
            formato_px=formato_px,
            product_analyses=product_analyses,
            text_render_mode=text_render_mode,
            brand_keywords=brand_keywords,
            spatial_instructions=spatial_instructions,
            references_usage_general=refs_usage_general,
            kb_translations=kb_translations,
            layout_document=layout_document,
            image_prompt_override=orchestrator_image_prompt or None,
            **pillow_kwargs,
        )
    except Exception as exc:
        logger.exception('[posts.local] Falha Gemini post_id=%s', post_id)
        post.status = 'failed'
        post.save(update_fields=['status'])
        raise self.retry(exc=exc)

    # ============================================================
    # DESIGNER-CRITIC — olhos novos sobre a arte renderizada.
    # Itera ate 3x. Em cada iteracao: critic ve o PNG atual + layout,
    # propoe edits cirurgicos, aplicamos, re-renderizamos (Pillow sobre
    # raw, sem chamar Gemini de novo). Custo: 0-3 calls de critic ($0.03-0.05/cada).
    # ============================================================
    critique_iterations = []
    if (orchestration_output and layout_document
            and result.get('raw_png_bytes') and result.get('png_bytes')):
        try:
            from apps.posts.services.post_critic import critique
            from apps.posts.services.gemini_image_generator import render_layout_document
            _max_iter = 3
            current_png = result['png_bytes']
            raw_png = result['raw_png_bytes']
            for _it in range(1, _max_iter + 1):
                cresp = critique(
                    post=post,
                    orchestration=orchestration_output,
                    layout_document=layout_document,
                    png_preview_bytes=current_png,
                    paleta=paleta,
                    iteration=_it,
                    max_iterations=_max_iter,
                )
                if not cresp:
                    break
                critique_iterations.append({
                    'iteration': _it,
                    'approved': bool(cresp.get('approved')),
                    'rationale': cresp.get('rationale', ''),
                    'edits': cresp.get('edits', []),
                    'usage': cresp.get('usage', {}),
                })
                # Loga custo da iteracao do critico no ai_usage_log
                try:
                    _record_ai_usage(
                        post,
                        step='text_generation',
                        model=cresp.get('model', 'claude-sonnet-4-6'),
                        usage_dict=cresp.get('usage') or {},
                        purpose=f'critic_iter_{_it}',
                    )
                except Exception:
                    logger.exception('[posts.local] falha logar uso critico iter %d', _it)
                if cresp.get('approved'):
                    break
                applied = _apply_layout_edits(
                    layout_document, cresp.get('edits') or []
                )
                if applied == 0:
                    break  # nada a aplicar, sai
                # Re-render Pillow sobre o raw (sem novo Gemini)
                try:
                    current_png = render_layout_document(
                        raw_png,
                        elements=layout_document.get('elements') or [],
                        paleta=paleta,
                        fonts={
                            'titulo': pillow_kwargs.get('pillow_title_font_path'),
                            'subtitulo': pillow_kwargs.get('pillow_subtitle_font_path'),
                            'cta': pillow_kwargs.get('pillow_title_font_path'),
                        },
                        logo_url=pillow_kwargs.get('pillow_logo_url'),
                    )
                except Exception:
                    logger.exception('[posts.local] re-render apos critic falhou')
                    break
            # Atualiza o png final com o ultimo render
            result['png_bytes'] = current_png
            # Persiste trail no ctx
            ctx['critique_iterations'] = critique_iterations
            ctx['orchestration'] = orchestration_output
            post.local_pipeline_context = ctx
            post.save(update_fields=['local_pipeline_context'])
            # Re-persiste _layout_elements (critic pode ter mutado posicoes/cores
            # via _apply_layout_edits). Garantia idempotente para o modal Arte Final.
            try:
                _final_els = (layout_document or {}).get('elements') or []
                if _final_els:
                    _dp = post.designer_payload or {}
                    _dp['_layout_elements'] = _final_els
                    post.designer_payload = _dp
                    post.save(update_fields=['designer_payload'])
            except Exception:
                logger.exception('[posts.local] falha re-persistir _layout_elements pos-critic')
            logger.info(
                '[posts.local] designer-critic: %d iteracoes',
                len(critique_iterations),
            )
        except Exception:
            logger.exception('[posts.local] designer-critic falhou — segue sem')

    # Upload PNG no S3
    s3_key, s3_url = _upload_image_to_s3(
        org_id=post.organization.id,
        post_id=post.id,
        png_bytes=result['png_bytes'],
        mime_type=result.get('mime_type', 'image/png'),
    )

    # Upload do PNG CRU (cena do Gemini SEM texto) — base do canvas editavel
    raw_bytes = result.get('raw_png_bytes')
    if raw_bytes:
        try:
            raw_key, raw_url = _upload_image_to_s3(
                org_id=post.organization.id,
                post_id=post.id,
                png_bytes=raw_bytes,
                mime_type='image/png',
            )
            post.raw_image_s3_key = raw_key
            post.raw_image_s3_url = raw_url
        except Exception:
            logger.exception('[posts.local] falha upload raw png')

    # Cria PostImage (model FK que o frontend le via post.images.all())
    # Equivalente ao que o callback N8N faz em views_webhook.py
    from apps.posts.models import PostImage
    from django.db.models import Max
    max_order = post.images.aggregate(Max('order'))['order__max']
    next_order = (max_order if max_order is not None else -1) + 1
    PostImage.objects.create(
        post=post,
        s3_key=s3_key,
        s3_url=s3_url,
        order=next_order,
    )

    # Atualiza Post (campos principais + lista json)
    post.image_s3_key = s3_key
    post.image_s3_url = s3_url
    post.has_image = True
    post.ia_model_image = result['model']
    img_entry = {
        's3_key': s3_key,
        'url': s3_url,
        'width': post.image_width or None,
        'height': post.image_height or None,
    }
    existing = post.generated_images if isinstance(post.generated_images, list) else []
    existing.append(img_entry)
    post.generated_images = existing
    post.status = 'image_ready'
    # Salvaguarda final: se layout_document tem elements e o designer_payload
    # em memoria perdeu (suspeita de race com refresh_from_db do _record_ai_usage),
    # re-injeta antes do save geral. Idempotente.
    try:
        _final_els = (layout_document or {}).get('elements') or []
        if _final_els and not (post.designer_payload or {}).get('_layout_elements'):
            _dp = post.designer_payload or {}
            _dp['_layout_elements'] = _final_els
            post.designer_payload = _dp
            logger.info(
                '[posts.local] _layout_elements re-injetado antes do save final (%d els)',
                len(_final_els),
            )
    except Exception:
        logger.exception('[posts.local] falha re-injetar _layout_elements pre-save')
    post.save()

    # Loga custo
    _log_usage_gemini(
        post,
        result['model'],
        result.get('cost_usd', 0),
        usage_metadata=result.get('usage') or {},
    )

    logger.info(
        '[posts.local] generate_post_image_task OK post_id=%s s3_key=%s cost=$%s',
        post_id, s3_key, result.get('cost_usd'),
    )

    return {
        'success': True,
        'post_id': post_id,
        's3_key': s3_key,
        's3_url': s3_url,
        'cost_usd': result.get('cost_usd'),
    }


@shared_task(
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def regenerate_background_task(self, post_id: int, message: str):
    """
    Regera APENAS a imagem de fundo (sem texto) usando o Gemini com a imagem
    atual + a mensagem do usuario como ajuste. Nao altera _layout_elements,
    nao re-roda strategist/copywriter/designer/critic. O usuario continua
    com seus textos, posicoes e edicoes intactas.

    Estrategia:
      1. Baixa a raw_image atual do S3 (PNG cru do Gemini, sem texto).
      2. Monta prompt: a imagem como image_part + texto curto em EN
         pedindo a alteracao do usuario, reforcando "no text in image".
      3. Chama Gemini Image API direto (sem passar por generate_post_image).
      4. Sobe novo PNG no S3.
      5. Empilha o raw_image_s3_key antigo em local_pipeline_context.background_history.
      6. Atualiza post.raw_image_s3_key/url.
    """
    import os as _os
    import urllib.request as _ur
    import urllib.error as _ue
    import base64 as _b64
    import json as _json
    from apps.posts.models import Post as _Post
    from apps.posts.services.gemini_image_generator import (
        _resolved_endpoint, _extract_image_from_response, _download_to_base64,
    )
    from apps.core.services.s3_service import S3Service

    logger.info('[regen_bg] iniciada post_id=%s msg=%s', post_id, (message or '')[:80])

    try:
        post = _Post.objects.select_related('organization', 'post_format').get(id=post_id)
    except _Post.DoesNotExist:
        logger.error('[regen_bg] post nao existe id=%s', post_id)
        return {'success': False, 'error': 'post_not_found'}

    if not post.raw_image_s3_key:
        logger.error('[regen_bg] post sem raw_image_s3_key id=%s', post_id)
        return {'success': False, 'error': 'no_raw_image'}

    # 1. Baixa raw_image atual (presigned 5min)
    try:
        cur_url = S3Service.generate_presigned_download_url(post.raw_image_s3_key, expires_in=300)
    except Exception:
        logger.exception('[regen_bg] presigned current raw falhou')
        return {'success': False, 'error': 'presign_failed'}

    cur_b64, cur_mime = _download_to_base64(cur_url)
    if not cur_b64:
        logger.error('[regen_bg] falha baixar imagem atual post=%s', post_id)
        return {'success': False, 'error': 'download_failed'}

    # 2. Monta prompt: simples e direto
    user_msg = (message or '').strip()
    prompt_text = (
        'Modify the attached image according to the user request below. '
        'Keep the same subject, composition style and brand feel — apply ONLY the requested change.\n\n'
        f'USER REQUEST (Portuguese): "{user_msg}"\n\n'
        'STRICT RULES:\n'
        '- Output an image only. No text, no typography, no letters, no logos anywhere.\n'
        '- Keep the aspect ratio of the original image.\n'
        '- Preserve identity of any product or person visible in the attached image.\n'
    )

    api_key = _os.environ.get('GEMINI_API_KEY')
    if not api_key:
        logger.error('[regen_bg] GEMINI_API_KEY ausente')
        return {'success': False, 'error': 'no_api_key'}

    payload = {
        'contents': [{
            'parts': [
                {'inline_data': {'mime_type': cur_mime or 'image/png', 'data': cur_b64}},
                {'text': prompt_text},
            ],
        }],
        'generationConfig': {
            'responseModalities': ['IMAGE', 'TEXT'],
            'candidateCount': 1,
            'temperature': 0.5,
        },
    }

    model_used, endpoint = _resolved_endpoint()
    body = _json.dumps(payload).encode('utf-8')
    req = _ur.Request(
        endpoint, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': api_key},
    )
    try:
        with _ur.urlopen(req, timeout=180) as resp:
            response_data = resp.read()
    except _ue.HTTPError as exc:
        err_body = exc.read().decode('utf-8', errors='ignore')[:500]
        logger.error('[regen_bg] Gemini HTTP %s: %s', exc.code, err_body)
        return {'success': False, 'error': f'gemini_http_{exc.code}', 'detail': err_body}
    except Exception:
        logger.exception('[regen_bg] falha chamada Gemini post=%s', post_id)
        return {'success': False, 'error': 'gemini_call_failed'}

    response_json = _json.loads(response_data.decode('utf-8'))
    png_bytes, mime_type = _extract_image_from_response(response_json)
    if not png_bytes:
        logger.error('[regen_bg] sem imagem na resposta Gemini post=%s', post_id)
        return {'success': False, 'error': 'no_image_returned'}

    # 3. Upload novo PNG no S3
    new_key, new_url = _upload_image_to_s3(
        org_id=post.organization.id,
        post_id=post.id,
        png_bytes=png_bytes,
        mime_type=mime_type or 'image/png',
    )

    # 4. Empilha antigo no history, atualiza raw_image_s3_key
    old_key = post.raw_image_s3_key
    old_url = post.raw_image_s3_url or ''
    ctx = post.local_pipeline_context or {}
    history = ctx.get('background_history') or []
    history.append({
        's3_key': old_key,
        's3_url': old_url,
        'replaced_at': dj_tz_now_isoformat(),
        'user_request': user_msg[:300],
    })
    # Limita a 10 versoes anteriores
    ctx['background_history'] = history[-10:]
    post.local_pipeline_context = ctx
    post.raw_image_s3_key = new_key
    post.raw_image_s3_url = new_url
    post.save(update_fields=['raw_image_s3_key', 'raw_image_s3_url', 'local_pipeline_context'])

    # 5. Loga custo
    try:
        usage = (response_json.get('usageMetadata') or {})
        cost_in = int(usage.get('promptTokenCount', 0) or 0) * 0.10 / 1_000_000
        cost_out = 0.04  # flat por imagem
        cost = round(cost_in + cost_out, 6)
        _log_usage_gemini(post, model_used, cost, usage_metadata=usage)
    except Exception:
        logger.exception('[regen_bg] falha logar custo')

    # 6. Re-renderiza a PostImage "editavel" com o novo raw + elements atuais.
    # Isso garante que a miniatura/imagem grande no card do post reflitam a
    # nova foto (compondo com os textos/logo que o user editou no modal).
    try:
        _refresh_editable_post_image(post)
    except Exception:
        logger.exception('[regen_bg] falha refresh PostImage editavel post=%s', post_id)

    logger.info('[regen_bg] OK post=%s old=%s new=%s', post_id, old_key, new_key)
    return {
        'success': True,
        'post_id': post_id,
        'old_s3_key': old_key,
        'new_s3_key': new_key,
        'new_s3_url': new_url,
    }


def _refresh_editable_post_image(post):
    """Rerenderiza a versao composta (raw + textos + logo) via Playwright e
    atualiza a PostImage "editavel" (s3_key == post.image_s3_key) + o proprio
    post.image_s3_key. Usado apos regenerate_background_task para que as
    miniaturas no card do post reflitam a nova foto."""
    import asyncio as _asyncio
    from apps.posts.models import PostImage as _PostImage
    from apps.posts.views_overlay import (
        _get_elements, _get_raw_image_url, _get_logo_url, _get_canvas,
        _get_font_paths, _download_as_data_uri, _playwright_screenshot,
        _prepare_stickers_for_export,
    )
    from apps.posts.services.html_renderer import build_html

    els = _get_elements(post)
    if not els:
        logger.info('[regen_bg] post sem _layout_elements, pula refresh')
        return

    raw_url = _get_raw_image_url(post)
    logo_url = _get_logo_url(post)
    cw, ch = _get_canvas(post)
    font_paths = _get_font_paths(post)
    raw_data = _download_as_data_uri(raw_url)
    logo_data = _download_as_data_uri(logo_url)
    if not raw_data:
        logger.warning('[regen_bg] raw_data vazio no refresh')
        return

    els_prepared = _prepare_stickers_for_export(els)
    html = build_html(els_prepared, raw_data, logo_data, cw, ch, font_paths)
    png_bytes = _asyncio.run(_playwright_screenshot(html, cw, ch))

    new_key, new_url = _upload_image_to_s3(
        org_id=post.organization.id,
        post_id=post.id,
        png_bytes=png_bytes,
        mime_type='image/png',
    )

    # Atualiza a PostImage "editavel" (atual). Se nao houver, cria uma.
    old_main_key = post.image_s3_key or ''
    editable = post.images.filter(s3_key=old_main_key).first() if old_main_key else None
    if editable:
        editable.s3_key = new_key
        editable.s3_url = new_url
        editable.save(update_fields=['s3_key', 's3_url'])
    else:
        # Sem PostImage casando — cria nova como a "atual"
        from django.db.models import Max
        next_order = ((post.images.aggregate(Max('order'))['order__max'] or -1) + 1)
        _PostImage.objects.create(post=post, s3_key=new_key, s3_url=new_url, order=next_order)

    post.image_s3_key = new_key
    post.image_s3_url = new_url
    post.has_image = True
    post.save(update_fields=['image_s3_key', 'image_s3_url', 'has_image'])
    logger.info('[regen_bg] PostImage editavel atualizada post=%s key=%s', post.id, new_key)


def dj_tz_now_isoformat() -> str:
    from django.utils import timezone as _tz
    return _tz.now().isoformat()


def _analyze_products_in_references(references, brand_context: str = '') -> list:
    """
    Para cada referencia com tipo contendo 'produto', baixa a imagem e
    chama Claude Vision para gerar descricao estruturada (subject preservation).
    brand_context: string descrevendo a marca/segmento (ajuda Claude a
        identificar modelo/versao exato do produto).
    Retorna lista de dicts (1 por produto, na mesma ordem em que aparecem
    nas references), cada um com:
      {product_name, distinctive_features, keep_unchanged_list, ...}

    Custo: ~$0.005 por produto. Falhas individuais nao quebram a task
    (descricao vazia entra como fallback no prompt).
    """
    from apps.posts.services.claude_post_generator import (
        analyze_product_image, download_image_bytes,
    )
    analyses = []
    for ref in references:
        tipo = str(ref.get('tipo', '')).lower()
        if 'produto' not in tipo:
            continue
        url = ref.get('url')
        if not url:
            analyses.append({})
            continue
        try:
            img_bytes, mime = download_image_bytes(url)
            if not img_bytes:
                analyses.append({})
                continue
            result = analyze_product_image(
                img_bytes, mime_type=mime, brand_context=brand_context,
            )
            analyses.append(result.get('structured') or {})
            logger.info(
                '[posts.local] product vision analysis: %s (%s tokens)',
                (result.get('structured') or {}).get('product_name', '?'),
                (result.get('usage') or {}).get('total_tokens', '?'),
            )
        except Exception:
            logger.exception('[posts.local] Falha em analyze_product_image')
            analyses.append({})
    return analyses


def _layout_plan_to_spec(layout_plan: dict, fallback: dict = None) -> dict:
    """
    Converte layout_plan (formato do orchestrator) em layout_spec (formato
    consumido pelo apply_text_overlay do Pillow).

    Schema layout_plan (do orchestrator):
      {
        "title_zone": {"position": "top-left", "width_pct": 60, "height_pct": 22, ...},
        "subtitle_zone": {...},
        "logo_zone": {"position": "top-right", "width_pct": 12, "height_pct": 8},
        "cta_zone": {"position": "bottom-center", ...},
        "main_subject_zone": {...}
      }

    Schema layout_spec (do Pillow):
      {
        "title_position": "top-left", "title_size_pct": 8, "title_weight": "bold",
        "subtitle_offset": "below_title", "subtitle_size_pct": 3,
        "logo_position": "top-right", "logo_size_pct": 12,
        "cta_style": "pill", "cta_position": "bottom-center",
        "alignment": "left", "padding_pct": 5,
      }
    """
    base = dict(fallback or {})

    title_zone = layout_plan.get('title_zone') or {}
    if title_zone:
        base['title_position'] = title_zone.get('position', base.get('title_position', 'top-left'))
        # height_pct da zona vira title_size_pct (proporcional, com cap)
        h = float(title_zone.get('height_pct', 22))
        base['title_size_pct'] = max(6, min(h * 0.35, 12))  # 35% da altura da zona = tamanho da fonte

    subtitle_zone = layout_plan.get('subtitle_zone') or {}
    if subtitle_zone:
        h_sub = float(subtitle_zone.get('height_pct', 8))
        base['subtitle_size_pct'] = max(2.5, min(h_sub * 0.35, 5))

    logo_zone = layout_plan.get('logo_zone') or {}
    if logo_zone:
        base['logo_position'] = logo_zone.get('position', base.get('logo_position', 'top-right'))
        base['logo_size_pct'] = float(logo_zone.get('width_pct', 12))

    cta_zone = layout_plan.get('cta_zone') or {}
    if cta_zone:
        base['cta_position'] = cta_zone.get('position', base.get('cta_position', 'bottom-center'))

    # Defaults pra completar
    base.setdefault('title_weight', 'bold')
    base.setdefault('title_color_hint', 'auto_contrast')
    base.setdefault('subtitle_offset', 'below_title')
    base.setdefault('subtitle_weight', 'regular')
    base.setdefault('cta_style', 'pill')
    base.setdefault('alignment', 'left')
    base.setdefault('padding_pct', 5)
    base.setdefault('background_treatment', 'none')

    base['source'] = 'orchestrator_layout_plan'
    return base


# ---- Layout a partir do dossie da ref marcada com aspecto 'layout' ----------

_ALIGN_MAP = {
    'esquerda': 'left', 'left': 'left',
    'centro': 'center', 'center': 'center', 'centralizado': 'center',
    'direita': 'right', 'right': 'right',
    'justificado': 'left',  # Pillow nao justifica — trata como left
}


def _norm_align(value, default='left') -> str:
    return _ALIGN_MAP.get(str(value or '').strip().lower(), default)


def _anchor_from_pct(x_pct, y_pct):
    """Mapeia x%/y% da zona para uma das 9 ancoras (logo/cta)."""
    try:
        x, y = float(x_pct), float(y_pct)
    except (TypeError, ValueError):
        return None
    h = 'left' if x < 38 else ('center' if x < 60 else 'right')
    v = 'top' if y < 33 else ('middle' if y < 60 else 'bottom')
    return f'{v}-{h}'


def _find_zone(zonas, *keywords):
    for z in zonas or []:
        name = (z.get('nome') or '').lower()
        cont = (z.get('conteudo') or '').lower()
        if any(k in name or k in cont for k in keywords):
            return z
    return None


def _zone_pct(z):
    if not z:
        return None
    return {
        'x_pct': z.get('x_pct', 0),
        'y_pct': z.get('y_pct', 0),
        'width_pct': z.get('largura_pct') or z.get('width_pct') or 90,
    }


def _aspect_ratio_to_float(ar):
    """'9:16' -> 0.5625 ; '1:1' -> 1.0. None se invalido."""
    try:
        s = str(ar or '')
        if ':' in s:
            w, h = s.split(':', 1)
            h = float(h)
            return round(float(w) / h, 3) if h else None
    except Exception:
        return None
    return None


def _layout_dossier(kb_dossiers):
    """Retorna o dossie da ref marcada com aspecto 'layout_composicao' (ou None)."""
    for d in kb_dossiers or []:
        if 'layout_composicao' in (d.get('aspects') or []):
            return d.get('dossier') or {}
    return None


def _dossier_to_gemini_brief(dossier: dict, aspects: list) -> str:
    """Converte a fatia do dossie (filtrada por aspectos) em brief estruturado
    pra enviar ao Gemini junto com a imagem da referencia. Inclui POSICOES,
    CORES e FORMAS — mas NAO o conteudo de texto (titulos/CTAs sao do nosso
    post). Inclui regras explicitas do que IGNORAR na referencia."""
    if not isinstance(dossier, dict) or not aspects:
        return ''
    lines = []
    if 'layout_composicao' in aspects:
        lines.append('GRID/ZONAS (replicar com as MESMAS porcentagens):')
        grid = dossier.get('grid') or {}
        for z in (grid.get('zonas') or []):
            nome = z.get('nome', '?')
            x = z.get('x_pct', 0); y = z.get('y_pct', 0)
            w = z.get('largura_pct', 0); h = z.get('altura_pct', 0)
            conteudo = z.get('conteudo', '')
            lines.append(f'  - {nome}: x={x}%, y={y}%, w={w}%, h={h}% ({conteudo})')
        comp = dossier.get('composicao') or {}
        if comp.get('enquadramento'):
            lines.append(f"COMPOSICAO: enquadramento={comp.get('enquadramento')}")
        if comp.get('foco_principal'):
            lines.append(f"  foco={comp.get('foco_principal')}")
        lnr = dossier.get('logo_na_referencia') or {}
        if lnr.get('presente'):
            lines.append(
                f"LOGO: posicao={lnr.get('posicao')}, fundo={lnr.get('fundo')}"
            )
        tx = dossier.get('texto_x_imagem') or {}
        if tx.get('blocos'):
            lines.append(
                'POSICIONAMENTO DOS TEXTOS (cor + alinhamento — o CONTEUDO sera '
                'sobreposto depois por nos, NAO replique o texto da referencia):'
            )
            for b in tx['blocos']:
                lines.append(
                    f"  - {b.get('papel')}: cor={b.get('cor')}, "
                    f"peso={b.get('peso')}, "
                    f"alinhamento={b.get('alinhamento_paragrafo')}"
                )
    if 'grafismos' in aspects:
        lines.append('GRAFISMOS (replicar FIELMENTE forma e cor):')
        for g in (dossier.get('assets_grafismos') or []):
            lines.append(
                f"  - {g.get('tipo')} cor={g.get('cor')} | "
                f"estilo={g.get('estilo')} | funcao={g.get('funcao')} | "
                f"posicao={g.get('posicao')}"
            )
    lines.append('')
    lines.append('IGNORE COMPLETAMENTE na imagem de referencia:')
    lines.append('  - O TEXTO VISIVEL dentro das faixas e selos (e exemplo).')
    lines.append('  - O sujeito especifico (a comida, o produto especifico).')
    lines.append('  - Detalhes de cenario que nao fazem parte do template.')
    lines.append(
        'TRATE faixas/selos/rodape como CAIXAS VAZIAS — texto e logo serao '
        'sobrepostos depois.'
    )
    return '\n'.join(lines)


def _grafismos_from_dossier(dossier: dict) -> list:
    """Constroi elementos role='grafismo' deterministicos APENAS para
    primitivas que o Pillow desenha bem matematicamente:
      - SELO circular (com texto centralizado por cima)
      - LINHA / DIVISOR reto
    Faixas/bandas (especialmente com canto organico) NAO entram aqui — o
    orquestrador as descreve no image_prompt_final para o Gemini desenhar
    fielmente dentro da cena. Cor EXATA do dossie.
    """
    if not isinstance(dossier, dict):
        return []
    out: list = []
    grid = dossier.get('grid') or {}
    zonas = {(z.get('nome') or '').lower(): z for z in (grid.get('zonas') or [])}

    def _coord(z, key, default):
        if not z:
            return default
        v = z.get(key)
        return v if v is not None else default

    for g in (dossier.get('assets_grafismos') or []):
        tipo = (g.get('tipo') or '').lower()
        cor = g.get('cor') or ''
        funcao = (g.get('funcao') or '').lower()
        zona = None
        if 'call' in funcao or 'cta' in funcao:
            zona = zonas.get('selo_cta')
        elif 'rodape' in funcao or 'footer' in funcao:
            zona = zonas.get('rodape_logo') or zonas.get('rodape')
        # SELO circular: primitiva — Pillow
        if any(t in tipo for t in ('selo', 'circulo', 'badge')):
            out.append({
                'role': 'grafismo', 'forma': 'selo', 'cor': cor,
                'x_pct': _coord(zona, 'x_pct', 8),
                'y_pct': _coord(zona, 'y_pct', 58),
                'width_pct': _coord(zona, 'largura_pct', 22),
                'height_pct': _coord(zona, 'altura_pct', 22),
            })
        # LINHA reta: primitiva — Pillow
        elif any(t in tipo for t in ('linha', 'divisor', 'rule')):
            out.append({
                'role': 'grafismo', 'forma': 'linha', 'cor': cor,
                'x_pct': _coord(zona, 'x_pct', 30),
                'y_pct': _coord(zona, 'y_pct', 94),
                'width_pct': _coord(zona, 'largura_pct', 40),
                'height_pct': _coord(zona, 'altura_pct', 0.3),
            })
        # Faixa/banda/background: organico OU simples — vai pro Gemini (descricao)
    return out


def _hex_to_rgb_t(h):
    h = (h or '').lstrip('#')
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _nearest_palette_hex(hex_str, paleta):
    """Cor observada -> cor mais proxima da paleta da KB (consistencia de marca)."""
    rgb = _hex_to_rgb_t(hex_str)
    if not rgb or not paleta:
        return None
    best, best_d = None, 1e18
    for c in paleta:
        prgb = _hex_to_rgb_t(c.get('hex'))
        if not prgb:
            continue
        d = sum((a - b) ** 2 for a, b in zip(rgb, prgb))
        if d < best_d:
            best_d, best = d, c.get('hex')
    return best


def _dossier_to_layout_spec(dossier: dict, paleta: list = None) -> dict:
    """
    Converte o dossie de uma ref (aspecto layout) em spec parcial do Pillow:
    zonas % de titulo/subtitulo, alinhamento/peso/caixa POR BLOCO, posicao de
    logo/cta. Cores do texto = cor observada na ref SNAPADA na paleta da KB.
    Fontes vem da KB.
    """
    spec = {}
    tx = dossier.get('texto_x_imagem') or {}
    blocos = tx.get('blocos') or []

    def _bloco(papel):
        for b in blocos:
            if (b.get('papel') or '').lower() == papel:
                return b
        return {}

    tb, sb, cb = _bloco('titulo'), _bloco('subtitulo'), _bloco('cta')
    overall = _norm_align(tx.get('alinhamento_paragrafo'), 'left')
    spec['title_align'] = _norm_align(tb.get('alinhamento_paragrafo'), overall)
    spec['subtitle_align'] = _norm_align(sb.get('alinhamento_paragrafo'), overall)
    spec['cta_align'] = _norm_align(cb.get('alinhamento_paragrafo'), overall)
    spec['alignment'] = spec['title_align']
    # Cor do titulo = cor primaria da marca (KB), com fallback de contraste.
    spec['title_color_hint'] = 'brand_primary_safe'
    # Sem painel/overlay do Pillow atras do texto (o fundo limpo vem da cena).
    spec['background_treatment'] = 'none'
    # Subtitulo = neutro legivel (auto contraste), distinto do titulo de marca.
    spec['subtitle_color_hint'] = 'auto_contrast'
    # Se a ref informou a cor de cada bloco, snap na paleta da KB (a cor que a
    # marca usou na referencia, garantida dentro da identidade).
    if paleta:
        tcor = _nearest_palette_hex(tb.get('cor'), paleta)
        if tcor:
            spec['title_color'] = tcor
        scor = _nearest_palette_hex(sb.get('cor'), paleta)
        if scor:
            spec['subtitle_color'] = scor
    if (tb.get('peso') or '').lower() in ('bold', 'negrito', 'semibold', 'black'):
        spec['title_weight'] = 'bold'
    if (tb.get('caixa') or '').lower() in ('alta', 'maiuscula', 'uppercase'):
        spec['title_case'] = 'alta'
    if (sb.get('caixa') or '').lower() in ('alta', 'maiuscula', 'uppercase'):
        spec['subtitle_case'] = 'alta'

    zonas = (dossier.get('grid') or {}).get('zonas') or []
    tz = _find_zone(zonas, 'titulo', 'texto_principal', 'título', 'bloco_texto')
    sz = _find_zone(zonas, 'subtitulo', 'texto_secundario', 'subtítulo')
    # subtitulo so e bloco INDEPENDENTE se for uma zona distinta da do titulo
    # (quando titulo+subtitulo compartilham uma zona, ficam colados).
    if sz is not None and tz is not None and (
        sz is tz or (sz.get('x_pct') == tz.get('x_pct') and sz.get('y_pct') == tz.get('y_pct'))
    ):
        sz = None
    lz = _find_zone(zonas, 'logo')
    cz = _find_zone(zonas, 'cta', 'call', 'botao', 'botão')

    if tz:
        spec['title_zone_pct'] = _zone_pct(tz)
        if tz.get('altura_pct'):
            # zona de titulo isolada -> fonte maior; zona compartilhada
            # (titulo+subtitulo) -> fracao menor pra caber os dois. Teto baixo
            # pra o texto NAO dominar a arte (peso de ocupacao da referencia).
            frac = 0.32 if sz is not None else 0.18
            spec['title_size_pct'] = max(5, min(float(tz['altura_pct']) * frac, 10))
    elif tx.get('posicao_texto'):
        spec['title_position'] = tx.get('posicao_texto')

    if sz:
        spec['subtitle_zone_pct'] = _zone_pct(sz)
        if sz.get('altura_pct'):
            spec['subtitle_size_pct'] = max(2.5, min(float(sz['altura_pct']) * 0.45, 6))

    if lz:
        anc = _anchor_from_pct(lz.get('x_pct'), lz.get('y_pct'))
        if anc:
            spec['logo_position'] = anc
        if lz.get('largura_pct'):
            spec['logo_size_pct'] = max(6, min(float(lz['largura_pct']), 25))

    if cz:
        anc = _anchor_from_pct(cz.get('x_pct'), cz.get('y_pct'))
        if anc:
            spec['cta_position'] = anc

    spec['source'] = 'dossier_layout_aspect'
    return spec


def _prepare_pillow_overlay(post, kb, formato_px: str) -> dict:
    """
    Monta os argumentos opcionais do Smart Pillow Overlay:
      - pillow_layout_spec: kb.brand_layout_spec (cached) OU wireframe
        fallback baseado no aspect_ratio do PostFormat.
      - pillow_title_font_path / pillow_subtitle_font_path: fontes resolvidas
        via FontResolver (Typography da KB -> Google Font / CustomFont -> DejaVu)
      - pillow_logo_url: presigned URL do logo selecionado (primeiro do
        local_pipeline_context.selected_logo_ids, ou primary da KB)
    """
    from apps.posts.services.brand_layout_analyzer import analyze_brand_layout_from_references
    from apps.posts.services.layout_wireframes import wireframe_for_aspect
    from apps.posts.services.font_resolver import (
        resolve_font_for_kb, system_dejavu_path,
    )

    out = {}

    # ---- Layout spec --------------------------------------------------
    spec = None
    try:
        spec = analyze_brand_layout_from_references(kb)
    except Exception:
        logger.exception('[posts.local] brand_layout_analyzer falhou — fallback wireframe')
    if not spec:
        aspect = ''
        if post.post_format and post.post_format.aspect_ratio:
            aspect = post.post_format.aspect_ratio
        spec = wireframe_for_aspect(aspect, formato_px)
        spec['source'] = 'wireframe_fallback'
    else:
        spec.setdefault('source', 'analyzed_from_references')
    out['pillow_layout_spec'] = spec

    # ---- Fontes -------------------------------------------------------
    try:
        out['pillow_title_font_path'] = (
            resolve_font_for_kb(kb, usage_filter='titulo', weight='bold')
            or system_dejavu_path('bold')
        )
    except Exception:
        logger.exception('Erro resolvendo title font')
        out['pillow_title_font_path'] = system_dejavu_path('bold')

    try:
        out['pillow_subtitle_font_path'] = (
            resolve_font_for_kb(kb, usage_filter='subtitulo', weight='regular')
            or resolve_font_for_kb(kb, usage_filter='corpo', weight='regular')
            or resolve_font_for_kb(kb, usage_filter='texto', weight='regular')
            or system_dejavu_path('regular')
        )
    except Exception:
        logger.exception('Erro resolvendo subtitle font')
        out['pillow_subtitle_font_path'] = system_dejavu_path('regular')

    # ---- Logo URL -----------------------------------------------------
    out['pillow_logo_url'] = _resolve_logo_url_for_overlay(post, kb)

    return out


def _resolve_logo_url_for_overlay(post, kb):
    """Retorna presigned URL do logo selecionado pelo user (ou primario da KB)."""
    if not kb:
        return None
    from apps.core.services.s3_service import S3Service

    ctx = post.local_pipeline_context or {}
    selected_ids = ctx.get('selected_logo_ids') or []

    try:
        if selected_ids:
            logo = kb.logos.filter(id__in=selected_ids).first()
        else:
            logo = kb.logos.filter(is_primary=True).first() or kb.logos.first()
    except Exception:
        return None
    if not logo or not logo.s3_key:
        return None
    try:
        return S3Service.generate_presigned_download_url(logo.s3_key, expires_in=3600)
    except Exception:
        return logo.s3_url or None


def _brand_keywords_from_kb(kb) -> list:
    """
    Termos de MARCA/MODELO a sanitizar na CENA enviada ao Gemini (citar marca
    ativa priors). CONSERVADOR de proposito: nome da empresa + tokens com
    digito (modelos, ex: TM7) + acronimos all-caps curtos. NAO inclui palavras
    genericas (ex: "Cozinha", "Robot") pra nao quebrar a descricao do ambiente.
    Funciona para qualquer empresa (le da KB dinamicamente).
    """
    import re as _re
    if not kb:
        return []
    # Palavras genericas que NUNCA devem ser tratadas como marca
    stop = {
        'de', 'da', 'do', 'e', 'a', 'o', 'os', 'as', 'um', 'uma', 'que',
        'para', 'com', 'em', 'robot', 'robo', 'cozinha', 'kitchen', 'maquina',
        'aparelho', 'produto', 'equipamento', 'multifuncional', 'inteligente',
    }
    keywords = set()
    # Nome da empresa = marca por definicao (tokens com >=3 chars, nao-stop)
    for w in str(kb.nome_empresa or '').split():
        w = w.strip()
        if len(w) >= 3 and w.lower() not in stop:
            keywords.add(w)
    # Descricao do produto: SO modelos (token com digito) ou acronimos all-caps
    desc = (kb.descricao_produto or '')[:500]
    for tok in _re.findall(r'\b[A-Za-z0-9]{2,}\b', desc):
        if tok.lower() in stop:
            continue
        if any(c.isdigit() for c in tok):          # ex: TM7, TM6
            keywords.add(tok)
        elif tok.isupper() and 2 <= len(tok) <= 6:  # ex: acronimos de marca
            keywords.add(tok)
    return sorted(keywords)


def _brand_context_for_vision(post) -> str:
    """
    Monta uma string curta com contexto da marca para ajudar Claude Vision
    a identificar produto especifico (ex: 'Thermomix - robos de cozinha Vorwerk').
    Usa nome_empresa + descricao_produto da KB se disponivel.
    """
    from apps.knowledge.models import KnowledgeBase
    kb = KnowledgeBase.objects.filter(organization=post.organization).first()
    if not kb:
        return ''
    parts = []
    if kb.nome_empresa:
        parts.append(kb.nome_empresa)
    if kb.descricao_produto:
        parts.append(kb.descricao_produto[:200])
    return ' — '.join(parts)


def _kb_colors(kb) -> list:
    if not kb:
        return []
    try:
        return [
            {
                'nome': c.name,
                'hex': c.hex_code,
                'tipo': c.color_type or 'primary',
            }
            for c in kb.colors.all().order_by('order')
        ]
    except Exception:
        return []


def _kb_typography(kb) -> list:
    if not kb:
        return []
    try:
        out = []
        for f in kb.typography_settings.all().order_by('order'):
            nome = (
                f.google_font_name if f.font_source == 'google'
                else (f.custom_font.name if f.custom_font else '')
            )
            out.append({
                'uso': f.usage,
                'origem': f.font_source or 'google',
                'nome': nome,
                'peso': f.google_font_weight if f.font_source == 'google' else 'regular',
            })
        return out
    except Exception:
        return []


def _kb_summary_marketing(kb) -> str:
    """Recupera marketing_input_summary do n8n_compilation, fallback string vazia."""
    if not kb:
        return ''
    compilation = getattr(kb, 'n8n_compilation', None)
    if isinstance(compilation, dict):
        return compilation.get('marketing_input_summary') or ''
    return ''


def _formato_px(post) -> str:
    if post.post_format and post.post_format.width and post.post_format.height:
        return f'{post.post_format.width}x{post.post_format.height}'
    if post.image_width and post.image_height:
        return f'{post.image_width}x{post.image_height}'
    return '1080x1080'


def dj_tz_now_iso() -> str:
    """Atalho para timezone-aware ISO timestamp."""
    from django.utils import timezone as dj_tz
    return dj_tz.now().isoformat()


def _collect_references(kb, post, text_render_mode: str = 'inline') -> list:
    """
    Coleta logos + PostReferenceImage como image_parts pro Gemini.

    NOVO comportamento:
    - Logos: em modo 'pillow' o logo e desenhado via Pillow overlay, entao
      e EXCLUIDO daqui (evita logo duplicado). Em outros modos, vai como
      image_part pra que Gemini renderize.
    - Refs da KB: NAO sao mais incluidas como image_parts. Em vez disso,
      passam pelo kb_reference_translator que extrai direcionamento textual.
      Use _collect_kb_refs_for_translation() para isso.
    - Uploads do post: sempre incluidos com fidelidade alta.

    Respeita post.local_pipeline_context:
      - selected_logo_ids: filtra logos
    """
    from apps.core.services.s3_service import S3Service

    ctx = post.local_pipeline_context or {}
    selected_logo_ids = set(ctx.get('selected_logo_ids') or [])

    out = []

    if kb and text_render_mode != 'pillow':
        # Logos — apenas em modo nao-pillow (em pillow, Pillow desenha)
        try:
            qs_logos = kb.logos.all().order_by('-is_primary', 'logo_type')
            for logo in qs_logos:
                if selected_logo_ids and logo.id not in selected_logo_ids:
                    continue
                if logo.s3_key:
                    try:
                        url = S3Service.generate_presigned_download_url(
                            logo.s3_key, expires_in=86400
                        )
                        out.append({'tipo': 'logotipo', 'url': url})
                    except Exception:
                        pass
        except Exception:
            pass

    # Post-specific references (uploads recentes — sempre incluidos)
    try:
        for ref in post.reference_image_files.all():
            if ref.s3_key:
                try:
                    url = S3Service.generate_presigned_download_url(
                        ref.s3_key, expires_in=86400
                    )
                    tipo = (ref.usage_type or 'referencia_post').strip().lower() or 'referencia_post'
                    out.append({
                        'tipo': tipo,
                        'url': url,
                        'usage_description': (ref.usage_description or '').strip(),
                    })
                except Exception:
                    pass
    except Exception:
        pass

    # Refs da KB marcadas como image-first ('produto' ou 'pessoa_modelo') —
    # enviadas como IMAGEM ao Gemini para fidelidade total (produto: mesma
    # caixa/forma/cor; pessoa_modelo: mesmo rosto/cabelo/tom de pele).
    # NAO viram dossie textual no prompt_designer (ver _collect_kb_dossiers).
    try:
        reference_aspects = ctx.get('reference_aspects') or {}
        IMAGE_FIRST_ASPECTS = {'produto', 'pessoa_modelo'}
        # Mapeia ref_id -> tipo (produto/pessoa). pessoa_modelo vira tipo='pessoa'
        # no Gemini (cai no bucket MODEL — mesma identidade) via _normalize_tipo.
        image_first_refs = {}
        for rid, asps in reference_aspects.items():
            asps_norm = _normalize_aspects(asps)
            for aspect in asps_norm:
                if aspect in IMAGE_FIRST_ASPECTS:
                    tipo = 'pessoa' if aspect == 'pessoa_modelo' else 'produto'
                    image_first_refs[str(rid)] = tipo
                    break
        if kb and image_first_refs:
            from apps.knowledge.models import ReferenceImage
            prod_refs = ReferenceImage.objects.filter(
                knowledge_base=kb, id__in=list(image_first_refs.keys())
            )
            for ref in prod_refs:
                if not ref.s3_key:
                    continue
                try:
                    url = S3Service.generate_presigned_download_url(
                        ref.s3_key, expires_in=86400
                    )
                    out.append({
                        'tipo': image_first_refs[str(ref.id)],
                        'url': url,
                        'usage_description': '',
                    })
                except Exception:
                    pass
    except Exception:
        logger.exception('[posts.local] falha ao coletar refs KB image-first')

    return out


_LOGO_POS_COORDS = {
    'top-left':      {'x_pct': 4,  'y_pct': 4},
    'top-center':    {'x_pct': 42, 'y_pct': 4},
    'top-right':     {'x_pct': 78, 'y_pct': 4},
    'middle-left':   {'x_pct': 4,  'y_pct': 46},
    'middle-center': {'x_pct': 42, 'y_pct': 46},
    'middle-right':  {'x_pct': 78, 'y_pct': 46},
    'bottom-left':   {'x_pct': 4,  'y_pct': 90},
    'bottom-center': {'x_pct': 42, 'y_pct': 90},
    'bottom-right':  {'x_pct': 78, 'y_pct': 90},
}


def _logo_pos_to_coords(pos: str) -> dict:
    """Mapeia keyword de posicao (top-left, etc) para x_pct/y_pct."""
    return _LOGO_POS_COORDS.get((pos or '').strip().lower())


def _apply_layout_edits(layout_document: dict, edits: list) -> int:
    """Aplica edits cirurgicos do designer-critic no layout_document.
    Cada edit muda um campo de um elemento, identificado por target_role
    (primeiro elemento com aquele role) ou target_index (posicao na lista).
    Retorna numero de edits aplicados com sucesso."""
    if not (layout_document and edits):
        return 0
    elements = layout_document.get('elements') or []
    applied = 0
    for edit in edits:
        if not isinstance(edit, dict):
            continue
        if 'new_value' not in edit:
            continue
        field = (edit.get('field') or '').strip()
        if not field:
            continue
        target_el = None
        idx = edit.get('target_index')
        role = edit.get('target_role')
        if isinstance(idx, int) and 0 <= idx < len(elements):
            target_el = elements[idx]
        elif role:
            role_lower = str(role).strip().lower()
            for el in elements:
                if (el.get('role') or '').lower() == role_lower:
                    target_el = el
                    break
        if target_el is None:
            logger.warning(
                '[critic] edit nao aplicado (target nao encontrado): %s', edit
            )
            continue
        target_el[field] = edit['new_value']
        applied += 1
    layout_document['elements'] = elements
    return applied


def _normalize_aspects(val) -> list:
    """Normaliza reference_aspects[ref] em lista de strings (aceita str legado)."""
    if isinstance(val, list):
        return [str(a).strip() for a in val if str(a).strip()]
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    return []


def _aspects_for_ref(reference_aspects: dict, ref_id) -> list:
    """Aspectos de uma ref (tenta chave str e int)."""
    return _normalize_aspects(
        reference_aspects.get(str(ref_id)) or reference_aspects.get(ref_id)
    )


def _collect_kb_dossiers(kb, post) -> list:
    """
    Le os dossies visuais (ReferenceImage.visual_analysis) das refs da KB
    selecionadas pelo user no modal. LOOKUP PURO — nao reanalisa o que ja
    tem dossie.

    Gatilho 3 (ultimo recurso): se uma ref selecionada ainda nao foi
    analisada (status != completed), analisa inline AGORA e PERSISTE — a
    info fica garantida para sempre, e da proxima vez e so leitura.

    Retorna lista de dicts {id, aspects, usage_description, dossier}:
      - aspects: lista de aspectos escolhidos no modal (multi-selecao) — a
        INTENCAO que o orchestrator usa para filtrar o dossie.
      - dossier: o JSON objetivo gravado em visual_analysis.

    NAO inclui logos (logo nao tem dossie nesta fase) nem refs marcadas como
    'produto' (essas vao como IMAGEM ao Gemini via _collect_references).
    """
    ctx = post.local_pipeline_context or {}
    selected_ref_ids = list(ctx.get('selected_reference_ids') or [])
    if not (kb and selected_ref_ids):
        return []

    general_guidance = (ctx.get('references_usage_description') or '').strip()
    # aspectos por ref: {ref_id(str/int): ['layout_composicao', 'grafismos', ...]}
    reference_aspects = ctx.get('reference_aspects') or {}

    from apps.knowledge.models import ReferenceImage
    from apps.knowledge.tasks import run_reference_image_analysis

    out = []
    refs = ReferenceImage.objects.filter(
        knowledge_base=kb, id__in=selected_ref_ids
    )
    # Aspectos "image-first" — a ref vai como IMAGEM ao Gemini para fidelidade
    # (NAO entram como dossie textual no prompt_designer). 'produto' eh fidelidade
    # do objeto, 'pessoa_modelo' eh fidelidade da pessoa (mesmo rosto, cabelo,
    # tom de pele, etc — a identidade do tema do user e ignorada).
    IMAGE_FIRST_ASPECTS = {'produto', 'pessoa_modelo'}

    for ref in refs:
        aspects = _aspects_for_ref(reference_aspects, ref.id)
        # Se o unico aspecto eh image-first, a ref vai como image_part e nao
        # entra como dossie. Mantemos o dossier no payload apenas para que o
        # strategist conheca o produto/pessoa, mas o prompt_designer
        # ignora dossiers com aspects ⊆ IMAGE_FIRST_ASPECTS.
        if aspects and all(a in IMAGE_FIRST_ASPECTS for a in aspects):
            if ref.analysis_status == 'completed' and ref.visual_analysis:
                dossier = ref.visual_analysis if isinstance(ref.visual_analysis, dict) else {}
                if dossier:
                    out.append({
                        'id': ref.id,
                        'aspects': aspects,
                        'usage_description': (getattr(ref, 'usage_description', '') or '').strip(),
                        'dossier': dossier,
                    })
            continue
        # Gatilho 3 — fallback inline: analisa e persiste se faltar dossie
        if ref.analysis_status != 'completed' or not ref.visual_analysis:
            try:
                logger.info('[posts.local] ref %s sem dossie — analisando inline', ref.id)
                run_reference_image_analysis(ref)
                ref.refresh_from_db(fields=['visual_analysis', 'analysis_status'])
            except Exception:
                logger.exception('[posts.local] fallback analise ref %s falhou', ref.id)

        dossier = ref.visual_analysis if isinstance(ref.visual_analysis, dict) else {}
        if not dossier:
            continue
        individual_desc = (getattr(ref, 'usage_description', '') or '').strip()
        # 'produto' nao e aspecto de dossie (a ref tambem vai como imagem)
        dossier_aspects = [a for a in aspects if a != 'produto']
        out.append({
            'id': ref.id,
            'aspects': dossier_aspects,
            'usage_description': individual_desc or general_guidance,
            'dossier': dossier,
        })
    return out


def _dossiers_to_translations(kb_dossiers: list) -> list:
    """
    Converte dossies em entradas kb_translations (formato consumido pelo
    gemini builder) SEM IA. Usado apenas como fallback quando o orchestrator
    nao roda — garante que o direcionamento das refs ainda chegue ao Gemini.
    """
    out = []
    for i, d in enumerate(kb_dossiers, 1):
        dossier = d.get('dossier') or {}
        bits = []
        recreation = (dossier.get('recreation_prompt') or '').strip()
        if recreation:
            bits.append(recreation)
        else:
            il = dossier.get('iluminacao') or {}
            comp = dossier.get('composicao') or {}
            il_txt = ' '.join(
                str(il.get(k, '')).strip()
                for k in ('tipo', 'direcao', 'temperatura', 'qualidade')
            ).strip()
            if il_txt:
                bits.append(f'Iluminacao: {il_txt}')
            if comp.get('enquadramento'):
                bits.append(f"Enquadramento: {comp.get('enquadramento')}")
        directives = ' '.join(b for b in bits if b).strip()
        if not directives:
            continue
        out.append({
            'ref_index': i,
            'category': (dossier.get('estilo_visual') or 'referencia').replace(' ', '_').lower(),
            'directives': directives,
            'kb_reference_id': d.get('id'),
            'usage_description_user': d.get('usage_description', ''),
        })
    return out


def _upload_image_to_s3(*, org_id: int, post_id: int, png_bytes: bytes, mime_type: str):
    """Faz upload do PNG gerado no S3 e retorna (s3_key, s3_url presigned)."""
    from apps.core.services.s3_service import S3Service
    from django.utils import timezone as dj_tz

    ext = 'png' if mime_type == 'image/png' else 'jpg'
    ts = int(dj_tz.now().timestamp() * 1000)
    s3_key = f'org-{org_id}/imagensgeradas/{ts}-post{post_id}-generated.{ext}'

    client = S3Service._get_s3_client()
    bucket = S3Service._get_bucket_name() if hasattr(S3Service, '_get_bucket_name') else None
    if not bucket:
        from django.conf import settings as dj_settings
        bucket = dj_settings.AWS_BUCKET_NAME

    client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=png_bytes,
        ContentType=mime_type,
    )

    s3_url = S3Service.generate_presigned_download_url(s3_key, expires_in=86400)
    return s3_key, s3_url


def _log_usage_gemini(post, model: str, cost_usd: float, usage_metadata: dict = None):
    """
    Loga custo Gemini no Post.ai_usage_log.
    usage_metadata: dict do response.usageMetadata do Gemini (tokens reais)
    """
    meta = usage_metadata or {}
    usage_dict = {
        'input_tokens': int(meta.get('promptTokenCount', 0) or 0),
        'output_tokens': int(meta.get('candidatesTokenCount', 0) or 0),
        'total_tokens': int(meta.get('totalTokenCount', 0) or 0),
        'cost_usd': float(cost_usd or 0),
    }
    _record_ai_usage(
        post,
        step='image_generation',
        model=model,
        usage_dict=usage_dict,
        images_generated=1,
    )


def _log_usage(post, model: str, usage: dict, purpose: str):
    """Wrapper retrocompativel — redireciona para _record_ai_usage com purpose."""
    _record_ai_usage(
        post,
        step='text_generation',
        model=model,
        usage_dict=usage,
        purpose=purpose,
        images_generated=0,
    )


def _derive_cache_status(cache_creation: int, cache_read: int) -> str:
    """Classifica a chamada pelo uso de cache.
    - 'cold': escrita de cache (1a da janela, paga premium)
    - 'warm': leitura de cache (chamadas subsequentes na janela, -90%)
    - 'partial': escrita E leitura (raro, parcialmente cacheado)
    - 'no_cache': nenhum cache_control aplicado
    """
    if cache_creation > 0 and cache_read > 0:
        return 'partial'
    if cache_creation > 0:
        return 'cold'
    if cache_read > 0:
        return 'warm'
    return 'no_cache'


def _record_ai_usage(post, *, step: str, model: str, usage_dict: dict,
                     purpose: str = '', images_generated: int = 0):
    """
    Acumula custo de IA no Post + adiciona entry granular no ai_usage_log.

    step: 'text_generation' | 'image_generation' (categoria de billing agregado)
    purpose: 'phase1_text' | 'orchestrator' | 'critic_iter_N' | 'gemini' (granular)
    usage_dict: dict com input_tokens, output_tokens, cost_usd (e demais)
    images_generated: para Gemini, quantas imagens foram geradas (cobranca flat)
    """
    from django.conf import settings as dj_settings
    from django.utils import timezone as dj_tz

    rate = float(getattr(dj_settings, 'USD_TO_BRL_RATE', 5.80))
    cost_usd_dec = Decimal(str(usage_dict.get('cost_usd', 0) or 0))
    cost_brl_dec = cost_usd_dec * Decimal(str(rate))
    cache_read = int(usage_dict.get('cache_read_input_tokens', 0) or 0)
    cache_creation = int(usage_dict.get('cache_creation_input_tokens', 0) or 0)
    cache_status = _derive_cache_status(cache_creation, cache_read)

    entry = {
        'timestamp': dj_tz.now().isoformat(),
        'step': step,
        'purpose': purpose,
        'model': model,
        'input_tokens': int(usage_dict.get('input_tokens', 0) or 0),
        'output_tokens': int(usage_dict.get('output_tokens', 0) or 0),
        'cache_read_tokens': cache_read,
        'cache_creation_tokens': cache_creation,
        'cache_status': cache_status,
        'total_tokens': int(usage_dict.get('total_tokens', 0) or 0),
        'images_generated': int(images_generated or 0),
        'cost_usd': float(cost_usd_dec),
        'cost_brl': float(cost_brl_dec.quantize(Decimal('0.0001'))),
        'usd_to_brl_rate': rate,
    }

    # Re-fetch para evitar race conditions (multiplas chamadas em paralelo)
    try:
        from apps.posts.models import Post
        post.refresh_from_db(fields=[
            'ai_usage_log', 'total_text_cost_usd', 'total_image_cost_usd',
            'total_cost_usd',
        ])
    except Exception:
        pass

    log = post.ai_usage_log if isinstance(post.ai_usage_log, list) else []
    log.append(entry)
    post.ai_usage_log = log

    if step == 'text_generation':
        post.total_text_cost_usd = (post.total_text_cost_usd or Decimal('0')) + cost_usd_dec
    elif step == 'image_generation':
        post.total_image_cost_usd = (post.total_image_cost_usd or Decimal('0')) + cost_usd_dec
    post.total_cost_usd = (post.total_cost_usd or Decimal('0')) + cost_usd_dec

    post.save(update_fields=[
        'ai_usage_log',
        'total_text_cost_usd',
        'total_image_cost_usd',
        'total_cost_usd',
    ])

    logger.info(
        '[ai_cost] post=%s step=%s model=%s tokens_in=%d tokens_out=%d images=%d cost=$%s (R$%s)',
        post.id, step, model,
        entry['input_tokens'], entry['output_tokens'], entry['images_generated'],
        entry['cost_usd'], entry['cost_brl'],
    )


# ============================================================
# PIPELINE NOVO — 2 agentes (copywriter + designer-orquestrador)
# Roda quando POST_USE_NEW_PIPELINE=true.
# ============================================================

def _run_new_pipeline_phase1(post):
    """Phase 1 do pipeline novo (3 agentes): strategist → copywriter → designer.
    Salva strategic_payload + copy_payload + designer_payload + wireframe_png.
    Mantém os campos legados (title/subtitle/cta/caption/image_prompt) preenchidos
    pra UI funcionar.
    """
    from apps.posts.services.strategist_agent import generate_strategy
    from apps.posts.services.copywriter_agent import generate_copy
    from apps.posts.services.designer_agent import generate_design
    from apps.posts.services.designer_payload_adapter import (
        render_wireframe_png, AssetResolver,
    )

    logger.info('[posts.local][new] phase1 iniciada post=%s', post.id)

    kb_summary = _build_kb_summary(post.organization)
    paleta = _kb_colors(_get_kb(post))
    tipografia = _kb_typography(_get_kb(post))

    references = _collect_references(
        kb=_get_kb(post), post=post, text_render_mode='pillow',
    )
    kb_dossiers = _collect_kb_dossiers(kb=_get_kb(post), post=post)
    ctx = post.local_pipeline_context or {}
    modal_choices = {
        'logo_position': ctx.get('logo_position') or '',
        'reference_aspects': ctx.get('reference_aspects') or {},
        'selected_logo_ids': ctx.get('selected_logo_ids') or [],
        'selected_reference_ids': ctx.get('selected_reference_ids') or [],
    }

    # ---- 1º STRATEGIST ----
    strategy_result = generate_strategy(
        post=post, kb_summary=kb_summary, references=references,
        modal_choices=modal_choices,
        paleta=paleta, tipografia=tipografia,
        kb_dossiers=kb_dossiers,
    )
    if not strategy_result:
        logger.error('[posts.local][new] strategist falhou')
        raise RuntimeError('strategist agent retornou None')

    strategic_payload = strategy_result['payload']
    if not isinstance(post.copy_payload, dict):
        post.copy_payload = {}
    post.copy_payload = {
        **(post.copy_payload or {}),
        '_strategic_payload': strategic_payload,
    }
    _record_ai_usage(
        post, step='text_generation', model=strategy_result['model'],
        usage_dict=strategy_result['usage'], purpose='strategist_phase1a',
    )

    blockers = [
        f for f in (strategic_payload.get('flags') or [])
        if f.get('type') == 'blocker'
    ]
    if blockers:
        logger.warning(
            '[posts.local][new] strategist emitiu %d blockers: %s',
            len(blockers), [b.get('message', '?')[:60] for b in blockers],
        )

    copy_direction = strategic_payload.get('copy_direction') or {}

    # ---- 2º COPYWRITER (recebe copy_direction do strategist) ----
    copy_result = generate_copy(
        post=post, kb_summary=kb_summary, references=references,
        copy_direction=copy_direction,
    )
    if not copy_result:
        logger.error('[posts.local][new] copywriter falhou')
        raise RuntimeError('copywriter agent retornou None')

    copy_payload = copy_result['payload']
    post.copy_payload = {
        **copy_payload,
        '_strategic_payload': strategic_payload,
    }
    _record_ai_usage(
        post, step='text_generation', model=copy_result['model'],
        usage_dict=copy_result['usage'], purpose='copywriter_phase1b',
    )

    variant = _pick_copy_variant(copy_payload)
    if variant:
        copy = variant.get('copy') or {}
        post.title = copy.get('headline', '') or ''
        post.subtitle = _first_sentence(copy.get('body', '')) or ''
        post.cta = copy.get('cta', '') or ''
        post.caption = copy.get('body', '') or ''
        hashtags = copy.get('hashtags') or []
        post.hashtags = [
            h if str(h).startswith('#') else f'#{str(h).lstrip("#").strip()}'
            for h in hashtags if h
        ]

    # ---- 3º DESIGNER (recebe strategic_payload + copy_payload) ----
    designer_result = generate_design(
        post=post, copy_payload=copy_payload, kb_summary=kb_summary,
        paleta=paleta, tipografia=tipografia, references=references,
        kb_dossiers=kb_dossiers, modal_choices=modal_choices,
        strategic_payload=strategic_payload,
    )
    if not designer_result:
        logger.error('[posts.local][new] designer falhou — segue só com copy')
        post.status = 'pending'
        post.ia_provider = 'anthropic'
        post.ia_model_text = copy_result['model']
        post.save()
        return {'success': True, 'post_id': post.id, 'phase': 'copy_only'}

    designer_payload = designer_result['payload']
    post.designer_payload = designer_payload
    _record_ai_usage(
        post, step='text_generation', model=designer_result['model'],
        usage_dict=designer_result['usage'], purpose='designer_phase1c',
    )

    image_prompts = designer_payload.get('image_prompts') or []
    if image_prompts:
        post.image_prompt = image_prompts[0].get('prompt', '')

    try:
        meta = designer_payload.get('designer_meta') or {}
        dims = meta.get('dimensions_px') or {}
        canvas_w = int(dims.get('width') or
                       (post.post_format.width if post.post_format else 1080))
        canvas_h = int(dims.get('height') or
                       (post.post_format.height if post.post_format else 1080))
        png_bytes = render_wireframe_png(designer_payload, canvas_w, canvas_h)
        wf_key, wf_url = _upload_image_to_s3(
            org_id=post.organization.id, post_id=post.id,
            png_bytes=png_bytes, mime_type='image/png',
        )
        post.wireframe_s3_key = wf_key
        post.wireframe_s3_url = wf_url
        logger.info(
            '[posts.local][new] wireframe_png salvo: %s (%d bytes)',
            wf_key, len(png_bytes),
        )
    except Exception:
        logger.exception('[posts.local][new] falha gerar wireframe_png')

    post.ia_provider = 'anthropic'
    post.ia_model_text = copy_result['model']
    post.status = 'pending'
    post.save()

    strat_cost = strategy_result['usage'].get('cost_usd', 0)
    copy_cost = copy_result['usage'].get('cost_usd', 0)
    design_cost = designer_result['usage'].get('cost_usd', 0)
    logger.info(
        '[posts.local][new] phase1 OK post=%s strat=$%.4f copy=$%.4f '
        'design=$%.4f total=$%.4f intent=%s img_style=%s',
        post.id, strat_cost, copy_cost, design_cost,
        strat_cost + copy_cost + design_cost,
        (strategic_payload.get('intention') or {}).get('primary', '?'),
        (strategic_payload.get('visual_direction') or {}).get('image_style', '?'),
    )
    return {
        'success': True, 'post_id': post.id, 'phase': 'phase1_complete',
        'designer_iterations': designer_result.get('iterations', 1),
        'intent': (strategic_payload.get('intention') or {}).get('primary'),
        'image_style': (strategic_payload.get('visual_direction') or {}).get('image_style'),
    }


def _get_kb(post):
    from apps.knowledge.models import KnowledgeBase
    return KnowledgeBase.objects.filter(organization=post.organization).first()


def _pick_copy_variant(copy_payload: dict) -> dict:
    """Retorna a variant recomendada (ou v1 fallback)."""
    if not isinstance(copy_payload, dict):
        return {}
    variants = copy_payload.get('variants') or []
    if not variants:
        return {}
    rec_id = copy_payload.get('recommended_variant') or 'v1'
    for v in variants:
        if v.get('id') == rec_id:
            return v
    return variants[0]


def _first_sentence(text: str) -> str:
    """Primeiro fragmento curto pra preencher post.subtitle."""
    if not text:
        return ''
    s = text.strip().split('\n')[0]
    if len(s) > 120:
        s = s[:117].rsplit(' ', 1)[0] + '...'
    return s


def _consume_designer_payload(post, references, ctx):
    """Adapta o designer_payload (px-based, asset_path lógico) ao formato que
    o renderer iamkt entende. Retorna (layout_document, image_prompt)."""
    from apps.posts.services.designer_payload_adapter import (
        wireframe_plan_to_layout_document, AssetResolver,
    )

    designer_payload = post.designer_payload or {}
    meta = designer_payload.get('designer_meta') or {}
    dims = meta.get('dimensions_px') or {}
    canvas_w = int(dims.get('width') or
                   (post.post_format.width if post.post_format else 1080))
    canvas_h = int(dims.get('height') or
                   (post.post_format.height if post.post_format else 1080))

    asset_resolver = AssetResolver(post=post, ctx=ctx, references=references)
    layout_document = wireframe_plan_to_layout_document(
        designer_payload, canvas_w, canvas_h, asset_resolver=asset_resolver,
    )

    # image_prompt principal pro Gemini (primeiro do array)
    image_prompts = designer_payload.get('image_prompts') or []
    image_prompt = ''
    if image_prompts:
        image_prompt = image_prompts[0].get('prompt', '')

    return layout_document, image_prompt


def _parse_formato_px(formato_px: str):
    """'1080x1080' → (1080, 1080)."""
    try:
        w, h = formato_px.split('x')
        return int(w), int(h)
    except Exception:
        return 1080, 1080


def _dominant_bg_from_dossiers(kb_dossiers: list) -> str:
    """Extrai a cor dominante (papel='dominante') da paleta_observada do primeiro
    dossie de referencia. Usado para contraste do subtitulo no layout_engine."""
    for d in (kb_dossiers or []):
        if 'produto' in (d.get('aspects') or []):
            continue
        dossier = d.get('dossier') or {}
        for c in (dossier.get('paleta_observada') or []):
            if c.get('papel') == 'dominante':
                return c.get('hex') or ''
    return ''


# =============================================================================
# PIPELINE SIMPLES (v2) — agente unico via OpenAI gpt-4o-mini
# Fase 1: apenas texto. Disparado por views_gerar_simples (pipeline_used='simple').
# Reaproveita os helpers de contexto do pipeline local (_build_kb_summary etc.).
# =============================================================================
@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def generate_post_simple_task(self, post_id: int):
    """Gera o TEXTO do post via agente unico OpenAI e salva no Post.

    Espelha generate_post_text_task, mas usa simple_post_agent.generate_simple_post
    (1 chamada, gpt-4o-mini). Status final 'pending' (texto pronto). Fase de
    imagem fica para depois.
    """
    from apps.posts.models import Post
    from apps.posts.services.simple_post_agent import generate_simple_post

    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        logger.error('[posts.simple] Post %s nao encontrado', post_id)
        return {'success': False, 'error': 'post_not_found'}

    post.status = 'generating'
    post.save(update_fields=['status'])

    # Contexto reaproveitado do pipeline local
    kb_summary = _build_kb_summary(post.organization)
    formato = _format_to_dict(post.post_format) if post.post_format else {
        'name': post.formats[0] if post.formats else 'feed',
        'aspect_ratio': '1:1',
    }
    logo_urls = list(_logos_from_org(post.organization, post=post))

    ctx = post.local_pipeline_context or {}
    refs_general = (ctx.get('references_usage_description', '') or '').strip()
    reference_descriptions = []
    if refs_general:
        reference_descriptions.append(f'Observacao geral: {refs_general}')
    for r in _reference_images_from_post(post):
        desc = (r.get('usage_description') or '').strip()
        utype = (r.get('usage_type') or '').strip()
        if desc or utype:
            reference_descriptions.append(
                f'{r.get("name") or "imagem"} ({utype or "uso nao informado"}): {desc}'
            )

    try:
        result = generate_simple_post(
            kb_summary=kb_summary,
            rede=post.social_network,
            formato=formato.get('name', 'feed'),
            is_carousel=post.is_carousel,
            image_count=post.image_count,
            tema=post.requested_theme,
            cta_requested=post.cta_requested,
            logo_urls=logo_urls,
            reference_descriptions=reference_descriptions,
        )
    except Exception as exc:
        logger.exception('[posts.simple] Falha OpenAI post_id=%s', post_id)
        # Nao usa status 'failed' (fora dos choices do model). Re-tenta; ao
        # esgotar retries mantem 'generating' para o usuario reabrir.
        raise self.retry(exc=exc)

    structured = result['structured']

    # Normaliza hashtags: garante prefixo '#'
    raw_hashtags = structured.get('hashtags') or []
    structured['hashtags'] = [
        h if str(h).startswith('#') else f'#{str(h).lstrip("#").strip()}'
        for h in raw_hashtags if h
    ]

    post.title = structured.get('title', '') or ''
    post.subtitle = structured.get('subtitle', '') or ''
    post.image_prompt = structured.get('image_prompt', '') or ''
    post.visual_brief = structured.get('visual_brief', '') or ''
    post.caption = structured.get('caption', '') or ''
    post.hashtags = structured.get('hashtags') or []
    post.cta = structured.get('cta_text') or ''
    # Guarda o payload bruto do agente para auditoria/comparacao entre pipelines
    post.copy_payload = {'_simple_agent': structured}
    post.ia_provider = 'openai'
    post.ia_model_text = result['model']
    post.status = 'pending'
    post.save()

    _log_usage(post, result['model'], result['usage'], purpose='generate_post_simple')

    logger.info(
        '[posts.simple] generate_post_simple_task OK post_id=%s tokens_in=%s tokens_out=%s cost=$%s',
        post_id, result['usage'].get('input_tokens'),
        result['usage'].get('output_tokens'), result['usage'].get('cost_usd'),
    )
    return {'success': True, 'post_id': post_id, 'model': result['model'], 'usage': result['usage']}


# --- Fonte unica do mapa "uso -> forma de envio" do pipeline simples ---
# image-first (produto/pessoa) vao como IMAGEM ao Gemini; os demais usos
# (cenario, iluminacao, layout, grafismos, estilo, fundo...) viram SPEC textual.
_IMAGE_FIRST_USES = {'produto', 'pessoa_modelo', 'pessoa'}


def _aspect_delivery(aspect: str) -> str:
    return 'image' if (aspect or '').strip().lower() in _IMAGE_FIRST_USES else 'spec'


def _collect_simple_reference_specs(kb, post) -> list:
    """SPECS textuais das referencias de uso 'spec' (nao image-first).

    - KB: lookup do dossie ja gravado (visual_analysis), filtrado pelo aspecto.
    - Uploads: analise EFEMERA via analyze_reference_image (Claude), sem persistir.
    Retorna [{source, aspects, usage_description, spec}] e loga o custo da analise.
    """
    specs = []
    try:
        for d in _collect_kb_dossiers(kb=kb, post=post):
            spec_aspects = [a for a in (d.get('aspects') or []) if _aspect_delivery(a) == 'spec']
            if spec_aspects and d.get('dossier'):
                specs.append({
                    'source': 'kb', 'aspects': spec_aspects,
                    'usage_description': d.get('usage_description', ''),
                    'spec': d['dossier'],
                })
    except Exception:
        logger.exception('[posts.simple] falha ao coletar dossie KB')

    try:
        from apps.knowledge.services.visual_asset_analyzer import analyze_reference_image
        from apps.core.services.s3_service import S3Service
        for ref in post.reference_image_files.all():
            utype = (ref.usage_type or '').strip().lower()
            if not ref.s3_key or _aspect_delivery(utype) != 'spec':
                continue
            try:
                url = S3Service.generate_presigned_download_url(ref.s3_key, expires_in=3600)
                res = analyze_reference_image(url)
            except Exception:
                logger.exception('[posts.simple] falha analise efemera upload %s', ref.id)
                continue
            if res and res.get('structured'):
                specs.append({
                    'source': 'upload', 'aspects': [utype or 'outro'],
                    'usage_description': (ref.usage_description or '').strip(),
                    'spec': res['structured'],
                })
                if res.get('usage'):
                    _log_usage(post, res.get('model', ''), res['usage'], purpose='simple_ref_analysis')
    except Exception:
        logger.exception('[posts.simple] falha ao analisar uploads')

    return specs


def _specs_directives_text(specs: list) -> str:
    """Resumo textual das specs para anexar ao prompt do fundo."""
    if not specs:
        return ''
    import json as _json
    bits = []
    for s in specs:
        asp = ', '.join(s.get('aspects') or [])
        bits.append(f'- [{asp}] {_json.dumps(s.get("spec") or {}, ensure_ascii=False)[:600]}')
    return 'DIRETRIZES DAS REFERENCIAS (por uso):\n' + '\n'.join(bits)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def generate_post_simple_image_task(self, post_id: int, message: str = ''):
    """Fase 2 do pipeline simples: gera imagem em 3 etapas.

    1. Fundo SEM texto (reuso do fluxo interno: generate_post_image em modo
       pillow -> usa raw_png_bytes, a cena limpa do Gemini).
    2. Agente de Regras (OpenAI) resolve o briefing (modal > KB > criatividade).
    3. Aplicacao de texto via Gemini (Nano Banana): envia fundo + fonte(s)
       .ttf/.otf + logo + textos exatos + briefing -> imagem final.

    Persiste fundo (raw_image_s3_key) e final (image_s3_key) + artefatos de
    debug em local_pipeline_context['simple_image'].
    """
    import base64 as _b64
    from django.utils import timezone as _tz
    from apps.posts.models import Post, PostImage
    from apps.knowledge.models import KnowledgeBase
    from apps.posts.services.gemini_image_generator import (
        generate_post_image, _download_to_base64,
    )
    from apps.posts.services.simple_image_briefing import resolve_briefing
    from apps.posts.services.simple_image_text_apply import apply_text_to_image
    from apps.posts.services.font_resolver import resolve_font_for_kb

    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        logger.error('[posts.simple] Post %s nao existe', post_id)
        return {'success': False, 'error': 'post_not_found'}

    post.status = 'image_generating'
    post.save(update_fields=['status'])

    kb = KnowledgeBase.objects.filter(organization=post.organization).first()
    paleta = _kb_colors(kb)
    tipografia = _kb_typography(kb)
    publico_alvo = (kb.publico_externo if kb else '') or ''
    marketing_input_summary = _kb_summary_marketing(kb)
    formato_px = _formato_px(post)
    # Termos da marca a sanitizar no prompt do fundo: citar a marca (ex.
    # "Thermomix") ativa priors do Gemini e degrada a fidelidade quando ha
    # imagem de produto selecionada. Mesma lista usada no pipeline local.
    brand_keywords = _brand_keywords_from_kb(kb)
    ctx = post.local_pipeline_context or {}

    # Referencias por uso: image-first (produto/pessoa) vao como IMAGEM ao
    # Gemini; os demais usos viram SPEC textual (KB: dossie ja gravado;
    # uploads: analise efemera via Claude). Em modo 'pillow' o logo nao entra.
    _all_refs = _collect_references(kb=kb, post=post, text_render_mode='pillow')
    references = [r for r in _all_refs if _aspect_delivery(r.get('tipo', '')) == 'image']
    reference_specs = _collect_simple_reference_specs(kb=kb, post=post)
    _specs_text = _specs_directives_text(reference_specs)
    bg_image_prompt = post.image_prompt or ''
    if _specs_text:
        bg_image_prompt = f'{bg_image_prompt}\n\n{_specs_text}'

    try:
        # -------- Etapa 1: fundo SEM texto (reuso) --------
        bg_result = generate_post_image(
            post=post,
            references=references,
            paleta=paleta,
            tipografia=tipografia,
            publico_alvo=publico_alvo,
            marketing_input_summary=marketing_input_summary,
            formato_px=formato_px,
            text_render_mode='pillow',
            brand_keywords=brand_keywords,
            image_prompt_override=bg_image_prompt,
        )
        bg_bytes = bg_result.get('raw_png_bytes') or bg_result.get('png_bytes')
        bg_prompt = bg_result.get('prompt_text', '')
        _log_usage_gemini(post, bg_result.get('model', ''), bg_result.get('cost_usd', 0),
                          bg_result.get('usage'))

        raw_key, raw_url = _upload_image_to_s3(
            org_id=post.organization.id, post_id=post.id,
            png_bytes=bg_bytes, mime_type='image/png',
        )
        post.raw_image_s3_key = raw_key
        post.raw_image_s3_url = raw_url
        post.save(update_fields=['raw_image_s3_key', 'raw_image_s3_url'])

        # -------- Etapa 2: agente de regras (briefing) --------
        ref_descs = []
        for r in _reference_images_from_post(post):
            d = (r.get('usage_description') or '').strip()
            t = (r.get('usage_type') or '').strip()
            if d or t:
                ref_descs.append(f'{r.get("name") or "imagem"} ({t or "uso?"}): {d}')
        modal_selections = {
            'has_logo': bool(ctx.get('selected_logo_ids')),
            'logo_position': ctx.get('logo_position') or '',
            'reference_aspects': ctx.get('reference_aspects') or {},
            'references_usage_description': ctx.get('references_usage_description') or '',
            'reference_descriptions': ref_descs,
            # Specs ja extraidas (KB dossie + analise efemera de uploads)
            'reference_specs': reference_specs,
        }
        textos = {'title': post.title or '', 'subtitle': post.subtitle or '', 'cta': post.cta or ''}
        brief_result = resolve_briefing(
            kb_summary=_build_kb_summary(post.organization),
            modal_selections=modal_selections, textos=textos, formato=formato_px,
        )
        briefing = brief_result['briefing']
        _log_usage(post, brief_result['model'], brief_result['usage'], purpose='simple_briefing')

        # -------- Etapa 3: aplicacao de texto via Gemini --------
        font_paths = []
        for usage, weight in (('titulo', 'bold'), ('corpo', 'regular')):
            fp = resolve_font_for_kb(kb, usage_filter=usage, weight=weight)
            if fp and fp not in font_paths:
                font_paths.append(fp)

        logo_cfg = briefing.get('logo') or {}
        logo_position = (logo_cfg.get('posicao') or ctx.get('logo_position') or '')
        logo_png = None
        if logo_cfg.get('usar', bool(ctx.get('selected_logo_ids'))):
            logos = list(_logos_from_org(post.organization, post=post))
            if logos:
                b64, _m = _download_to_base64(logos[0])
                if b64:
                    logo_png = _b64.b64decode(b64)

        apply_result = apply_text_to_image(
            background_png=bg_bytes, font_paths=font_paths, logo_png=logo_png,
            textos=textos, briefing=briefing, formato_px=formato_px,
            logo_position=logo_position,
        )
        final_prompt = apply_result['prompt_text']
        _log_usage_gemini(post, apply_result['model'], apply_result['usage'].get('cost_usd', 0),
                          {'promptTokenCount': apply_result['usage'].get('input_tokens', 0)})

    except Exception as exc:
        logger.exception('[posts.simple] Falha na geracao de imagem post_id=%s', post_id)
        raise self.retry(exc=exc)

    # -------- Persistencia da imagem final --------
    s3_key, s3_url = _upload_image_to_s3(
        org_id=post.organization.id, post_id=post.id,
        png_bytes=apply_result['png_bytes'], mime_type='image/png',
    )
    from django.db.models import Max
    max_order = post.images.aggregate(Max('order'))['order__max']
    PostImage.objects.create(
        post=post, s3_key=s3_key, s3_url=s3_url,
        order=(max_order if max_order is not None else -1) + 1,
    )
    post.image_s3_key = s3_key
    post.image_s3_url = s3_url
    post.has_image = True
    post.ia_model_image = apply_result['model']
    existing = post.generated_images if isinstance(post.generated_images, list) else []
    existing.append({'s3_key': s3_key, 'url': s3_url})
    post.generated_images = existing

    # Artefatos de debug (fundo+final+prompts+json) — area de validacao na tela
    _ctx = post.local_pipeline_context or {}
    _ctx['simple_image'] = {
        'bg_prompt': bg_prompt,
        'final_prompt': final_prompt,
        'rules': briefing,
        'reference_specs': reference_specs,
        'model_bg': bg_result.get('model', ''),
        'model_final': apply_result['model'],
        'created_at': _tz.now().isoformat(),
    }
    post.local_pipeline_context = _ctx
    post.status = 'image_ready'
    post.save()

    logger.info('[posts.simple] generate_post_simple_image_task OK post_id=%s', post_id)
    return {'success': True, 'post_id': post_id, 'final_model': apply_result['model']}
