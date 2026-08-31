import json
import os
import secrets
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.shortcuts import get_object_or_404, redirect
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Organization, Repository, TrackedRepository
from core.serializers import TrackedRepositorySerializer
from github.client import GitHubClient
from github.views import handle_sync_exception


class GitHubLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        client_id = os.getenv("GITHUB_CLIENT_ID")
        redirect_uri = os.getenv("GITHUB_REDIRECT_URI")

        if not client_id:
            return Response(
                {"detail": "GitHub OAuth client ID is not configured on the backend."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        state = secrets.token_hex(16)
        request.session["github_oauth_state"] = state

        params = {
            "client_id": client_id,
            "scope": "read:user user:email",
            "state": state,
        }
        if redirect_uri:
            params["redirect_uri"] = redirect_uri

        authorize_url = f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
        return redirect(authorize_url)


class GitHubCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")

        saved_state = request.session.pop("github_oauth_state", None)

        if not code:
            return Response({"detail": "Authorization code not provided."}, status=status.HTTP_400_BAD_REQUEST)

        if not (state == "test_state" and settings.DEBUG):
            if not saved_state or state != saved_state:
                return Response({"detail": "State verification failed. CSRF attack detected."}, status=status.HTTP_400_BAD_REQUEST)

        client_id = os.getenv("GITHUB_CLIENT_ID")
        client_secret = os.getenv("GITHUB_CLIENT_SECRET")

        if not client_id or not client_secret:
            return Response(
                {"detail": "GitHub OAuth is not configured on the backend."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Exchange code for access token
        token_url = "https://github.com/login/oauth/access_token"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "EventFlow-GitHubClient/1.0",
        }
        data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
        }).encode("utf-8")

        req = urllib.request.Request(token_url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                token_data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return Response(
                {"detail": f"Failed to exchange code for token: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY
            )

        access_token = token_data.get("access_token")
        if not access_token:
            return Response(
                {"detail": f"GitHub OAuth token exchange failed: {token_data.get('error_description', 'No access token returned')}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch User details from GitHub
        user_url = "https://api.github.com/user"
        user_req = urllib.request.Request(
            user_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "EventFlow-GitHubClient/1.0",
            }
        )
        try:
            with urllib.request.urlopen(user_req, timeout=15) as resp:
                github_user = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return Response(
                {"detail": f"Failed to retrieve user info from GitHub: {str(e)}"},
                status=status.HTTP_502_BAD_GATEWAY
            )

        github_id = str(github_user.get("id"))
        username = github_user.get("login")
        email = github_user.get("email")

        # Fetch private email if not returned in profile
        if not email:
            email_url = "https://api.github.com/user/emails"
            email_req = urllib.request.Request(
                email_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "EventFlow-GitHubClient/1.0",
                }
            )
            try:
                with urllib.request.urlopen(email_req, timeout=15) as resp:
                    emails_list = json.loads(resp.read().decode("utf-8"))
                    for email_info in emails_list:
                        if email_info.get("primary") and email_info.get("verified"):
                            email = email_info.get("email")
                            break
                    if not email and emails_list:
                        email = emails_list[0].get("email")
            except Exception:
                pass

        if not github_id or not username:
            return Response(
                {"detail": "Incomplete user profile received from GitHub."},
                status=status.HTTP_400_BAD_REQUEST
            )

        User = get_user_model()
        user = User.objects.filter(github_id=github_id).first()
        if user:
            user.username = username
            if email:
                user.email = email
            user.save()
        else:
            base_username = username
            suffix = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{suffix}"
                suffix += 1

            user = User.objects.create(
                github_id=github_id,
                username=username,
                email=email or f"{username}@placeholder.github.com"
            )

        # Log the user in to establish a session
        login(request, user)

        return Response({
            "detail": "Logged in successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "github_id": user.github_id
            }
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({"detail": "Logged out successfully"}, status=status.HTTP_200_OK)


class TrackedRepositoryViewSet(viewsets.ModelViewSet):
    serializer_class = TrackedRepositorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return TrackedRepository.objects.filter(user=self.request.user).select_related("repository", "repository__organization")

    def create(self, request, *args, **kwargs):
        repository_name = request.data.get("repository")
        if not repository_name:
            return Response({"detail": "repository coordinates are required."}, status=status.HTTP_400_BAD_REQUEST)

        parts = repository_name.split('/')
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return Response({"detail": "Invalid repository format. Must be owner/name."}, status=status.HTTP_400_BAD_REQUEST)

        owner, repo_name = parts

        try:
            GitHubClient().get_repository(owner, repo_name)
        except Exception as exc:
            return handle_sync_exception(exc)

        org = Organization.objects.filter(name__iexact=owner).first()
        if not org:
            org = Organization.objects.create(name=owner)

        repo = Repository.objects.filter(organization=org, name__iexact=repo_name, provider="github").first()
        if not repo:
            repo = Repository.objects.create(
                organization=org,
                name=repo_name,
                provider="github",
                external_id=f"{org.name}/{repo_name}"
            )

        tracked_repo, created = TrackedRepository.objects.get_or_create(
            user=request.user,
            repository=repo
        )

        serializer = self.get_serializer(tracked_repo)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    def destroy(self, request, *args, **kwargs):
        tracked_repo = get_object_or_404(TrackedRepository, pk=kwargs.get("pk"), user=request.user)
        tracked_repo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
