#!/usr/bin/env python
"""
Teste para verificar salvamento de campos editados e sugestões aceitas
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, '/opt/iamkt/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema.settings.development')
django.setup()

from apps.knowledge.models import KnowledgeBase
from django.utils import timezone

def test_salvamento_campos():
    """
    Testa se campos editados e sugestões aceitas são salvos corretamente
    """
    print("=" * 80)
    print("TESTE: SALVAMENTO DE CAMPOS EDITADOS E SUGESTÕES ACEITAS")
    print("=" * 80)
    
    # Buscar KB
    kb = KnowledgeBase.objects.first()
    if not kb:
        print("❌ Nenhuma KnowledgeBase encontrada")
        return
    
    print(f"\n📋 KB ID: {kb.id}")
    print(f"📋 Organização: {kb.organization.name if kb.organization else 'N/A'}")
    
    # =========================================================================
    # PARTE 1: VERIFICAR VALORES ANTES
    # =========================================================================
    print("\n" + "=" * 80)
    print("PARTE 1: VALORES ANTES DA MODIFICAÇÃO")
    print("=" * 80)
    
    valores_antes = {
        'missao': kb.missao,
        'visao': kb.visao,
        'accepted_suggestion_fields': kb.accepted_suggestion_fields.copy() if kb.accepted_suggestion_fields else []
    }
    
    print(f"\n📊 Valores ANTES:")
    print(f"  mission (missao): {valores_antes['missao'][:80] if valores_antes['missao'] else 'VAZIO'}...")
    print(f"  vision (visao): {valores_antes['visao'][:80] if valores_antes['visao'] else 'VAZIO'}...")
    print(f"  accepted_suggestion_fields: {valores_antes['accepted_suggestion_fields']}")
    
    # =========================================================================
    # PARTE 2: SIMULAR EDIÇÃO (APENAS MEMÓRIA)
    # =========================================================================
    print("\n" + "=" * 80)
    print("PARTE 2: MODIFICAR OBJETO NA MEMÓRIA (setattr)")
    print("=" * 80)
    
    # Simular edição de campos
    novo_missao = "TESTE: Ser a melhor pizzaria artesanal da região"
    novo_visao = "TESTE: Tornar-se referência em qualidade e sabor"
    
    print(f"\n✏️ Modificando na MEMÓRIA:")
    print(f"  kb.missao = '{novo_missao}'")
    kb.missao = novo_missao
    
    print(f"  kb.visao = '{novo_visao}'")
    kb.visao = novo_visao
    
    print(f"  kb.accepted_suggestion_fields = ['mission', 'vision']")
    kb.accepted_suggestion_fields = ['mission', 'vision']
    
    # =========================================================================
    # PARTE 3: VERIFICAR MEMÓRIA vs BANCO
    # =========================================================================
    print("\n" + "=" * 80)
    print("PARTE 3: COMPARAR MEMÓRIA vs BANCO (ANTES DO SAVE)")
    print("=" * 80)
    
    # Buscar do banco novamente (sem cache)
    kb_banco = KnowledgeBase.objects.get(id=kb.id)
    
    print(f"\n🧠 MEMÓRIA (objeto kb):")
    print(f"  missao: {kb.missao[:80]}...")
    print(f"  visao: {kb.visao[:80]}...")
    print(f"  accepted_suggestion_fields: {kb.accepted_suggestion_fields}")
    
    print(f"\n💾 BANCO (kb_banco - busca direta):")
    print(f"  missao: {kb_banco.missao[:80] if kb_banco.missao else 'VAZIO'}...")
    print(f"  visao: {kb_banco.visao[:80] if kb_banco.visao else 'VAZIO'}...")
    print(f"  accepted_suggestion_fields: {kb_banco.accepted_suggestion_fields}")
    
    print(f"\n📊 COMPARAÇÃO:")
    print(f"  missao igual? {kb.missao == kb_banco.missao} {'❌ DIFERENTE (correto - ainda não salvou)' if kb.missao != kb_banco.missao else '⚠️ IGUAL (estranho)'}")
    print(f"  visao igual? {kb.visao == kb_banco.visao} {'❌ DIFERENTE (correto - ainda não salvou)' if kb.visao != kb_banco.visao else '⚠️ IGUAL (estranho)'}")
    print(f"  accepted_suggestion_fields igual? {kb.accepted_suggestion_fields == kb_banco.accepted_suggestion_fields} {'❌ DIFERENTE (correto)' if kb.accepted_suggestion_fields != kb_banco.accepted_suggestion_fields else '⚠️ IGUAL (estranho)'}")
    
    # =========================================================================
    # PARTE 4: SALVAR NO BANCO
    # =========================================================================
    print("\n" + "=" * 80)
    print("PARTE 4: SALVAR NO BANCO (kb.save())")
    print("=" * 80)
    
    print(f"\n💾 Executando kb.save()...")
    kb.save()
    print(f"✅ Save executado")
    
    # =========================================================================
    # PARTE 5: VERIFICAR APÓS SAVE
    # =========================================================================
    print("\n" + "=" * 80)
    print("PARTE 5: VERIFICAR APÓS SAVE")
    print("=" * 80)
    
    # Buscar do banco novamente
    kb_banco_depois = KnowledgeBase.objects.get(id=kb.id)
    
    print(f"\n💾 BANCO (após save):")
    print(f"  missao: {kb_banco_depois.missao[:80]}...")
    print(f"  visao: {kb_banco_depois.visao[:80]}...")
    print(f"  accepted_suggestion_fields: {kb_banco_depois.accepted_suggestion_fields}")
    
    print(f"\n📊 COMPARAÇÃO COM VALORES MODIFICADOS:")
    print(f"  missao salva corretamente? {kb_banco_depois.missao == novo_missao} {'✅ SIM' if kb_banco_depois.missao == novo_missao else '❌ NÃO'}")
    print(f"  visao salva corretamente? {kb_banco_depois.visao == novo_visao} {'✅ SIM' if kb_banco_depois.visao == novo_visao else '❌ NÃO'}")
    print(f"  accepted_suggestion_fields salvo? {kb_banco_depois.accepted_suggestion_fields == ['mission', 'vision']} {'✅ SIM' if kb_banco_depois.accepted_suggestion_fields == ['mission', 'vision'] else '❌ NÃO'}")
    
    # =========================================================================
    # PARTE 6: RESTAURAR VALORES ORIGINAIS
    # =========================================================================
    print("\n" + "=" * 80)
    print("PARTE 6: RESTAURAR VALORES ORIGINAIS")
    print("=" * 80)
    
    print(f"\n🔄 Restaurando valores originais...")
    kb.missao = valores_antes['missao']
    kb.visao = valores_antes['visao']
    kb.accepted_suggestion_fields = valores_antes['accepted_suggestion_fields']
    kb.save()
    print(f"✅ Valores restaurados")
    
    # =========================================================================
    # RESULTADO FINAL
    # =========================================================================
    print("\n" + "=" * 80)
    print("RESULTADO FINAL")
    print("=" * 80)
    
    sucesso = (
        kb_banco_depois.missao == novo_missao and
        kb_banco_depois.visao == novo_visao and
        kb_banco_depois.accepted_suggestion_fields == ['mission', 'vision']
    )
    
    if sucesso:
        print("\n✅ TESTE PASSOU!")
        print("   - Campos editados foram salvos corretamente")
        print("   - accepted_suggestion_fields foi salvo corretamente")
        print("   - setattr modifica apenas memória")
        print("   - save() persiste no banco de dados")
    else:
        print("\n❌ TESTE FALHOU!")
        print("   - Algum campo não foi salvo corretamente")
    
    print("\n" + "=" * 80)

if __name__ == '__main__':
    test_salvamento_campos()
