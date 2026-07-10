"""
artkit — nucleo compartilhado dos pipelines de arte por arquetipo
(docs/arquitetura-pipeline-escalavel.md, Fase 1).

Regras deste pacote:
1. FIDELIDADE SOBRE ELEGANCIA: cada funcao preserva o comportamento exato do
   pipeline de origem. Diferencas historicas entre orgs viram PARAMETRO
   explicito (ex.: cover(rounding=int|round)) — nunca mudanca silenciosa.
2. Todo passo de migracao para ca exige `manage.py golden_archetypes --check`
   com 15/15 identicos antes do commit.
3. Unificacao SEMANTICA (um unico fitter de texto, um unico wrap) e trabalho
   da Fase 2 (engine v3), com re-gravacao consciente dos goldens — nao daqui.
"""
