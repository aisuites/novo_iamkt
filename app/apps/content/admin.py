from django.contrib import admin
from .models import (
    Pauta, GeneratedContent, Asset, TrendMonitor, 
    WebInsight, IAModelUsage, ContentMetrics
)


@admin.register(Pauta)
class PautaAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'area', 'objective', 'status', 'created_at']
    list_filter = ['status', 'objective', 'area', 'created_at']
    search_fields = ['title', 'theme', 'description']
    readonly_fields = ['created_at', 'completed_at']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('user', 'area', 'theme', 'target_audience', 'objective', 'additional_context')
        }),
        ('Conteúdo Gerado', {
            'fields': ('title', 'description', 'key_points', 'suggested_formats', 
                      'research_sources', 'trends_related')
        }),
        ('Status', {
            'fields': ('status', 'error_message', 'created_at', 'completed_at')
        }),
    )


@admin.register(GeneratedContent)
class GeneratedContentAdmin(admin.ModelAdmin):
    list_display = ['id', 'content_type', 'social_network', 'user', 'area', 
                   'ia_provider', 'status', 'created_at']
    list_filter = ['content_type', 'social_network', 'ia_provider', 'status', 'area', 'created_at']
    search_fields = ['caption', 'image_prompt']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('user', 'area', 'pauta', 'content_type', 'social_network')
        }),
        ('IA Utilizada', {
            'fields': ('ia_provider', 'ia_model_text', 'ia_model_image')
        }),
        ('Conteúdo', {
            'fields': ('caption', 'hashtags')
        }),
        ('Imagem', {
            'fields': ('has_image', 'image_s3_key', 'image_s3_url', 'image_prompt', 
                      'image_width', 'image_height')
        }),
        ('Status', {
            'fields': ('status', 'created_at', 'updated_at')
        }),
    )


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ['title', 'asset_type', 'user', 'area', 'file_size', 'is_active', 'created_at']
    list_filter = ['asset_type', 'is_active', 'area', 'created_at']
    search_fields = ['title', 'description', 'tags']
    readonly_fields = ['file_size', 'content_type', 'width', 'height', 'created_at']


@admin.register(TrendMonitor)
class TrendMonitorAdmin(admin.ModelAdmin):
    list_display = ['keyword', 'source', 'trend_score', 'relevance', 'is_active', 
                   'alert_sent', 'created_at']
    list_filter = ['source', 'relevance', 'is_active', 'alert_sent', 'created_at']
    search_fields = ['keyword', 'ia_analysis']
    readonly_fields = ['created_at']


@admin.register(WebInsight)
class WebInsightAdmin(admin.ModelAdmin):
    list_display = ['query', 'search_type', 'user', 'area', 'status', 'created_at']
    list_filter = ['search_type', 'status', 'area', 'created_at']
    search_fields = ['query', 'summary']
    readonly_fields = ['created_at', 'completed_at']


@admin.register(IAModelUsage)
class IAModelUsageAdmin(admin.ModelAdmin):
    list_display = ['provider', 'model', 'operation', 'user', 'area', 
                   'tokens_total', 'cost_usd', 'execution_time_seconds', 'status', 'started_at']
    list_filter = ['provider', 'operation', 'status', 'area', 'started_at']
    search_fields = ['model', 'user__username']
    readonly_fields = ['user', 'area', 'content', 'provider', 'model', 'operation',
                      'tokens_input', 'tokens_output', 'tokens_total', 'cost_usd',
                      'execution_time_seconds', 'started_at', 'completed_at', 'status']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ContentMetrics)
class ContentMetricsAdmin(admin.ModelAdmin):
    list_display = ['content', 'creation_duration_seconds', 'approval_duration_seconds',
                   'adjustment_count', 'total_cost_usd', 'total_tokens']
    list_filter = ['created_at']
    readonly_fields = ['content', 'creation_started_at', 'creation_completed_at',
                      'creation_duration_seconds', 'submitted_for_approval_at',
                      'approved_at', 'approval_duration_seconds', 'adjustment_count',
                      'total_adjustment_time_seconds', 'total_cost_usd', 'total_tokens',
                      'created_at', 'updated_at']
    
    def has_add_permission(self, request):
        return False
