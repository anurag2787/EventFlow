from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Activity, Organization, Repository, User, WebhookSubscription


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    readonly_fields = ('created_at',)
    list_display = ('username', 'email', 'is_staff', 'is_active', 'created_at')
    ordering = ('username',)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'repository_count', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at',)

    @admin.display(description='Repositories')
    def repository_count(self, obj):
        return obj.repositories.count()


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'provider', 'organization', 'external_id', 'created_at')
    list_filter = ('provider', 'organization')
    search_fields = ('name', 'external_id', 'organization__name')
    list_select_related = ('organization',)
    readonly_fields = ('created_at', 'external_id')

    @admin.display(description='Repository')
    def display_name(self, obj):
        return f'{obj.organization.name}/{obj.name}'


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = (
        'activity_type',
        'repository_display',
        'actor',
        'target_id',
        'source_provider',
        'source_event_type',
        'source_event_id',
        'source_url',
        'created_at',
    )
    list_filter = ('activity_type', 'source_provider', 'repository__organization')
    search_fields = ('target_id', 'source_event_id', 'source_url', 'repository__name', 'repository__organization__name')
    list_select_related = ('repository', 'repository__organization', 'actor')

    @admin.display(description='Repository')
    def repository_display(self, obj):
        return f'{obj.repository.organization.name}/{obj.repository.name}'


@admin.register(WebhookSubscription)
class WebhookSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('provider', 'organization', 'repository_display', 'active', 'created_at')
    list_filter = ('provider', 'active', 'organization')
    search_fields = ('provider', 'organization__name', 'repository__name')
    list_select_related = ('organization', 'repository')

    @admin.display(description='Repository')
    def repository_display(self, obj):
        return f'{obj.repository.organization.name}/{obj.repository.name}'
