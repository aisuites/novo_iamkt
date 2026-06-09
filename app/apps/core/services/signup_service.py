"""
Serviço de cadastro de novas contas (organização + usuário admin).

Fonte única usada tanto pelo formulário web (register_view) quanto pela
API de cadastro externo chamada pelo site iamkt.com.br (views_signup_api).

Fluxo:
1. create_pending_signup() -> cria Organization PENDENTE + User admin INATIVO.
2. confirm_payment() -> ativa a Organization após confirmação de pagamento.
"""
import logging

from django.db import transaction
from django.utils import timezone

from ..models import User, Organization, PlanTemplate
from ..utils.cpf import normalize_cpf, is_valid_cpf

logger = logging.getLogger(__name__)


# Mapeia o nome do plano usado no site para o plan_type interno (PlanTemplate).
# "starter" herda as configs do antigo plano gratuito; "pro" = plano básico.
SITE_PLAN_TO_TEMPLATE = {
    'starter': 'free',
    'pro': 'basic',
}


class SignupError(Exception):
    """
    Erro de cadastro com mensagem amigável e código.
    `code` permite que a API devolva o status HTTP adequado
    (ex: 'email_exists'/'cpf_exists' -> 409, 'invalid' -> 400).
    """
    def __init__(self, message, code='invalid'):
        super().__init__(message)
        self.message = message
        self.code = code


def _split_name(full_name):
    parts = (full_name or '').split()
    first_name = parts[0] if parts else ''
    last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
    return first_name, last_name


@transaction.atomic
def create_pending_signup(*, full_name, email, company_name, password,
                          cpf='', phone='', plan=''):
    """
    Cria uma Organization pendente de aprovação e o User admin (inativo).

    Não ativa nada — a liberação ocorre em confirm_payment().
    Levanta SignupError em caso de duplicidade ou dados inválidos.

    Retorna (organization, user).
    """
    email = (email or '').strip().lower()
    company_name = (company_name or '').strip()
    full_name = (full_name or '').strip()
    phone = (phone or '').strip()
    plan = (plan or '').strip().lower()
    cpf_digits = normalize_cpf(cpf)

    # --- Validações de duplicidade (chave do usuário é o email) ---
    if User.objects.filter(email=email).exists():
        raise SignupError('Este email já está cadastrado.', code='email_exists')

    if cpf_digits:
        if not is_valid_cpf(cpf_digits):
            raise SignupError('CPF inválido.', code='invalid')
        if Organization.objects.filter(cpf=cpf_digits).exists():
            raise SignupError('Este CPF já está cadastrado.', code='cpf_exists')

    # --- Criação ---
    # slug é gerado automaticamente pelo Organization.save() (resolve colisões).
    organization = Organization.objects.create(
        name=company_name,
        is_active=False,                 # Aguardando confirmação de pagamento
        plan_type='pending',
        suspension_reason='pending',     # choice válida (era 'pending_approval' — inválido)
        cpf=cpf_digits or None,          # None evita conflito de unicidade entre cadastros sem CPF
        requested_plan=plan,
        quota_pautas_dia=0,
        quota_posts_dia=0,
        quota_posts_mes=0,
    )

    first_name, last_name = _split_name(full_name)
    user = User.objects.create(
        username=email,                  # email é o username
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        organization=organization,
        profile='admin',                 # primeiro usuário é admin da org
        is_active=False,                 # Aguardando confirmação de pagamento
    )
    user.set_password(password)
    user.save()

    organization.owner = user
    organization.save()

    logger.info(
        f"[SIGNUP] Conta pendente criada: org={organization.id} '{organization.name}' "
        f"user={email} plano={plan or '(não informado)'}"
    )
    return organization, user


@transaction.atomic
def confirm_payment(*, org_id, plan='', payment_ref=''):
    """
    Confirma o pagamento e libera a organização.

    - Aplica o PlanTemplate correspondente ao plano (starter/pro).
    - Marca a org como ativa e ativa todos os usuários pendentes.
    - O email de "conta aprovada" é disparado pelo signal de Organization
      quando approved_at passa de None -> valor.
    - Idempotente: se já estiver ativa, não faz nada.

    Levanta Organization.DoesNotExist se org_id não existir.

    Retorna (organization, activated: bool). `activated=False` quando a org
    já estava ativa (chamada repetida do webhook).
    """
    organization = Organization.objects.select_for_update().get(id=org_id)

    if organization.is_active:
        logger.info(f"[SIGNUP] confirm_payment ignorado — org {org_id} já está ativa (idempotente).")
        return organization, False

    plan_key = (plan or organization.requested_plan or '').strip().lower()
    template_type = SITE_PLAN_TO_TEMPLATE.get(plan_key)

    if template_type:
        template = PlanTemplate.objects.filter(plan_type=template_type, is_active=True).first()
        if template:
            template.apply_to_organization(organization)
        else:
            logger.warning(
                f"[SIGNUP] PlanTemplate '{template_type}' (plano '{plan_key}') não encontrado/ativo. "
                f"Org {org_id} liberada sem aplicar quotas do template."
            )
    else:
        logger.warning(
            f"[SIGNUP] Plano '{plan_key}' desconhecido na confirmação da org {org_id}. "
            f"Org liberada sem aplicar template."
        )

    organization.is_active = True
    organization.approved_at = organization.approved_at or timezone.now()
    organization.suspension_reason = ''
    if payment_ref:
        organization.payment_reference = str(payment_ref)
    organization.save()  # dispara signal -> email de conta aprovada

    activated_users = organization.users.filter(is_active=False).update(is_active=True)

    logger.info(
        f"[SIGNUP] Pagamento confirmado — org {org_id} '{organization.name}' liberada. "
        f"plano={plan_key} ref={payment_ref or '-'} usuarios_ativados={activated_users}"
    )
    return organization, True
