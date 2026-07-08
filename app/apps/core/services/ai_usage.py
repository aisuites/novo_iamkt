"""
Registro central de eventos de custo de IA (core.AIUsageEvent).

REGRA (dono, 2026-07-08): TODO fluxo que gasta tokens registra um evento —
com ou sem Post — para responder "quanto gastou a org X no mês?".
`record_ai_event` NUNCA levanta exceção: billing não pode derrubar geração.
"""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def record_ai_event(organization, *, step, model, usage_dict, purpose='',
                    post=None, source='', images_generated=0):
    """Grava um AIUsageEvent. usage_dict: input_tokens/output_tokens/
    cache_*_tokens/cost_usd (mesmo formato do _record_ai_usage de posts)."""
    try:
        from django.conf import settings

        from apps.core.models import AIUsageEvent

        if organization is None:
            logger.warning('[ai_event] sem organization — evento descartado '
                           '(step=%s model=%s)', step, model)
            return None
        u = usage_dict or {}
        rate = float(getattr(settings, 'USD_TO_BRL_RATE', 5.80))
        cost_usd = Decimal(str(u.get('cost_usd', 0) or 0))
        return AIUsageEvent.objects.create(
            organization=organization,
            post=post,
            source=source or ('posts' if post is not None else ''),
            pipeline=(getattr(post, 'pipeline_used', '') or '') if post else '',
            step=step,
            purpose=purpose or '',
            model=model or '',
            input_tokens=int(u.get('input_tokens', 0) or 0),
            output_tokens=int(u.get('output_tokens', 0) or 0),
            cache_read_tokens=int(u.get('cache_read_input_tokens', 0) or 0),
            cache_creation_tokens=int(u.get('cache_creation_input_tokens', 0) or 0),
            images_generated=int(images_generated or 0),
            cost_usd=cost_usd,
            cost_brl=(cost_usd * Decimal(str(rate))).quantize(Decimal('0.0001')),
        )
    except Exception:
        logger.exception('[ai_event] falha ao gravar evento (step=%s)', step)
        return None
