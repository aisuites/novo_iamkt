"""
Onboarding da Samsung Healthcare como tenant (dados textuais + paleta + tipografia).

Cria/atualiza, de forma idempotente:
  - Organization "Samsung Healthcare"
  - User dono de teste (teste.samsung-hc@teste.samsung-hc)
  - KnowledgeBase (DNA da marca: identidade, posicionamento, tom de voz, vocabulário)
  - Paleta institucional (branco/azul/cinza/preto/prata — comunicação sóbria)
  - 2 papéis de Typography (stand-in Google "Inter"; a família oficial é
    SamsungOne / Samsung Sharp Sans — o arquivo real entra depois, ligando um
    CustomFont)

NÃO faz upload de assets (logos, grafismos, fotos de referência): isso depende de
arquivos + S3 e é feito numa segunda etapa (o dono envia os arquivos).

NÃO cria migrations — apenas dados. Seguro para rodar em produção.

Fonte do conteúdo: "Base de Conhecimento da Marca — Samsung Healthcare
(Samsung Medison e Diagnostic Displays)" v1.0, consolidada pela IAMKT.
IMPORTANTE: o dossiê distingue informação OFICIAL (missão), NÃO publicada
(visão), PARCIALMENTE oficial (valores) e INFERÊNCIAS estratégicas da IAMKT
(tom de voz, personalidade, posicionamento percebido). Essa separação é
preservada no texto dos campos para reduzir alucinação dos agentes.

Uso:
    python manage.py seed_samsung_healthcare --dry-run
    python manage.py seed_samsung_healthcare
    python manage.py seed_samsung_healthcare --owner-email pessoa@exemplo.com --plan premium
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

from apps.core.models import Organization
from apps.knowledge.models import KnowledgeBase, ColorPalette, Typography

User = get_user_model()


# --- Conteúdo da marca (consolidado da Base de Conhecimento Samsung Healthcare) ---

KB_FIELDS = {
    "nome_empresa": "Samsung Healthcare",
    "descricao_produto": (
        "A Samsung Healthcare (Samsung Medison e Diagnostic Displays) desenvolve "
        "soluções inovadoras de diagnóstico por imagem — ultrassonografia, "
        "monitores e displays de diagnóstico — para hospitais, clínicas e centros "
        "de diagnóstico. A tecnologia é apresentada como apoio à decisão clínica: "
        "melhora a confiança diagnóstica, otimiza o fluxo de trabalho e apoia "
        "melhores cuidados ao paciente, com inteligência artificial no papel de "
        "facilitadora da prática clínica — nunca como substituta do médico."
    ),
    "missao": (
        "[OFICIAL] Adicionar valor à saúde e à felicidade da vida humana por meio "
        "de soluções inovadoras de diagnóstico por imagem. A comunicação "
        "institucional reforça continuamente: melhorar a confiança diagnóstica; "
        "transformar desafios clínicos em soluções; apoiar melhores cuidados ao "
        "paciente; desenvolver tecnologias médicas inovadoras."
    ),
    "visao": (
        "[NÃO PUBLICADA OFICIALMENTE] A Samsung Healthcare não divulga uma "
        "declaração formal de visão para a divisão de diagnóstico por imagem. "
        "Direcionamento observado na comunicação: evolução do diagnóstico por "
        "imagem; integração entre IA e prática clínica; melhoria do fluxo de "
        "trabalho; apoio à decisão médica; inovação contínua."
    ),
    "valores": (
        "[PARCIALMENTE OFICIAL — distribuídos entre documentos institucionais e de "
        "sustentabilidade] Pessoas em primeiro lugar; respeito aos direitos "
        "humanos; diversidade; inclusão; desenvolvimento das pessoas; segurança; "
        "inovação responsável."
    ),
    "publico_externo": (
        "Profissionais de saúde e instituições que operam diagnóstico por imagem: "
        "médicos, radiologistas e ultrassonografistas, em hospitais, clínicas e "
        "centros de diagnóstico. A comunicação foca no profissional que utiliza o "
        "equipamento (raramente apenas no paciente), tratando o benefício ao "
        "paciente como resultado da confiança e eficiência entregues ao médico."
    ),
    "publico_interno": (
        "Equipes da Samsung Healthcare — P&D, aplicação clínica, vendas e suporte "
        "técnico — orientadas por inovação centrada no cliente (Customer Driven "
        "Innovation) e por evidências clínicas."
    ),
    "posicionamento": (
        "[PERCEBIDO — inferência estratégica IAMKT] Tecnologia sofisticada com "
        "comunicação discreta: autoridade científica, baixa autopromoção e forte "
        "orientação para benefícios clínicos — confiança acima de espetáculo. A "
        "estrutura de comunicação parte quase sempre do desafio clínico → "
        "tecnologia Samsung → benefício para o médico → benefício para o paciente "
        "→ impacto no fluxo clínico. Quase nunca começa falando do equipamento."
    ),
    "diferenciais": (
        "Confiança diagnóstica (Diagnostic Confidence); eficiência e inteligência "
        "de fluxo de trabalho (Workflow Efficiency / Smart Workflow); imagem "
        "avançada e de alta qualidade (Advanced Imaging / Image Quality); "
        "diagnóstico rápido e preciso (Fast and Accurate Diagnosis / Precision); "
        "IA de apoio ao diagnóstico (AI-powered Imaging / AI-assisted Diagnosis); "
        "inovação orientada pelo cliente (Customer Driven Innovation). A IA é "
        "sempre ferramenta de apoio ao profissional, nunca protagonista."
    ),
    "proposta_valor": (
        "Transformar desafios clínicos em soluções que aumentam a confiança "
        "diagnóstica, elevam a qualidade clínica e a produtividade e, por "
        "consequência, melhoram o cuidado ao paciente — só então apresentando as "
        "funcionalidades do equipamento. A Samsung Healthcare raramente vende "
        "tecnologia pela tecnologia."
    ),
    "tom_voz_externo": (
        "[INFERÊNCIA ESTRATÉGICA IAMKT — padrão observado, não declaração oficial] "
        "Técnico, objetivo, elegante, seguro, baseado em evidências, claro, "
        "respeitoso e confiante. Personalidade percebida: arquétipo predominante "
        "Sábio; secundários Cuidador e Criador. "
        "ESTRUTURA típica do texto: desafio clínico → tecnologia Samsung → "
        "benefício para o médico → benefício para o paciente → impacto no fluxo "
        "clínico. Começar pelo problema clínico, não pelo equipamento. "
        "PAPEL DA IA: apoio à decisão clínica e facilitadora da prática — nunca "
        "substituta do médico; representada por interfaces, medições e "
        "sobreposições discretas, sem robôs nem futurismo exagerado. "
        "EVITAR: linguagem emocional exagerada, promessas absolutas, marketing "
        "sensacionalista, 'revolucionário', 'disruptivo', 'o melhor do mundo', a "
        "IA como protagonista e qualquer ideia de substituição do médico. "
        "Nunca inventar fatos ou números — usar apenas dados fornecidos. "
        "Sempre distinguir informação oficial, padrão observado e interpretação "
        "estratégica da IAMKT."
    ),
    "palavras_recomendadas": [
        "Diagnostic Confidence", "Workflow Efficiency", "Better Patient Care",
        "AI-powered Imaging", "AI-assisted Diagnosis", "Customer Driven Innovation",
        "Advanced Imaging", "Fast and Accurate Diagnosis", "Smart Workflow",
        "Precision", "confiança diagnóstica", "eficiência", "qualidade de imagem",
        "cuidado ao paciente", "inovação", "clínico", "produtividade",
        "improve", "enhance", "support", "enable", "assist", "optimize",
        "advanced", "smart", "solutions", "performance",
    ],
    "palavras_evitar": [
        "revolucionário", "disruptivo", "o melhor do mundo",
        "linguagem emocional exagerada", "promessas absolutas",
        "marketing sensacionalista", "robôs", "IA como protagonista",
        "substituição do médico",
    ],
}

# Paleta institucional (estilo visual do dossiê): comunicação sóbria, muito
# espaço negativo, poucas cores vibrantes. Azul Samsung como cor de marca
# (protagonista) + branco; neutros estruturais (preto/cinza/prata) = secondary.
PALETTE = [
    ("Azul Samsung", "#1428A0", "primary"),
    ("Branco", "#FFFFFF", "primary"),
    ("Preto", "#000000", "secondary"),
    ("Cinza", "#808080", "secondary"),
    ("Prata", "#C0C0C0", "secondary"),
]

# Papéis tipográficos. A família oficial da marca é Samsung SS Head (títulos:
# Bold/Medium/Regular/Light) e Samsung SS Body (texto: Bold/Regular/Light).
# Os .otf reais são subidos numa etapa separada (CustomFont → Typography, via
# script Drive/arquivos → S3), que religa estes papéis para font_source=upload.
# O stand-in Google "Inter" abaixo só é aplicado se o papel ainda não existir
# (get_or_create por usage), então re-rodar o seed nunca sobrescreve as fontes
# reais já ligadas. As strings de `usage` batem com as usadas no religamento.
TYPOGRAPHY = [
    ("Títulos e destaques (Samsung SS Head)", "Inter", "700", 0),
    ("Blocos de texto (Samsung SS Body)", "Inter", "400", 1),
]


class Command(BaseCommand):
    help = "Onboarda a Samsung Healthcare (Organization + User + KnowledgeBase + paleta + tipografia stand-in). Idempotente, sem migrations."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Não salva nada; só mostra o que faria.")
        parser.add_argument("--slug", default="samsung-healthcare", help="Slug da organização (default: samsung-healthcare).")
        parser.add_argument("--plan", default="premium", help="plan_type (default: premium).")
        parser.add_argument("--owner-email", default="teste.samsung-hc@teste.samsung-hc",
                            help="Email do User dono (criado se não existir).")
        parser.add_argument("--owner-password", default="teste.samsung-hc@teste.samsung-hc",
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

        self.stdout.write(self.style.SUCCESS("\n✅ Samsung Healthcare onboardada (dados + paleta + tipografia stand-in)."))
        self.stdout.write(
            "   Pendente (etapa 2, requer arquivos do dono): logos, grafismos "
            "(BrandgraficModule), fotos de referência (ReferenceImage) e o "
            "arquivo real da família SamsungOne / Samsung Sharp Sans (CustomFont → Typography)."
        )

    # --- passos -------------------------------------------------------------

    def _upsert_org(self, opts, owner):
        slug = slugify(opts["slug"])
        active = not opts["no_activate"]
        defaults = {
            "name": "Samsung Healthcare",
            "tagline": "Innovation for Healthcare",
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
                org.name = "Samsung Healthcare"; changed.append("name")
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
            f"• Tipografia: {n_new} papel(éis) novo(s) (stand-in Google Inter); "
            f"{len(TYPOGRAPHY) - n_new} já existia(m)."
        )


class _Rollback(Exception):
    """Sentinela para abortar a transação no modo --dry-run."""
