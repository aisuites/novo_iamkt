from django.contrib import admin
from .models import (
    Pauta, Asset, TrendMonitor,
    WebInsight, IAModelUsage, ContentMetrics,
    HeygenAvatar, VideoAvatar,
)
# NOTA: Post foi movido para apps.posts.admin


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
    
    def save_model(self, request, obj, form, change):
        """Auto-preencher organization e validar quota ao salvar"""
        # Auto-preencher organization
        if not obj.organization_id and hasattr(request, 'organization'):
            obj.organization = request.organization
        
        # Validar quota apenas ao criar (não ao editar)
        if not change and obj.organization:
            can_create, error_code, message = obj.organization.can_create_pauta()
            if not can_create:
                from django.contrib import messages
                messages.error(request, f'❌ Não foi possível criar a pauta: {message}')
                # Impedir salvamento retornando sem chamar super()
                return
        
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        """Filtrar por organization do usuário"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request, 'organization') and request.organization:
            return qs.filter(organization=request.organization)
        return qs.none()


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


class HeygenLookInline(admin.TabularInline):
    from .models import HeygenLook
    model = HeygenLook
    extra = 0
    fields = ['name', 'look_id', 'avatar_type', 'preview_image',
              'is_active', 'is_default']
    readonly_fields = ['avatar_type']


@admin.register(HeygenAvatar)
class HeygenAvatarAdmin(admin.ModelAdmin):
    """Apresentadores HeyGen por org — cadastro pela equipe interna.
    Preencha group_id + voice_id e use a ação "Sincronizar looks" para
    puxar os looks da HeyGen (entram INATIVOS; ative os que o cliente
    pode usar). IDs: command `heygen_setup` ou plataforma HeyGen."""
    list_display = ['name', 'organization', 'group_id', 'voice_id', 'engine',
                    'is_active', 'looks_count']
    list_filter = ['organization', 'is_active', 'engine']
    search_fields = ['name', 'group_id', 'organization__name']
    inlines = [HeygenLookInline]
    actions = ['sync_looks']

    @admin.display(description='Looks (ativos/total)')
    def looks_count(self, obj):
        total = obj.looks.count()
        active = obj.looks.filter(is_active=True).count()
        return f'{active}/{total}'

    @admin.action(description='Sincronizar looks da HeyGen')
    def sync_looks(self, request, queryset):
        from django.contrib import messages
        from apps.content.services import heygen
        for avatar in queryset:
            try:
                r = heygen.sync_group_looks(avatar)
                messages.success(
                    request,
                    f'{avatar.name}: {r["created"]} novos (inativos), '
                    f'{r["deactivated"]} desativados, '
                    f'{r["remote_total"]} looks no grupo.')
            except heygen.HeygenError as e:
                messages.error(request, f'{avatar.name}: {e}')


@admin.register(VideoAvatar)
class VideoAvatarAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'avatar', 'look', 'created_by', 'status',
                    'video_duration', 'cost_usd', 'created_at']
    list_filter = ['organization', 'status']
    search_fields = ['script_text', 'heygen_video_id', 'organization__name']
    readonly_fields = ['heygen_video_id', 'idempotency_key', 'estimated_duration',
                       'cost_usd', 'error_code', 'error_message',
                       'created_at', 'updated_at', 'delivered_at']
