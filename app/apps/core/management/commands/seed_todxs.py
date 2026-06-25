"""
Onboarding da TODXS como tenant (dados textuais + paleta).

Cria/atualiza, de forma idempotente:
  - Organization "TODXS"
  - KnowledgeBase (DNA da marca: identidade, tom de voz, vocabulário)
  - 10 cores da ColorPalette (releitura da bandeira LGBTQIA+)
  - 2 papéis de Typography (placeholders — o arquivo .ttf/.otf entra na etapa 2)

NÃO faz upload de assets (logo, grafismo do "X", fotos de referência): isso
depende de arquivos + S3 e é feito numa segunda etapa.

NÃO cria migrations — apenas dados. Seguro para rodar em produção.

Fonte do conteúdo: skill `todxs-social-posts` (brand-spec + tone-of-voice).

Uso:
    python manage.py seed_todxs --dry-run
    python manage.py seed_todxs
    python manage.py seed_todxs --owner-email pessoa@exemplo.com --plan premium
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

from apps.core.models import Organization
from apps.knowledge.models import KnowledgeBase, ColorPalette, Typography

User = get_user_model()


# --- Conteúdo da marca (extraído da skill todxs-social-posts) ---------------

KB_FIELDS = {
    "nome_empresa": "TODXS",
    "descricao_produto": (
        "A TODXS é uma ONG dedicada ao empoderamento da comunidade "
        "LGBTI+/LGBTQIA+ no Brasil. Atua para dar protagonismo às pessoas da "
        "comunidade, com projetos sociais nos eixos de cidadania, "
        "empregabilidade, empreendedorismo e equidade — gerando "
        "representatividade, acesso a espaços de poder e cuidado com as pessoas."
    ),
    "missao": (
        "Empoderar a comunidade LGBTI+/LGBTQIA+ dando protagonismo às suas "
        "histórias — narrativas que aproximam, conectam e dão protagonismo às "
        "pessoas da comunidade."
    ),
    "valores": (
        "Representatividade real, protagonismo, equidade (inclusive racial), "
        "diversidade de existências, dignidade, pertencimento, acesso a espaços "
        "de poder e influência, e cuidado com as pessoas."
    ),
    "publico_externo": (
        "Comunidade LGBTI+/LGBTQIA+ em toda a sua diversidade (raça, corpo, "
        "idade, expressão de gênero) e aliados(as) da causa; parceiros, "
        "apoiadores e a sociedade civil engajada em diversidade e inclusão."
    ),
    "posicionamento": (
        "Estética editorial com releitura do jornal LGBTQIA+ Lampião da Esquina "
        "(anos 70): tipografia protagonista, manchetes diretas e com peso, cores "
        "da bandeira LGBTQIA+ e o 'X' como elemento central. Comunicação "
        "afirmativa que coloca a pessoa/comunidade como sujeito, nunca como objeto."
    ),
    "diferenciais": (
        "Identidade visual proprietária construída sobre o grafismo do 'X' "
        "(máscara de foto, blobs orgânicos, selo) e uma hierarquia tipográfica "
        "forte; linguagem editorial contemporânea que une calor humano e "
        "posicionamento político."
    ),
    "proposta_valor": (
        "Dar mais rostos e voz às histórias da comunidade, conectando passado e "
        "presente da memória LGBTQIA+ com pautas, educação/cuidado e impacto "
        "social mensurável."
    ),
    "tom_voz_externo": (
        "Afirmativa e protagonista — a pessoa/comunidade é o sujeito, não o "
        "objeto. Plural e contemporânea; acolhedora, mas com posicionamento "
        "(calor humano + clareza política). Editorial, herdando o espírito de "
        "chamada de jornal (Lampião da Esquina): manchetes diretas, com peso. "
        "Linguagem neutra/inclusiva quando soar natural, sem travar a leitura. "
        "Evitar tom corporativo frio, vitimização, jargão acadêmico empilhado e "
        "eufemismo. Nunca inventar fatos ou números — usar apenas dados fornecidos."
    ),
    "palavras_recomendadas": [
        "comunidade", "representatividade", "protagonismo", "equidade",
        "diversidade", "dignidade", "acesso", "pertencimento",
        "espaços de poder e influência", "cidadania", "empreendedorismo",
        "empregabilidade", "equidade racial", "cuidado com as pessoas",
        "impacto social", "LGBTI+", "LGBTQIA+", "TODXS",
    ],
    "palavras_evitar": [
        "tom corporativo frio", "vitimização", "jargão acadêmico empilhado",
        "eufemismo",
    ],
}

# Paleta oficial (Manual da Marca TODXS). As 8 cromáticas compartilham
# protagonismo (primary); preto é estrutural (secondary); off-white é apoio (accent).
PALETTE = [
    ("Vermelho", "#ED2E26", "primary"),
    ("Laranja", "#FF6B06", "primary"),
    ("Amarelo", "#F5D938", "primary"),
    ("Verde", "#35D386", "primary"),
    ("Azul", "#0E82E9", "primary"),
    ("Roxo", "#8B11EA", "primary"),
    ("Rosa", "#F2A8FD", "primary"),
    ("Marrom", "#83501D", "primary"),
    ("Preto", "#000000", "secondary"),
    ("Off-white", "#F4F1D9", "accent"),
]

# Papéis tipográficos. Fontes próprias (não Google Fonts) — o arquivo entra
# na etapa 2 ligando o CustomFont; por ora ficam como placeholder de papel.
TYPOGRAPHY = [
    ("Títulos / manchetes (Ana Banana Black)", 0),
    ("Corpo e subtítulos (Vinila)", 1),
]


class Command(BaseCommand):
    help = "Onboarda a TODXS como tenant (Organization + KnowledgeBase + paleta). Idempotente, sem migrations."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Não salva nada; só mostra o que faria.")
        parser.add_argument("--slug", default="todxs", help="Slug da organização (default: todxs).")
        parser.add_argument("--plan", default="premium", help="plan_type (default: premium).")
        parser.add_argument("--owner-email", default=None, help="Email do User dono (opcional).")
        parser.add_argument("--no-activate", action="store_true", help="Cria a org inativa (pending) em vez de ativa.")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        if dry:
            self.stdout.write(self.style.WARNING("🔍 DRY-RUN — nada será salvo.\n"))

        owner = None
        if opts["owner_email"]:
            owner = User.objects.filter(email__iexact=opts["owner_email"]).first()
            if not owner:
                self.stdout.write(self.style.ERROR(f"❌ Usuário {opts['owner_email']} não encontrado. Abortando."))
                return

        try:
            with transaction.atomic():
                org = self._upsert_org(opts, owner)
                kb = self._upsert_kb(org)
                self._upsert_colors(kb)
                self._upsert_typography(kb)
                # Recalcula a completude DEPOIS de inserir cores (o save() da KB
                # roda o cálculo; sem este re-save o valor fica defasado).
                kb.save()
                if dry:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING("\n🔁 DRY-RUN concluído — rollback aplicado."))
            return

        self.stdout.write(self.style.SUCCESS("\n✅ TODXS onboardada (dados + paleta)."))
        self.stdout.write(
            "   Pendente (etapa 2, requer arquivos): logo, grafismo do 'X' "
            "(BrandgraficModule), fotos de referência (ReferenceImage) e os "
            "arquivos de fonte (CustomFont → Typography)."
        )

    # --- passos -------------------------------------------------------------

    def _upsert_org(self, opts, owner):
        slug = slugify(opts["slug"])
        active = not opts["no_activate"]
        defaults = {
            "name": "TODXS",
            "tagline": "Empoderamento da comunidade LGBTI+/LGBTQIA+",
            "plan_type": opts["plan"],
            "is_active": active,
            "suspension_reason": "" if active else "pending",
            "posts_enabled": True,
            "pautas_enabled": True,
        }
        if owner:
            defaults["owner"] = owner

        org, created = Organization.objects.get_or_create(slug=slug, defaults=defaults)
        if not created:
            # Idempotência: completa só o que estiver vazio, sem sobrescrever ajustes manuais.
            changed = []
            if not org.name:
                org.name = "TODXS"; changed.append("name")
            if owner and not org.owner_id:
                org.owner = owner; changed.append("owner")
            if changed:
                org.save(update_fields=changed)
            self.stdout.write(f"• Organization já existia (slug={slug}, id={org.id}); ajustes: {changed or 'nenhum'}")
        else:
            self.stdout.write(self.style.SUCCESS(f"• Organization criada: {org.name} (slug={slug}, id={org.id}, ativa={org.is_active})"))
        return org

    def _upsert_kb(self, org):
        kb, created = KnowledgeBase.objects.get_or_create(
            organization=org, defaults=KB_FIELDS,
        )
        if not created:
            changed = []
            for field, value in KB_FIELDS.items():
                current = getattr(kb, field)
                empty = current in (None, "", [], {})
                if empty and value:
                    setattr(kb, field, value); changed.append(field)
            if changed:
                kb.save()
            self.stdout.write(f"• KnowledgeBase já existia (id={kb.id}); campos preenchidos: {changed or 'nenhum'}")
        else:
            self.stdout.write(self.style.SUCCESS(f"• KnowledgeBase criada (id={kb.id})"))
        return kb

    def _upsert_colors(self, kb):
        n_new = 0
        for order, (name, hex_code, ctype) in enumerate(PALETTE):
            _, created = ColorPalette.objects.get_or_create(
                knowledge_base=kb, name=name,
                defaults={"hex_code": hex_code, "color_type": ctype, "order": order},
            )
            n_new += int(created)
        self.stdout.write(f"• Paleta: {n_new} cor(es) nova(s), {len(PALETTE) - n_new} já existia(m).")

    def _upsert_typography(self, kb):
        n_new = 0
        for usage, order in TYPOGRAPHY:
            _, created = Typography.objects.get_or_create(
                knowledge_base=kb, usage=usage,
                defaults={"font_source": "upload", "order": order},
            )
            n_new += int(created)
        self.stdout.write(
            f"• Tipografia: {n_new} papel(éis) novo(s) (placeholder, sem arquivo); "
            f"{len(TYPOGRAPHY) - n_new} já existia(m)."
        )


class _Rollback(Exception):
    """Sentinela para abortar a transação no modo --dry-run."""
