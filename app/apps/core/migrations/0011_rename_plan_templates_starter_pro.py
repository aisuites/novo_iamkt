from django.db import migrations


# Renomeia o nome de exibição dos planos para alinhar com o site (Starter/Pro).
# A chave interna (plan_type) NÃO muda: free continua 'free', basic continua 'basic'.
RENAMES = [
    ('free', 'Plano Gratuito', 'Starter'),
    ('basic', 'Plano Básico', 'Pro'),
]


def rename_forward(apps, schema_editor):
    PlanTemplate = apps.get_model('core', 'PlanTemplate')
    for plan_type, _old, new in RENAMES:
        PlanTemplate.objects.filter(plan_type=plan_type).update(name=new)


def rename_backward(apps, schema_editor):
    PlanTemplate = apps.get_model('core', 'PlanTemplate')
    for plan_type, old, _new in RENAMES:
        PlanTemplate.objects.filter(plan_type=plan_type).update(name=old)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_organization_cpf_organization_payment_reference_and_more'),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename_backward),
    ]
