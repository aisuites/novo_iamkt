"""
Onboarding da VB Gastronomia como tenant (dados textuais + paleta + tipografia).

Cria/atualiza, de forma idempotente:
  - Organization "VB Gastronomia"
  - KnowledgeBase (DNA da marca: identidade, posicionamento, tom de voz, vocabulário)
  - 8 cores da ColorPalette (paleta institucional do manual)
  - 2 papéis de Typography (stand-in Google "Barlow Condensed"; a Acumin é Adobe
    Fonts/licenciada — o arquivo real entra depois, ligando um CustomFont)

NÃO faz upload de assets (logos, grafismos, fotos de referência): isso depende de
arquivos + S3 e é feito numa segunda etapa (o dono envia os arquivos).

NÃO cria migrations — apenas dados. Seguro para rodar em produção.

Fonte do conteúdo: "[VB Gastronomia] Manual de Marca.pdf" (Colletivo Design) +
PDFs de paleta e tipografia. Consolidado em docs-aplicacao/vb-gastronomia/FICHA_MARCA.md.

Uso:
    python manage.py seed_vb_gastronomia --dry-run
    python manage.py seed_vb_gastronomia
    python manage.py seed_vb_gastronomia --owner-email pessoa@exemplo.com --plan premium
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

from apps.core.models import Organization
from apps.knowledge.models import KnowledgeBase, ColorPalette, Typography

User = get_user_model()


# --- Conteúdo da marca (consolidado do Manual de Marca) ---------------------

KB_FIELDS = {
    "nome_empresa": "VB Gastronomia",
    "descricao_produto": (
        "A VB Gastronomia é uma empresa de gastronomia corporativa (buffet e "
        "catering) que leva alimentação de qualidade ao mundo corporativo. Com "
        "tecnologia de ponta e métodos operacionais padronizados, oferece um "
        "serviço personalizado e eficiente — do tamanho da necessidade de cada "
        "cliente — reduzindo desperdícios, otimizando recursos e garantindo "
        "previsibilidade em toda a cadeia de produção, sempre com foco no "
        "bem-estar dos colaboradores das empresas atendidas."
    ),
    "missao": (
        "Entregar valor e sabor ao mundo corporativo: alimentar pessoas, "
        "fortalecer negócios e cultivar relações que tornam o cotidiano "
        "corporativo uma experiência mais saudável e um espaço mais produtivo, "
        "com cuidado em cada detalhe."
    ),
    "visao": (
        "Ser referência em gastronomia corporativa que une rigor técnico e "
        "hospitalidade, transformando a refeição em uma experiência de pausa, "
        "bem-estar e pertencimento dentro das empresas."
    ),
    "valores": (
        "Hospitalidade como valor central; excelência com sensibilidade (rigor "
        "técnico com calor humano); eficiência e autonomia (resolver e antecipar "
        "sem burocracia); presença estratégica e escuta ativa (proximidade como "
        "ferramenta de inovação); cuidado com os detalhes; previsibilidade e "
        "responsabilidade (redução de desperdício, uso eficiente de recursos)."
    ),
    "publico_externo": (
        "Empresas (B2B) que valorizam o bem-estar de seus colaboradores — áreas "
        "de RH, facilities e administração que contratam alimentação corporativa "
        "— e, indiretamente, os colaboradores que vivem a experiência das "
        "refeições no dia a dia."
    ),
    "publico_interno": (
        "Equipes da VB Gastronomia — times na ponta com autonomia para resolver "
        "imprevistos e antecipar demandas, integrados à cultura corporativa de "
        "cada cliente."
    ),
    "posicionamento": (
        "Cuidar com excelência é um ingrediente invisível. Posicionamento: "
        "excelência, proximidade e escala inteligente. A VB une rigor técnico "
        "(estratégia, processos, inteligência operacional, previsibilidade) e "
        "sensibilidade (hospitalidade, calor humano), tratando a refeição como "
        "experiência que impacta pessoas, relações e ambientes — pausa, "
        "bem-estar e pertencimento que respeitam o ritmo de cada empresa."
    ),
    "diferenciais": (
        "1) Hospitalidade como valor central — alimentação como vivência de "
        "bem-estar, atendimento e conexão humana. 2) Eficiência e autonomia — "
        "times na ponta resolvem imprevistos e antecipam demandas sem "
        "burocracia. 3) Presença estratégica — escuta ativa e analítica que "
        "converte percepções em melhorias reais; proximidade como ferramenta de "
        "inovação. 4) Excelência com sensibilidade — rigor técnico com calor "
        "humano, unindo processos precisos, sabor e hospitalidade."
    ),
    "proposta_valor": (
        "Refeições corporativas que unem sabor, excelência operacional e "
        "hospitalidade — um serviço personalizado, previsível e eficiente que "
        "cuida de cada detalhe e transforma a pausa para a refeição em um "
        "momento real de bem-estar, conexão e produtividade."
    ),
    "tom_voz_externo": (
        "Próximo, caloroso e acessível — evita formalidades e aproxima a marca "
        "das pessoas, transmitindo acolhimento com naturalidade. Convidativo — "
        "inspira pertencimento e faz o público querer fazer parte da "
        "experiência. Expressa conhecimento, autoridade e eficiência, mas com "
        "leveza: mostra domínio do que faz, com informações e soluções claras e "
        "práticas. Comunicação viva e presente, que transmite segurança e "
        "otimismo com equilíbrio, destacando o lado humano e inspirador das "
        "relações. Evitar tom corporativo frio, burocrático e formalidades. "
        "Nunca inventar fatos ou números — usar apenas dados fornecidos."
    ),
    "palavras_recomendadas": [
        "cuidado", "excelência", "hospitalidade", "acolhimento", "pertencimento",
        "bem-estar", "pausa", "proximidade", "escuta ativa", "sabor",
        "experiência", "conexão", "detalhe", "comida real", "frescor",
        "previsibilidade", "personalização", "cotidiano corporativo",
        "perto de cada detalhe",
    ],
    "palavras_evitar": [
        "tom corporativo frio", "linguagem burocrática", "formalidades excessivas",
        "jargão", "frieza",
    ],
}

# Paleta institucional (Manual VB). Base = tons terrosos (protagonistas);
# neutros estruturais = secondary; laranja e amarelo = apoio/destaque (accent).
PALETTE = [
    ("Verde-oliva", "#666651", "primary"),
    ("Terracota", "#C68B71", "primary"),
    ("Bordô", "#71140D", "primary"),
    ("Off-white", "#EAE0D3", "primary"),
    ("Preto", "#000000", "secondary"),
    ("Cinza claro", "#CCCCCC", "secondary"),
    ("Laranja", "#F95B00", "accent"),
    ("Amarelo", "#FFF15F", "accent"),
]

# Papéis tipográficos. A marca usa Acumin Variable Concept Condensed (Adobe
# Fonts, licenciada). Stand-in gratuito enquanto o arquivo real não é subido:
# Barlow Condensed (Google) — condensada neogrotesca próxima. Trocar depois.
TYPOGRAPHY = [
    ("Títulos e destaques (Acumin Condensed)", "Barlow Condensed", "600", 0),
    ("Blocos de texto (Acumin Condensed Light)", "Barlow Condensed", "300", 1),
]


class Command(BaseCommand):
    help = "Onboarda a VB Gastronomia (Organization + KnowledgeBase + paleta + tipografia stand-in). Idempotente, sem migrations."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Não salva nada; só mostra o que faria.")
        parser.add_argument("--slug", default="vb-gastronomia", help="Slug da organização (default: vb-gastronomia).")
        parser.add_argument("--plan", default="premium", help="plan_type (default: premium).")
        parser.add_argument("--owner-email", default="teste.vbgastronomia@teste.vbgastronomia",
                            help="Email do User dono (criado se não existir).")
        parser.add_argument("--owner-password", default="teste.vbgastronomia@teste.vbgastronomia",
                            help="Senha do User dono (usada só na criação).")
        parser.add_argument("--no-owner", action="store_true", help="Não cria/associa usuário dono.")
        parser.add_argument("--no-activate", action="store_true", help="Cria a org inativa (pending) em vez de ativa.")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        if dry:
            self.stdout.write(self.style.WARNING("🔍 DRY-RUN — nada será salvo.\n"))

        try:
            with transaction.atomic():
                org = self._upsert_org(opts, owner=None)
                if not opts["no_owner"]:
                    self._ensure_owner(org, opts["owner_email"], opts["owner_password"])
                kb = self._upsert_kb(org)
                self._upsert_colors(kb)
                self._upsert_typography(kb)
                kb.save()  # recalcula completude após inserir cores/typo
                if dry:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING("\n🔁 DRY-RUN concluído — rollback aplicado."))
            return

        self.stdout.write(self.style.SUCCESS("\n✅ VB Gastronomia onboardada (dados + paleta + tipografia stand-in)."))
        self.stdout.write(
            "   Pendente (etapa 2, requer arquivos do dono): logos, grafismos "
            "(BrandgraficModule), fotos de referência (ReferenceImage) e o "
            "arquivo real da fonte Acumin (CustomFont → Typography)."
        )

    # --- passos -------------------------------------------------------------

    def _upsert_org(self, opts, owner):
        slug = slugify(opts["slug"])
        active = not opts["no_activate"]
        defaults = {
            "name": "VB Gastronomia",
            "tagline": "Perto de cada detalhe",
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
            changed = []
            if not org.name:
                org.name = "VB Gastronomia"; changed.append("name")
            if owner and not org.owner_id:
                org.owner = owner; changed.append("owner")
            if changed:
                org.save(update_fields=changed)
            self.stdout.write(f"• Organization já existia (slug={slug}, id={org.id}); ajustes: {changed or 'nenhum'}")
        else:
            self.stdout.write(self.style.SUCCESS(f"• Organization criada: {org.name} (slug={slug}, id={org.id}, ativa={org.is_active})"))
        return org

    def _ensure_owner(self, org, email, password):
        """Cria (se faltar) o User dono, vincula à org e define org.owner.
        Sem signals de email no User → não dispara nada."""
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            user = User.objects.create_user(
                username=email, email=email, password=password,
                is_active=True, is_staff=False,  # usuário comum (não admin)
            )
            user.organization = org
            user.profile = "operacional"
            user.save(update_fields=["organization", "profile"])
            self.stdout.write(self.style.SUCCESS(f"• Usuário dono criado: {email} (id={user.id})"))
        else:
            changed = []
            if not user.organization_id:
                user.organization = org; changed.append("organization")
            if changed:
                user.save(update_fields=changed)
            self.stdout.write(f"• Usuário dono já existia: {email} (id={user.id}); ajustes: {changed or 'nenhum'}")
        if not org.owner_id:
            org.owner = user
            org.save(update_fields=["owner"])
            self.stdout.write(f"• org.owner definido = {email}")
        return user

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
        for usage, gfont, weight, order in TYPOGRAPHY:
            _, created = Typography.objects.get_or_create(
                knowledge_base=kb, usage=usage,
                defaults={"font_source": "google", "google_font_name": gfont,
                          "google_font_weight": weight, "order": order},
            )
            n_new += int(created)
        self.stdout.write(
            f"• Tipografia: {n_new} papel(éis) novo(s) (stand-in Google Barlow Condensed); "
            f"{len(TYPOGRAPHY) - n_new} já existia(m)."
        )


class _Rollback(Exception):
    """Sentinela para abortar a transação no modo --dry-run."""
