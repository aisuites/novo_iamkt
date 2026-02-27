from django.contrib import admin
from django.utils.html import format_html
import json
from .models import (
    KnowledgeBase, InternalSegment, ReferenceImage, CustomFont, Logo, 
    Competitor, ColorPalette, SocialNetwork, SocialNetworkTemplate,
    KnowledgeChangeLog, Typography
)


class InternalSegmentInline(admin.TabularInline):
    """Inline para exibir segmentos dentro da KnowledgeBase"""
    model = InternalSegment
    extra = 0
    fields = ['name', 'description', 'parent', 'order', 'is_active']
    readonly_fields = []
    ordering = ['order', 'name']
    
    def get_readonly_fields(self, request, obj=None):
        # Code é readonly pois é auto-gerado
        return ['code'] if obj else []


@admin.register(InternalSegment)
class InternalSegmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'parent', 'order', 'is_active', 'knowledge_base', 'updated_at']
    list_filter = ['is_active', 'knowledge_base', 'parent']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['code', 'created_at', 'updated_at', 'updated_by']
    ordering = ['knowledge_base', 'order', 'name']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('knowledge_base', 'name', 'code', 'description')
        }),
        ('Hierarquia e Ordenação', {
            'fields': ('parent', 'order')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change or not obj.updated_by:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ['nome_empresa', 'completude_percentual', 'is_complete', 'analysis_status', 'updated_at']
    list_filter = ['analysis_status', 'is_complete']
    readonly_fields = [
        'completude_percentual', 'is_complete', 'created_at', 'updated_at',
        'display_concorrentes', 'display_n8n_analysis', 'display_n8n_compilation',
        'analysis_revision_id', 'analysis_requested_at', 'analysis_completed_at',
        'compilation_requested_at', 'compilation_completed_at'
    ]
    inlines = [InternalSegmentInline]
    
    fieldsets = (
        ('Bloco 1: Identidade Institucional', {
            'fields': ('nome_empresa', 'missao', 'visao', 'valores', 'descricao_produto')
        }),
        ('Bloco 2: Público e Segmentos', {
            'fields': ('publico_externo', 'publico_interno')
        }),
        ('Bloco 3: Posicionamento e Diferenciais', {
            'fields': ('posicionamento', 'diferenciais', 'proposta_valor')
        }),
        ('Bloco 4: Tom de Voz e Linguagem', {
            'fields': ('tom_voz_externo', 'tom_voz_interno', 'palavras_recomendadas', 'palavras_evitar')
        }),
        ('Bloco 5: Identidade Visual', {
            'fields': ()
        }),
        ('Bloco 6: Sites e Redes Sociais', {
            'fields': ('site_institucional', 'display_concorrentes', 'templates_redes')
        }),
        ('Bloco 7: Dados e Insights', {
            'fields': ('fontes_confiaveis', 'canais_trends', 'palavras_chave_trends')
        }),
        ('Análise N8N', {
            'fields': (
                'analysis_status', 'analysis_revision_id',
                'analysis_requested_at', 'analysis_completed_at',
                'display_n8n_analysis'
            ),
            'classes': ('collapse',)
        }),
        ('Compilação N8N', {
            'fields': (
                'compilation_status',
                'compilation_requested_at', 'compilation_completed_at',
                'display_n8n_compilation'
            ),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('completude_percentual', 'is_complete', 'last_updated_by', 'created_at', 'updated_at')
        }),
    )
    
    def has_add_permission(self, request):
        # Singleton - apenas uma instância
        return not KnowledgeBase.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def display_concorrentes(self, obj):
        """Exibe concorrentes de forma formatada"""
        if not obj.concorrentes:
            return format_html('<em style="color: #999;">Nenhum concorrente cadastrado</em>')
        
        html = '<div style="font-family: monospace; background: #f5f5f5; padding: 10px; border-radius: 4px;">'
        for i, conc in enumerate(obj.concorrentes, 1):
            nome = conc.get('nome', 'Sem nome')
            url = conc.get('url', '')
            html += f'<div style="margin-bottom: 8px; padding: 8px; background: white; border-left: 3px solid #7c3aed;">'
            html += f'<strong>{i}. {nome}</strong>'
            if url:
                html += f'<br><a href="{url}" target="_blank" style="color: #7c3aed; font-size: 0.9em;">{url}</a>'
            html += '</div>'
        html += '</div>'
        return format_html(html)
    display_concorrentes.short_description = 'Concorrentes (Visualização)'
    
    def display_n8n_analysis(self, obj):
        """Exibe análise N8N de forma formatada"""
        if not obj.n8n_analysis:
            return format_html('<em style="color: #999;">Nenhuma análise recebida</em>')
        
        try:
            # Adicionar resumo
            payload = obj.n8n_analysis.get('payload', [])
            revision_id = obj.n8n_analysis.get('revision_id', 'N/A')
            received_at = obj.n8n_analysis.get('received_at', 'N/A')
            
            campos_analisados = 0
            if payload and len(payload) > 0 and isinstance(payload[0], dict):
                campos_analisados = len(payload[0].keys())
            
            # Contar status
            status_count = {'fraco': 0, 'médio': 0, 'bom': 0}
            if payload and len(payload) > 0:
                for campo_data in payload[0].values():
                    if isinstance(campo_data, dict):
                        status = campo_data.get('status', '')
                        if status in status_count:
                            status_count[status] += 1
            
            html = f'<div style="margin-bottom: 15px; padding: 12px; background: white; border-left: 4px solid #7c3aed; border-radius: 4px;">'
            html += f'<p style="margin: 0 0 8px 0;"><strong>Resumo da Análise:</strong></p>'
            html += f'<p style="margin: 0 0 4px 0; font-size: 0.9em;">📊 <strong>{campos_analisados}</strong> campos analisados</p>'
            html += f'<p style="margin: 0 0 4px 0; font-size: 0.9em;">🔴 <strong>{status_count["fraco"]}</strong> fracos | 🟡 <strong>{status_count["médio"]}</strong> médios | 🟢 <strong>{status_count["bom"]}</strong> bons</p>'
            html += f'<p style="margin: 0 0 4px 0; font-size: 0.85em; color: #666;">Revision ID: <code>{revision_id}</code></p>'
            html += f'<p style="margin: 0; font-size: 0.85em; color: #666;">Recebido em: {received_at}</p>'
            html += '</div>'
            
            # Formatar JSON com indentação
            json_str = json.dumps(obj.n8n_analysis, indent=2, ensure_ascii=False)
            # Limitar tamanho para não sobrecarregar a página
            if len(json_str) > 8000:
                json_str = json_str[:8000] + '\n... (truncado)'
            
            html += f'<div style="font-family: monospace; background: #f5f5f5; padding: 10px; border-radius: 4px; max-height: 500px; overflow-y: auto;">'
            html += f'<pre style="margin: 0; white-space: pre-wrap; word-wrap: break-word; font-size: 0.85em;">{json_str}</pre>'
            html += '</div>'
            
            return format_html(html)
        except Exception as e:
            return format_html(f'<em style="color: #d32f2f;">Erro ao formatar JSON: {str(e)}</em>')
    display_n8n_analysis.short_description = 'Análise N8N (JSON Formatado)'
    
    def display_n8n_compilation(self, obj):
        """Exibe compilação N8N de forma formatada"""
        if not obj.n8n_compilation:
            return format_html('<em style="color: #999;">Nenhuma compilação recebida</em>')
        
        try:
            json_str = json.dumps(obj.n8n_compilation, indent=2, ensure_ascii=False)
            if len(json_str) > 5000:
                json_str = json_str[:5000] + '\n... (truncado)'
            
            html = f'<div style="font-family: monospace; background: #f5f5f5; padding: 10px; border-radius: 4px; max-height: 400px; overflow-y: auto;">'
            html += f'<pre style="margin: 0; white-space: pre-wrap; word-wrap: break-word;">{json_str}</pre>'
            html += '</div>'
            return format_html(html)
        except Exception as e:
            return format_html(f'<em style="color: #d32f2f;">Erro ao formatar JSON: {str(e)}</em>')
    display_n8n_compilation.short_description = 'Compilação N8N (JSON Formatado)'


@admin.register(ReferenceImage)
class ReferenceImageAdmin(admin.ModelAdmin):
    list_display = ['title', 'knowledge_base', 'width', 'height', 'file_size', 'uploaded_by', 'created_at']
    list_filter = ['created_at', 'uploaded_by']
    search_fields = ['title', 'description']
    readonly_fields = ['perceptual_hash', 'file_size', 'width', 'height', 'created_at']


@admin.register(CustomFont)
class CustomFontAdmin(admin.ModelAdmin):
    list_display = ['name', 'font_type', 'file_format', 'uploaded_by', 'created_at']
    list_filter = ['font_type', 'file_format']
    search_fields = ['name']
    readonly_fields = ['created_at']


@admin.register(Typography)
class TypographyAdmin(admin.ModelAdmin):
    list_display = ['usage', 'font_source', 'get_font_name', 'get_font_weight', 'knowledge_base', 'updated_by', 'updated_at']
    list_filter = ['font_source', 'usage', 'knowledge_base']
    search_fields = ['usage', 'google_font_name', 'custom_font__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['knowledge_base', 'order', 'usage']
    
    fieldsets = (
        ('Configuração', {
            'fields': ('knowledge_base', 'usage', 'font_source', 'order')
        }),
        ('Google Fonts', {
            'fields': ('google_font_name', 'google_font_weight', 'google_font_url'),
            'classes': ('collapse',)
        }),
        ('Upload Customizado', {
            'fields': ('custom_font',),
            'classes': ('collapse',)
        }),
        ('Auditoria', {
            'fields': ('created_at', 'updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_font_name(self, obj):
        """Retorna nome da fonte (Google ou Custom)"""
        if obj.font_source == 'google':
            return obj.google_font_name
        elif obj.custom_font:
            return obj.custom_font.name
        return '-'
    get_font_name.short_description = 'Nome da Fonte'
    
    def get_font_weight(self, obj):
        """Retorna peso da fonte"""
        if obj.font_source == 'google':
            return obj.google_font_weight or '400'
        return '-'
    get_font_weight.short_description = 'Peso'
    
    def save_model(self, request, obj, form, change):
        if not change or not obj.updated_by:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Logo)
class LogoAdmin(admin.ModelAdmin):
    list_display = ['name', 'logo_type', 'is_primary', 'file_format', 'uploaded_by', 'created_at']
    list_filter = ['logo_type', 'is_primary']
    search_fields = ['name']
    readonly_fields = ['created_at']


@admin.register(Competitor)
class CompetitorAdmin(admin.ModelAdmin):
    list_display = ['name', 'website', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ColorPalette)
class ColorPaletteAdmin(admin.ModelAdmin):
    list_display = ['name', 'hex_code', 'color_type', 'order', 'knowledge_base']
    list_filter = ['color_type', 'knowledge_base']
    search_fields = ['name', 'hex_code']
    ordering = ['knowledge_base', 'order', 'name']


@admin.register(SocialNetwork)
class SocialNetworkAdmin(admin.ModelAdmin):
    list_display = ['name', 'network_type', 'username', 'is_active', 'order', 'knowledge_base']
    list_filter = ['network_type', 'is_active', 'knowledge_base']
    search_fields = ['name', 'username', 'url']
    ordering = ['knowledge_base', 'order', 'name']


@admin.register(SocialNetworkTemplate)
class SocialNetworkTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'social_network', 'aspect_ratio', 'width', 'height', 'is_active']
    list_filter = ['social_network__network_type', 'is_active']
    search_fields = ['name']
    ordering = ['social_network', 'name']


@admin.register(KnowledgeChangeLog)
class KnowledgeChangeLogAdmin(admin.ModelAdmin):
    list_display = ['block_name', 'field_name', 'user', 'change_summary', 'created_at']
    list_filter = ['block_name', 'created_at']
    search_fields = ['field_name', 'change_summary']
    readonly_fields = ['knowledge_base', 'user', 'block_name', 'field_name', 
                      'old_value', 'new_value', 'change_summary', 'created_at']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
