from django.urls import path

from .views import repository_sync, sync_all_repositories

urlpatterns = [
    path("repositories/<int:repository_id>/sync/", repository_sync, name="repository-sync"),
    path("repositories/sync-all/", sync_all_repositories, name="repository-sync-all"),
    path("sync/all/", sync_all_repositories, name="repository-sync-all-slash"),
    path("sync/all", sync_all_repositories, name="repository-sync-all-no-slash"),
]

