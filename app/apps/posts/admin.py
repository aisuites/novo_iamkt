from django.contrib import admin
from .models import Post, PostImage, PostReferenceImage, PostChangeRequest, PostFormat


class PostImageInline(admin.TabularInline):
    model = PostImage
    extra = 1
    fields = ('image_file', 's3_url', 'order')
    readonly_fields = ('s3_url',)
    verbose_name = 'Imagem do Post'
    verbose_name_plural = 'Imagens do Post'


class PostReferenceImageInline(admin.TabularInline):
    model = PostReferenceImage
    extra = 0
    fields = ('original_name', 's3_url', 'order')
    readonly_fields = ('original_name', 's3_url', 's3_key')
    verbose_name = 'Imagem de Referência'
    verbose_name_plural = 'Imagens de Referência'
    
    def has_add_permission(self, request, obj=None):
        # Não permitir adicionar manualmente (são criadas via modal)
        return False


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    inlines = [PostReferenceImageInline, PostImageInline]
    list_display = [
        'id',
        'title',
        'social_network',
        'content_type',
        'status',
        'user',
        'organization',
        'cost_usd_display',
        'cost_brl_display',
        'created_at',
    ]
    list_filter = [
        'status',
        'social_network',
        'content_type',
        'is_carousel',
        'created_at',
    ]
    search_fields = [
        'title',
        'subtitle',
        'caption',
        'requested_theme',
        'user__email',
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
        'organization',
        'image_s3_url',
        'image_s3_key',
        'has_image',
        'total_text_cost_usd',
        'total_image_cost_usd',
        'total_cost_usd',
        'cost_brl_display',
        'ai_usage_log_pretty',
    ]
    fieldsets = (
        ('Informações Básicas', {
            'fields': (
                'user',
                'area',
                'pauta',
                'organization',
            )
        }),
        ('Conteúdo', {
            'fields': (
                'requested_theme',
                'title',
                'subtitle',
                'caption',
                'hashtags',
                'cta',
                'cta_requested',
            )
        }),
        ('Configurações', {
            'fields': (
                'social_network',
                'content_type',
                'formats',
                'is_carousel',
                'image_count',
                'slides_metadata',
            )
        }),
        ('IA', {
            'fields': (
                'ia_provider',
                'ia_model_text',
                'ia_model_image',
                'thread_id',
            )
        }),
        ('Imagem', {
            'fields': (
                'post_format',
                'has_image',
                'image_s3_url',
                'image_s3_key',
                'image_prompt',
                'image_width',
                'image_height',
            ),
            'description': 'Campos de referência da imagem principal. Para fazer upload de imagens, use a seção "IMAGENS DO POST" abaixo.'
        }),
        ('Status e Revisões', {
            'fields': (
                'status',
                'revisions_remaining',
            )
        }),
        ('Custos de IA', {
            'fields': (
                'total_text_cost_usd',
                'total_image_cost_usd',
                'total_cost_usd',
                'cost_brl_display',
                'ai_usage_log_pretty',
            ),
            'description': 'Custos acumulados de chamadas Claude/Gemini neste post. Histórico granular abaixo.',
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(organization=request.user.organization)

    # ---- Display helpers para custos de IA ----

    def cost_usd_display(self, obj):
        return f'${obj.total_cost_usd:.4f}' if obj.total_cost_usd else '—'
    cost_usd_display.short_description = 'Custo USD'
    cost_usd_display.admin_order_field = 'total_cost_usd'

    def cost_brl_display(self, obj):
        from django.conf import settings as dj_settings
        rate = float(getattr(dj_settings, 'USD_TO_BRL_RATE', 5.80))
        brl = float(obj.total_cost_usd or 0) * rate
        return f'R$ {brl:.4f}' if brl else '—'
    cost_brl_display.short_description = 'Custo BRL'

    def ai_usage_log_pretty(self, obj):
        """Renderiza ai_usage_log como tabela HTML legivel."""
        from django.utils.html import format_html
        log = obj.ai_usage_log or []
        if not log:
            return '—'
        rows = []
        for entry in log:
            ts = (entry.get('timestamp') or '')[:19].replace('T', ' ')
            rows.append(
                f'<tr>'
                f'<td style="padding:4px 8px">{ts}</td>'
                f'<td style="padding:4px 8px">{entry.get("step", "?")}</td>'
                f'<td style="padding:4px 8px">{entry.get("model", "?")}</td>'
                f'<td style="padding:4px 8px;text-align:right">{entry.get("input_tokens", 0)}</td>'
                f'<td style="padding:4px 8px;text-align:right">{entry.get("output_tokens", 0)}</td>'
                f'<td style="padding:4px 8px;text-align:right">{entry.get("images_generated", 0)}</td>'
                f'<td style="padding:4px 8px;text-align:right">${entry.get("cost_usd", 0):.4f}</td>'
                f'<td style="padding:4px 8px;text-align:right">R$ {entry.get("cost_brl", 0):.4f}</td>'
                f'</tr>'
            )
        table = (
            '<table style="border-collapse:collapse;width:100%;font-size:12px">'
            '<thead><tr style="background:#f0f0f0">'
            '<th style="padding:4px 8px;text-align:left">Quando</th>'
            '<th style="padding:4px 8px;text-align:left">Etapa</th>'
            '<th style="padding:4px 8px;text-align:left">Modelo</th>'
            '<th style="padding:4px 8px;text-align:right">In tokens</th>'
            '<th style="padding:4px 8px;text-align:right">Out tokens</th>'
            '<th style="padding:4px 8px;text-align:right">Imagens</th>'
            '<th style="padding:4px 8px;text-align:right">USD</th>'
            '<th style="padding:4px 8px;text-align:right">BRL</th>'
            '</tr></thead><tbody>'
            + ''.join(rows) +
            '</tbody></table>'
        )
        return format_html(table)
    ai_usage_log_pretty.short_description = 'Histórico de uso de IA'


@admin.register(PostChangeRequest)
class PostChangeRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'post',
        'change_type',
        'is_initial',
        'requester_name',
        'requester_email',
        'created_at',
    ]
    list_filter = [
        'change_type',
        'is_initial',
        'created_at',
    ]
    search_fields = [
        'message',
        'requester_name',
        'requester_email',
        'post__title',
    ]
    readonly_fields = [
        'created_at',
    ]
    fieldsets = (
        ('Solicitação', {
            'fields': (
                'post',
                'change_type',
                'is_initial',
                'message',
            )
        }),
        ('Solicitante', {
            'fields': (
                'requester_name',
                'requester_email',
            )
        }),
        ('Timestamp', {
            'fields': (
                'created_at',
            )
        }),
    )


@admin.register(PostFormat)
class PostFormatAdmin(admin.ModelAdmin):
    list_display = ['social_network', 'name', 'width', 'height', 'aspect_ratio', 'is_active', 'order']
    list_filter = ['social_network', 'is_active']
    list_editable = ['order', 'is_active']
    search_fields = ['name', 'social_network']
    ordering = ['social_network', 'order', 'name']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('social_network', 'name', 'is_active', 'order')
        }),
        ('Dimensões', {
            'fields': ('width', 'height', 'aspect_ratio')
        }),
    )
