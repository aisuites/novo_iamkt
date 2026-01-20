from django.contrib import admin
from .models import Project, Approval, ApprovalComment, ProjectContent


class ProjectContentInline(admin.TabularInline):
    model = ProjectContent
    extra = 1
    readonly_fields = ['added_by', 'added_at']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'area', 'owner', 'status', 'start_date', 'end_date', 'created_at']
    list_filter = ['status', 'area', 'created_at']
    search_fields = ['name', 'description', 'tags']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ProjectContentInline]
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('name', 'description', 'area', 'owner')
        }),
        ('Datas', {
            'fields': ('start_date', 'end_date')
        }),
        ('Status e Metadados', {
            'fields': ('status', 'tags', 'budget_usd')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


class ApprovalCommentInline(admin.TabularInline):
    model = ApprovalComment
    extra = 1
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ['id', 'content', 'approval_type', 'requested_by', 'approver', 
                   'decision', 'requested_at', 'decided_at']
    list_filter = ['approval_type', 'decision', 'notification_sent', 'reminder_sent', 'requested_at']
    search_fields = ['content__caption', 'decision_notes']
    readonly_fields = ['requested_at', 'decided_at']
    inlines = [ApprovalCommentInline]
    
    fieldsets = (
        ('Conteúdo', {
            'fields': ('content', 'project')
        }),
        ('Aprovação', {
            'fields': ('approval_type', 'requested_by', 'approver')
        }),
        ('Decisão', {
            'fields': ('decision', 'decision_notes')
        }),
        ('Timestamps', {
            'fields': ('requested_at', 'decided_at')
        }),
        ('Notificações', {
            'fields': ('notification_sent', 'reminder_sent')
        }),
    )


@admin.register(ApprovalComment)
class ApprovalCommentAdmin(admin.ModelAdmin):
    list_display = ['approval', 'user', 'comment', 'has_attachment', 'created_at']
    list_filter = ['has_attachment', 'created_at']
    search_fields = ['comment']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ProjectContent)
class ProjectContentAdmin(admin.ModelAdmin):
    list_display = ['project', 'content', 'added_by', 'added_at']
    list_filter = ['project', 'added_at']
    search_fields = ['project__name', 'content__caption']
    readonly_fields = ['added_by', 'added_at']
