from django.contrib import admin
from .models import (
    KnowledgeBase, InternalSegment, ReferenceImage, CustomFont, Logo, 
    Competitor, ColorPalette, SocialNetwork, SocialNetworkTemplate,
    KnowledgeChangeLog
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
    list_display = ['nome_empresa', 'completude_percentual', 'is_complete', 'updated_at']
    readonly_fields = ['completude_percentual', 'is_complete', 'created_at', 'updated_at']
    inlines = [InternalSegmentInline]
    
    fieldsets = (
        ('Bloco 1: Identidade Institucional', {
            'fields': ('nome_empresa', 'missao', 'visao', 'valores', 'historia')
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
            'fields': ('paleta_cores', 'tipografia')
        }),
        ('Bloco 6: Sites e Redes Sociais', {
            'fields': ('site_institucional', 'redes_sociais', 'templates_redes')
        }),
        ('Bloco 7: Dados e Insights', {
            'fields': ('fontes_confiaveis', 'canais_trends', 'palavras_chave_trends')
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
