# 📡 EventFlow - Complete Project Information Guide

> **For anyone who is new to this project** - this document gives you a full end-to-end understanding of what EventFlow is, why it was built, how it works, what technologies it uses, what features have been implemented, and how to run and test it.

---

## Table of Contents

1. [What is EventFlow?](#1-what-is-eventflow)
2. [Why Was It Built?](#2-why-was-it-built)
3. [High-Level Architecture](#3-high-level-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Project Folder Structure](#5-project-folder-structure)
6. [Data Models (Database Schema)](#6-data-models-database-schema)
7. [Features Implemented (Phase-by-Phase)](#7-features-implemented-phase-by-phase)
8. [Complete API Reference](#8-complete-api-reference)
9. [How GitHub Data Flows Through the System](#9-how-github-data-flows-through-the-system)
10. [Performance & Scalability](#10-performance--scalability)
11. [Security Mechanisms](#11-security-mechanisms)
12. [How to Run the Project Locally](#12-how-to-run-the-project-locally)
13. [Environment Variables Reference](#13-environment-variables-reference)
14. [Key Design Decisions Explained](#14-key-design-decisions-explained)
15. [Glossary of Terms](#15-glossary-of-terms)

---

## 1. What is EventFlow?

**EventFlow** is a **backend web application** that acts as a **unified developer activity tracking system** for GitHub repositories.

In simple words:

> EventFlow connects to GitHub, pulls all developer activities (like opening pull requests, pushing commits, creating releases, opening/closing issues), normalizes them into a consistent format, stores them in a database, and exposes clean REST APIs so that any frontend or tool can query, filter, and analyze developer activity over time.

Think of it like a **personal analytics dashboard** for GitHub activity - you tell it which repositories to watch, it continuously syncs their events, and you can then query that data in many ways (by date, by activity type, by repository, etc.).

---

## 2. Why Was It Built?

GitHub's native APIs are powerful, but they have some limitations for analytics use cases:

- **Rate limits**: GitHub limits how many API calls you can make per hour (60 req/hr unauthenticated, 5,000 req/hr with a token).
- **No aggregation**: GitHub doesn't let you query "all PR opens across 10 repos between these dates".
- **No unified stream**: Activity from PRs, issues, commits, and releases are all separate GitHub API endpoints.
- **No persistence**: Once you query, you have to query again - there's no database behind it.

EventFlow solves all of this by:
- **Polling GitHub** and ingesting raw events into a **PostgreSQL database**.
- **Normalizing** all events into a consistent schema (`PR_OPENED`, `COMMIT_PUSHED`, etc.).
- **Caching** queries with Redis to serve responses in < 2ms.
- **Rate limiting** its own API to prevent abuse.
- **Authenticating users** via GitHub OAuth so each user sees only their tracked repositories.

---

## 3. High-Level Architecture

EventFlow is composed of **four Docker containers** working together:

```
┌─────────────────────────────────────────────────────────────────┐
│                        EventFlow System                         │
│                                                                 │
│  ┌──────────────┐    ┌────────────────┐    ┌────────────────┐  │
│  │   Django     │    │   Celery       │    │     Redis      │  │
│  │   Backend    │───▶│   Worker       │◀───│   (Broker +    │  │
│  │  (Port 8000) │    │  (Async Jobs)  │    │    Cache)      │  │
│  └──────┬───────┘    └────────────────┘    └────────────────┘  │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐                                               │
│  │  PostgreSQL  │                                               │
│  │  Database    │                                               │
│  │  (Port 5432) │                                               │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
   GitHub REST API
   (External - api.github.com)
```

### Data Flow Summary

```
GitHub REST API
      │
      │  (HTTP polling via GitHubClient)
      ▼
 github/client.py  →  github/normalizers.py  →  github/services.py
      │                                               │
      │                                               ▼
      │                                    PostgreSQL (Activity saved)
      │
      ▼
 POST /api/events/ingest/
      │
      ├── Store raw Event (PENDING) in PostgreSQL
      │
      └── Queue task to Celery via Redis broker
                    │
                    ▼
           Celery Worker picks up task
                    │
                    ▼
         EventProcessorService.process_event()
                    │
                    ▼
         Activity saved to PostgreSQL (COMPLETED)
                    │
                    ▼
         Redis cache invalidated automatically
```

---

## 4. Technology Stack

### Core Technologies

| Technology | Version | Purpose |
|:---|:---|:---|
| **Python** | 3.13 | Primary programming language |
| **Django** | 5.1 | Web framework - handles models, admin, routing, sessions, auth |
| **Django REST Framework (DRF)** | 3.15.0 | REST API toolkit - ViewSets, Serializers, Pagination, Throttling |
| **PostgreSQL** | 17 | Primary relational database - stores all persistent data |
| **Redis** | 7 (Alpine) | Dual-purpose: (1) Celery message broker, (2) API response cache |
| **Celery** | 5.4.0 | Distributed async task queue - background event processing |
| **psycopg** | 3.3.4 | Modern PostgreSQL adapter for Python (async-ready) |
| **django-filter** | 24.1 | Declarative query filtering for DRF viewsets |
| **Docker + Docker Compose** | - | Containerization and local orchestration of all services |

### Supporting Libraries

| Library | Purpose |
|:---|:---|
| `redis` (Python client) | Connecting Django/Celery to Redis |
| `asgiref` | ASGI compatibility layer for Django |
| `sqlparse` | SQL parsing utilities |
| `typing_extensions` | Enhanced Python type hints |

### Infrastructure

| Tool | Purpose |
|:---|:---|
| **Docker** | Containerizes all services into isolated environments |
| **Docker Compose** | Defines and orchestrates multi-container setup (`compose.yml`) |
| **Makefile** | Shortcut commands for common operations (`make run`, `make migrate`, etc.) |
| **GitHub REST API** | External data source (`api.github.com/repos/{owner}/{repo}/events`) |
| **GitHub OAuth 2.0** | User authentication - users log in with their GitHub account |

---

## 5. Project Folder Structure

```
Event_FLow/
├── .env                    # Secret environment variables (NOT committed to git)
├── .env.example            # Template for .env file
├── Dockerfile              # Docker image build instructions for the backend
├── compose.yml             # Docker Compose - defines all 4 services
├── Makefile                # Shortcut commands (make run, make migrate, etc.)
├── TEST.md                 # Developer testing guide and API examples
└── backend/
    ├── manage.py           # Django management CLI entry point
    ├── requirements.txt    # Python dependencies
    │
    ├── config/             # Root Django project configuration
    │   ├── settings.py     # All Django settings (DB, cache, auth, REST framework)
    │   ├── urls.py         # Master URL router - delegates to each app's urls.py
    │   ├── celery.py       # Celery app configuration (broker + result backend)
    │   ├── __init__.py     # Loads Celery app when Django starts
    │   ├── wsgi.py         # WSGI entry point for production servers
    │   └── asgi.py         # ASGI entry point for async servers
    │
    ├── core/               # Main domain application
    │   ├── models.py       # All database models (User, Repository, Activity, Event, etc.)
    │   ├── serializers.py  # DRF serializers - convert models to/from JSON
    │   ├── views/          # API views - split by resource for clarity
    │   │   ├── __init__.py    # Re-exports all views (keeps urls.py import-clean)
    │   │   ├── activities.py  # ActivityViewSet, MyActivityViewSet
    │   │   ├── events.py      # EventViewSet
    │   │   └── auth.py        # GitHubLoginView, LogoutView, TrackedRepositoryViewSet
    │   ├── services.py     # Business logic layer (EventProcessorService)
    │   ├── tasks.py        # Celery async tasks (process_event_task)
    │   ├── throttling.py   # Redis-backed rate limiter (RedisRateThrottle)
    │   ├── urls.py         # URL routing for core API endpoints
    │   ├── admin.py        # Django Admin panel registrations and customizations
    │   ├── apps.py         # Core app configuration
    │   └── management/
    │       └── commands/
    │           └── seed_performance_data.py  # CLI to generate 100K test records
    │
    └── github/             # GitHub integration application
        ├── client.py       # Raw HTTP client for GitHub REST API (with retries, rate-limit handling)
        ├── normalizers.py  # Translates raw GitHub event payloads into standardized Activity format
        ├── services.py     # Repository sync orchestration (single + bulk sync)
        ├── views.py        # Sync API endpoints (trigger sync for repo or all repos)
        ├── urls.py         # URL routing for GitHub sync endpoints
        ├── exceptions.py   # Custom exception types (GitHubRateLimitError, GitHubTimeoutError)
        ├── models.py       # (Placeholder - GitHub module uses core models)
        └── admin.py        # GitHub admin registrations
```

---

## 6. Data Models (Database Schema)

EventFlow has **7 database tables** (Django models). Here is what each one stores:

---

### `User` (extends Django's AbstractUser)
Stores authenticated users. Extended with a `github_id` field to link to GitHub identities.

| Field | Type | Description |
|:---|:---|:---|
| `id` | AutoField | Primary key |
| `username` | CharField | GitHub username |
| `email` | EmailField | GitHub email address |
| `github_id` | CharField (unique) | GitHub's numeric user ID |
| `created_at` | DateTimeField | When the user first logged in |

---

### `Organization`
Represents a GitHub organization or user account that owns repositories.

| Field | Type | Description |
|:---|:---|:---|
| `id` | AutoField | Primary key |
| `name` | CharField | Organization/username (e.g., `"owasp"`, `"octocat"`) |
| `created_at` | DateTimeField | Record creation timestamp |

---

### `Repository`
Represents a GitHub repository being tracked by EventFlow.

| Field | Type | Description |
|:---|:---|:---|
| `id` | AutoField | Primary key |
| `organization` | ForeignKey → Organization | Which org owns this repo |
| `name` | CharField | Repository name (e.g., `"nest"`) |
| `external_id` | CharField | Full `owner/name` identifier (e.g., `"owasp/nest"`) |
| `provider` | CharField | Always `"github"` for now |
| `last_synced_at` | DateTimeField | When sync last ran |
| `last_sync_status` | CharField | `NEVER` / `IN_PROGRESS` / `SUCCESS` / `FAILED` |
| `last_sync_error` | TextField | Error message if last sync failed |
| `created_at` | DateTimeField | Record creation timestamp |

---

### `Activity`
The **core record** - represents a single normalized developer action on a repository.

| Field | Type | Description |
|:---|:---|:---|
| `id` | AutoField | Primary key |
| `repository` | ForeignKey → Repository | Which repository this activity belongs to |
| `actor` | ForeignKey → User (nullable) | Who performed the action |
| `activity_type` | CharField | Normalized type: `PR_OPENED`, `COMMIT_PUSHED`, etc. |
| `target_id` | CharField | PR number, issue number, commit SHA, etc. |
| `source_provider` | CharField | Always `"github"` |
| `source_event_id` | CharField | GitHub's raw event ID (for deduplication) |
| `source_event_type` | CharField | Raw GitHub event type (e.g., `PullRequestEvent`) |
| `source_url` | URLField | Direct link to the PR/issue/commit on GitHub |
| `metadata` | JSONField | Extra context (PR title, branch ref, release tag, etc.) |
| `created_at` | DateTimeField | When the activity was recorded |

**Database Constraints on Activity:**
- `UniqueConstraint(repository, source_provider, source_event_id)` - prevents duplicate activities.
- **Composite Indexes** for high-performance queries:
  - `idx_activity_repo_created` → `(repository_id, created_at DESC)`
  - `idx_activity_actor_created` → `(actor_id, created_at DESC)`
  - `idx_activity_type_created` → `(activity_type, created_at DESC)`

---

### `Event`
Stores **raw, unprocessed** events as they come in from GitHub (before normalization into Activities).

| Field | Type | Description |
|:---|:---|:---|
| `id` | AutoField | Primary key |
| `repository` | ForeignKey → Repository | Associated repository |
| `provider` | CharField | Always `"github"` |
| `event_id` | CharField | GitHub's raw event ID |
| `event_type` | CharField | Raw type like `PullRequestEvent` |
| `payload` | JSONField | The full raw GitHub event JSON |
| `status` | CharField | `PENDING` → `PROCESSING` → `COMPLETED` / `FAILED` |
| `retry_count` | IntegerField | How many processing attempts have occurred |
| `max_retries` | IntegerField | Maximum allowed retry attempts (default: 3) |
| `next_retry_at` | DateTimeField | When to retry next (used by exponential backoff) |
| `last_error` | TextField | Last processing error message |
| `created_at` / `updated_at` | DateTimeField | Timestamps |

---

### `EventProcessingAttempt`
Audit log - records each individual attempt to process an `Event`.

| Field | Type | Description |
|:---|:---|:---|
| `id` | AutoField | Primary key |
| `event` | ForeignKey → Event | Which event was being processed |
| `attempt_number` | IntegerField | 1, 2, 3, … |
| `status` | CharField | `SUCCESS` or `FAILED` |
| `error` | TextField | Error message if failed |
| `started_at` | DateTimeField | When this attempt started |
| `completed_at` | DateTimeField | When this attempt finished |

---

### `TrackedRepository`
Links an authenticated `User` to a `Repository` they want to monitor personally.

| Field | Type | Description |
|:---|:---|:---|
| `id` | AutoField | Primary key |
| `user` | ForeignKey → User | The authenticated user |
| `repository` | ForeignKey → Repository | The repository they are tracking |
| `created_at` | DateTimeField | When tracking started |
| `last_synced_at` | DateTimeField | Last time this user's tracked repo was synced |

**Constraint:** `unique_together(user, repository)` - a user can only track the same repo once.

---

### `WebhookSubscription`
(Planned/scaffolded) Stores webhook subscription records for future real-time GitHub webhook integration.

| Field | Type | Description |
|:---|:---|:---|
| `organization` | ForeignKey → Organization | Related org |
| `repository` | ForeignKey → Repository | Related repo |
| `provider` | CharField | `"github"` |
| `secret` | CharField | Webhook secret for HMAC validation |
| `active` | BooleanField | Whether this subscription is active |

---

## 7. Features Implemented (Phase-by-Phase)

EventFlow was built incrementally across 15 phases. Here's a plain-English explanation of each:

---

### Phase 1–3: Foundation
- **Django project scaffolding** with modular app structure (`core`, `github`, `config`).
- **PostgreSQL database** connected via `psycopg`.
- **Core data models** defined: `Organization`, `Repository`, `Activity`, `WebhookSubscription`.
- **Django Admin** configured to manage all models visually at `http://localhost:8000/admin/`.

---

### Phase 4: GitHub REST API Integration
- **`GitHubClient`** (`github/client.py`) - A raw Python HTTP client (using `urllib`) that calls `https://api.github.com/repos/{owner}/{repo}/events`.
- **`GitHubEventNormalizer`** (`github/normalizers.py`) - Translates raw GitHub event JSON into normalized `Activity` records.
- **Sync APIs** - `POST /api/github/repositories/{id}/sync/` and `POST /api/github/repositories/sync-all/` trigger data ingestion.

**Normalized Event Type Mapping:**

| Raw GitHub Event | Action | Normalized Type |
|:---|:---|:---|
| `PullRequestEvent` | `opened` | `PR_OPENED` |
| `PullRequestEvent` | `closed` + merged | `PR_MERGED` |
| `PullRequestEvent` | `closed` + not merged | `PR_CLOSED` |
| `IssuesEvent` | `opened` | `ISSUE_OPENED` |
| `IssuesEvent` | `closed` | `ISSUE_CLOSED` |
| `PushEvent` | - | `COMMIT_PUSHED` |
| `ReleaseEvent` | `published` | `RELEASE_PUBLISHED` |

---

### Phase 5: Reliability - Retries & Dead-Letter State
- Every event goes through **up to 3 processing attempts** before being dead-lettered.
- **Exponential backoff** scheduling:
  - Attempt 1 fails → retry in 30 seconds
  - Attempt 2 fails → retry in 60 seconds
  - Attempt 3 fails → status = `FAILED` (dead-letter), no more retries
- Every attempt is stored in `EventProcessingAttempt` for full auditability.

---

### Phase 6: Idempotency & Database-Enforced Uniqueness
- The system guarantees that **no duplicate activity is ever created**, even if the same GitHub event is received 5 times simultaneously.
- This is enforced at the **database level** using `UniqueConstraint` on both `Event` and `Activity` tables - not just application-level checks.
- **Idempotency test endpoint** (`POST /api/events/test_idempotency/`) fires 5 concurrent requests and proves only 1 Event and 1 Activity are created.

---

### Phase 7: GitHub Sync Reliability Features
- **Retry with Exponential Backoff** on outbound GitHub API calls (up to 3 retries for 5xx errors).
- **Rate-Limit Fail-Fast** - immediately raises `GitHubRateLimitError` on HTTP 429 or `X-RateLimit-Remaining: 0`, stopping further API calls.
- **Timeout Protection** - every GitHub API request has a 15-second hard timeout.
- **Partial Failure Isolation** - in bulk sync, if one repository fails, all other repositories continue and succeed independently.

---

### Phase 8: PostgreSQL Performance Indexing
- Added **B-Tree composite indexes** on the `Activity` table to accelerate the most common query patterns.
- **Performance results on 100,000+ records:**

| Query Pattern | Before Index | After Index | Speedup |
|:---|:---|:---|:---|
| Filter by repository + sort by date | 13.089 ms | 0.100 ms | **130.8x faster** |
| Filter by actor + sort by date | 12.373 ms | 0.068 ms | **181.9x faster** |
| Filter by activity type + sort by date | 11.400 ms | 0.074 ms | **154.0x faster** |

- A **data seeder management command** (`seed_performance_data`) can generate 100,000 realistic records for benchmarking.

---

### Phase 9: Asynchronous Event Processing with Celery + Redis
- **Decoupled ingestion from processing**: The ingestion endpoint (`POST /api/events/ingest/`) now responds in **< 20ms** with HTTP 202, then queues processing to a Celery worker.
- **Redis** acts as the **message broker** - tasks are placed in a Redis queue, and the Celery worker picks them up independently.
- **Celery Worker** (`celery-eventflow` container) processes events in the background and updates the `Event` status to `COMPLETED`.
- This prevents slow GitHub normalization logic from blocking API responses.

**Async Flow:**
```
POST /api/events/ingest/  →  HTTP 202 Accepted (< 20ms)
          │
          └── process_event_task.delay(event.pk)  →  Redis queue
                        │
                        ▼
              Celery worker picks task up
                        │
                        ▼
              Event normalized → Activity saved → Status: COMPLETED
```

---

### Phase 12: Redis Caching
- **Cache-aside pattern** applied to the two most read-heavy endpoints:
  - `GET /api/activities/` - Activity stream list
  - `GET /api/activities/stats/` - Aggregate statistics
- **Cache key design**: MD5 hash of the query parameters ensures each unique filter combination has its own cache entry.
- **Cache TTL**: 300 seconds (5 minutes).
- **HTTP Headers**: Responses include `X-Cache: HIT` or `X-Cache: MISS` to make caching behavior observable.
- **Automatic invalidation**: Whenever a new Activity is created (via `EventProcessorService`), all related cache keys are purged.

**Cache Performance Benchmark:**

| Endpoint | PostgreSQL (Miss) | Redis (Hit) | Speedup |
|:---|:---|:---|:---|
| `GET /api/activities/` | 93.704 ms | 1.230 ms | **76.2x faster** |
| `GET /api/activities/stats/` | 38.113 ms | 0.617 ms | **61.8x faster** |

---

### Phase 13: API Rate Limiting
- **`RedisRateThrottle`** (`core/throttling.py`) - A custom rate limiter built on `SimpleRateThrottle`, storing counters in Redis.
- **Limit**: 100 requests per minute per client.
- **Client identification**:
  1. If `X-API-Key` header is present → rate limit by API key.
  2. Otherwise → rate limit by client IP address.
- **Response when throttled**: `HTTP 429 Too Many Requests`.

---

### Phase 14: GitHub OAuth Authentication
- Users can **log in with their GitHub account** - no separate username/password needed.
- Full **OAuth 2.0 Authorization Code flow** implementation:
  1. User visits `GET /api/auth/github/login/` → redirected to GitHub consent screen.
  2. User approves → GitHub redirects back to `GET /api/auth/github/callback/`.
  3. Server exchanges the `code` for an `access_token`.
  4. Fetches GitHub profile → upserts `User` record in the database.
  5. Establishes a **Django session cookie** (stateful, server-side).
- **CSRF protection** via a `state` token stored in the server session.
- **Private email fallback** - if a user's email is private on GitHub, fetches it from `GET /user/emails`.
- **Username conflict handling** - if a username already exists, appends `_1`, `_2`, etc.
- **Logout**: `POST /api/auth/logout/` invalidates the session.

---

### Phase 15: Personal Activity Dashboard (Tracked Repositories)
- Authenticated users can **track specific repositories** they care about.
- A `TrackedRepository` model links a `User` to a `Repository`.
- **Personal API endpoints** under `/api/me/`:
  - `POST /api/me/repositories/` - Add a repo to your tracking list (validates it exists on GitHub live).
  - `GET /api/me/repositories/` - See all your tracked repos.
  - `DELETE /api/me/repositories/{id}/` - Stop tracking a repo.
  - `GET /api/me/activities/` - Paginated activity feed scoped to your tracked repos only.
  - `GET /api/me/activities/stats/` - Personalized statistics across your tracked repos.
- **User-scoped Redis caching** - each user's activity cache is isolated (`my_activities_list:{user_id}:{hash}`).

---

## 8. Complete API Reference

### Authentication Endpoints

| Method | Endpoint | Auth Required | Description |
|:---|:---|:---|:---|
| `GET` | `/api/auth/github/login/` | No | Redirects browser to GitHub OAuth consent page |
| `GET` | `/api/auth/github/callback/` | No | Handles OAuth callback, creates session |
| `POST` | `/api/auth/logout/` | ✅ Yes | Destroys current user session |

---

### Activity Endpoints (Public)

| Method | Endpoint | Auth Required | Description |
|:---|:---|:---|:---|
| `GET` | `/api/activities/` | No | List all activities (paginated, filterable) |
| `GET` | `/api/activities/stats/` | No | Aggregate statistics (total, by type, by repo) |

**Available Query Filters for `GET /api/activities/`:**
- `?repository=owner/name` - Filter by full repository name
- `?repository=name` - Filter by short repository name
- `?activity_type=PR_OPENED` - Filter by normalized activity type
- `?start_date=2026-01-01` - Filter activities after this date
- `?end_date=2026-12-31` - Filter activities before this date

---

### Event Endpoints

| Method | Endpoint | Auth Required | Description |
|:---|:---|:---|:---|
| `POST` | `/api/events/ingest/` | No | Ingest a raw event → queues Celery task (returns HTTP 202) |
| `POST` | `/api/events/{id}/process/` | No | Manually trigger processing of an event |
| `GET` | `/api/events/{id}/` | No | Get an event's current status and attempts |
| `GET` | `/api/events/{id}/attempts/` | No | Get the full processing attempt history |
| `POST` | `/api/events/test_idempotency/` | No | Fires 5 concurrent requests to prove uniqueness constraints work |

---

### GitHub Sync Endpoints

| Method | Endpoint | Auth Required | Description |
|:---|:---|:---|:---|
| `POST` | `/api/github/repositories/{id}/sync/` | No | Sync a single repository from GitHub |
| `POST` | `/api/github/repositories/sync-all/` | No | Sync all registered GitHub repositories |

---

### Personal Dashboard Endpoints (Requires Login)

| Method | Endpoint | Auth Required | Description |
|:---|:---|:---|:---|
| `GET` | `/api/me/repositories/` | ✅ Yes | List your tracked repositories |
| `POST` | `/api/me/repositories/` | ✅ Yes | Add a repository to your tracking list |
| `DELETE` | `/api/me/repositories/{id}/` | ✅ Yes | Remove a tracked repository |
| `GET` | `/api/me/activities/` | ✅ Yes | Paginated activity feed for your tracked repos |
| `GET` | `/api/me/activities/stats/` | ✅ Yes | Activity statistics for your tracked repos |

---

## 9. How GitHub Data Flows Through the System

### Path A: Repository Sync (Pull Model)

```
User calls: POST /api/github/repositories/{id}/sync/
                    │
                    ▼
        github/views.py  (repository_sync / sync_all_repositories)
                    │
                    ▼
        github/services.py  (GitHubRepositorySyncService.sync_repository)
         │
         ├── github/client.py  (GitHubClient.get_repository_events)
         │       └── GET https://api.github.com/repos/{owner}/{repo}/events
         │               ↑ Automatic retries (3x) + Rate-limit detection + 15s timeout
         │
         ├── github/normalizers.py  (GitHubEventNormalizer.normalize)
         │       └── Converts each raw event → Activity dict
         │
         └── core/models.py  (Activity.objects.get_or_create)
                 └── Idempotent write - skips if already in DB
                         │
                         ▼
                 Repository.last_sync_status = SUCCESS
```

### Path B: Async Ingestion (Push Model)

```
External system calls: POST /api/events/ingest/
                    │
                    ▼
        core/views/events.py  (EventViewSet.ingest)
         │
         ├── Event.objects.get_or_create  → saves to PostgreSQL (status: PENDING)
         │
         └── process_event_task.delay(event.pk)  → queued in Redis
                    │
                    ▼  [Redis message broker]
                    │
            celery-eventflow worker receives task
                    │
                    ▼
        core/services.py  (EventProcessorService.process_event)
         │
         ├── Normalize payload → github/normalizers.py
         ├── Activity.objects.get_or_create
         ├── Create EventProcessingAttempt record
         └── Event.status = COMPLETED
                    │
                    ▼
         Redis activity caches invalidated
```

---

## 10. Performance & Scalability

### Database Performance

EventFlow was benchmarked on a dataset of **100,000+ Activity records** using PostgreSQL's `EXPLAIN ANALYZE`. The addition of **composite B-Tree indexes** yielded dramatic improvements:

| Query | Before | After | Improvement |
|:---|:---|:---|:---|
| Filter by repository, sort by date | 13.089 ms | 0.100 ms | 130.8× |
| Filter by actor, sort by date | 12.373 ms | 0.068 ms | 181.9× |
| Filter by activity type, sort by date | 11.400 ms | 0.074 ms | 154.0× |

The key insight: a composite index `(repository_id, created_at DESC)` lets PostgreSQL satisfy both the `WHERE` filter and the `ORDER BY` clause using a single index scan, completely eliminating the in-memory sort step.

### API Response Caching

Redis caching of frequently-read endpoints reduces response time by over 60×:

| Endpoint | Cold (DB) | Warm (Cache) | Improvement |
|:---|:---|:---|:---|
| `GET /api/activities/` | 93.704 ms | 1.230 ms | 76.2× |
| `GET /api/activities/stats/` | 38.113 ms | 0.617 ms | 61.8× |

### Async Processing

The Celery + Redis architecture decouples ingestion latency from processing latency:
- **Ingestion response time**: < 20ms (HTTP 202 Accepted)
- **Processing time** (background): ~28ms (verified in Celery logs)

---

## 11. Security Mechanisms

| Mechanism | Implementation | Details |
|:---|:---|:---|
| **OAuth 2.0 CSRF Protection** | CSRF `state` token | `secrets.token_hex(16)` stored in session; verified on callback |
| **Session Security** | Django sessions | Server-side session cookies via `django.contrib.sessions` |
| **Rate Limiting** | `RedisRateThrottle` | 100 req/min per API key or IP; HTTP 429 on excess |
| **Database Idempotency** | `UniqueConstraint` | DB-level uniqueness prevents duplicate Events and Activities |
| **GitHub API Fail-Fast** | `GitHubRateLimitError` | Immediately aborts on 429/rate-limit to prevent API hammering |
| **Request Timeout** | 15-second hard timeout | Every GitHub outbound call is bounded |
| **Private Email Fallback** | `/user/emails` API | Handles GitHub users with private email settings |
| **Username Collision** | Numeric suffix | `_1`, `_2` appended if GitHub username already exists in DB |
| **Environment Secrets** | `.env` file | All credentials loaded from environment; never hardcoded |

---

## 12. How to Run the Project Locally

### Prerequisites

- **Docker** and **Docker Compose** installed on your machine.
- A **GitHub OAuth App** (for login functionality) - create at: `GitHub → Settings → Developer Settings → OAuth Apps`.
- Optionally: a **GitHub Personal Access Token** (increases API rate limit from 60 to 5,000 requests/hour).

---

### Step 1: Clone the Repository

```bash
git clone <repo-url>
cd Event_FLow
```

---

### Step 2: Set Up Environment Variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your configuration (see [Section 13](#13-environment-variables-reference) for details).

---

### Step 3: Start All Services

```bash
make run
```

This command will:
1. Build the Docker image for the Django backend and Celery worker.
2. Pull PostgreSQL 17 and Redis 7 images.
3. Start all 4 containers (backend, celery, redis, db).
4. The backend becomes available at `http://localhost:8000`.

---

### Step 4: Apply Database Migrations

```bash
make migrate
```

This creates all the database tables defined in the models.

---

### Step 5: Create an Admin Superuser (Optional)

```bash
make create-superuser
```

Then visit `http://localhost:8000/admin/` to manage data through the admin panel.

---

### Step 6: Add a Repository and Sync It

**Option A - Via Django Admin:**
1. Open `http://localhost:8000/admin/`
2. Create an `Organization` (e.g., `octocat`)
3. Create a `Repository` (e.g., `Hello-World`, provider: `github`)

**Option B - Via Django Shell:**
```bash
make shell
```
```python
from core.models import Organization, Repository

org, _ = Organization.objects.get_or_create(name="octocat")
repo, _ = Repository.objects.get_or_create(
    organization=org,
    name="Hello-World",
    provider="github",
    external_id="octocat/Hello-World"
)
```

**Trigger Sync:**
```bash
curl -X POST http://localhost:8000/api/github/repositories/1/sync/
```

---

### Step 7: Query Activities

```bash
# All activities
curl http://localhost:8000/api/activities/

# Filter by type
curl "http://localhost:8000/api/activities/?activity_type=PR_OPENED"

# Get statistics
curl http://localhost:8000/api/activities/stats/
```

---

### Useful Make Commands

| Command | What It Does |
|:---|:---|
| `make run` | Start all Docker containers |
| `make down` | Stop and remove all containers |
| `make restart` | Rebuild and restart everything |
| `make logs` | Stream live logs from all containers |
| `make migrate` | Run database migrations |
| `make migrations` | Generate new migration files |
| `make create-superuser` | Create a Django admin user |
| `make shell` | Open interactive Python shell in the backend container |
| `make recreate-schema` | Drop all volumes, rebuild, and migrate from scratch |

---

## 13. Environment Variables Reference

Create a `.env` file in the project root with these variables:

```ini
# ─────────────────────────────────────────
# PostgreSQL Database
# ─────────────────────────────────────────
POSTGRES_DB=eventflow
POSTGRES_USER=eventflow_user
POSTGRES_PASSWORD=eventflow_password
POSTGRES_HOST=db
POSTGRES_PORT=5432

# ─────────────────────────────────────────
# GitHub API (Optional - improves rate limit)
# ─────────────────────────────────────────
# Without this: 60 API requests/hour
# With this:  5,000 API requests/hour
GITHUB_TOKEN=your_personal_access_token_here

# ─────────────────────────────────────────
# GitHub OAuth App (Required for user login)
# ─────────────────────────────────────────
# Create at: GitHub → Settings → Developer Settings → OAuth Apps
GITHUB_CLIENT_ID=your_github_oauth_app_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_app_client_secret
GITHUB_REDIRECT_URI=http://localhost:8000/api/auth/github/callback/

# ─────────────────────────────────────────
# Celery / Redis
# ─────────────────────────────────────────
CELERY_BROKER_URL=redis://redis:6379/0       # Redis database 0 - task queue
CELERY_RESULT_BACKEND=redis://redis:6379/0   # Celery results stored here
REDIS_CACHE_URL=redis://redis:6379/1         # Redis database 1 - API response cache
```

---

## 14. Key Design Decisions Explained

### Why Django + DRF instead of FastAPI?
Django's ORM, built-in admin panel, migrations system, sessions, and `AbstractUser` extension model make it significantly faster to build production-grade features. DRF adds a rich toolkit (ViewSets, Routers, Serializers, Throttling) on top.

### Why PostgreSQL instead of a NoSQL database?
GitHub events have structured, relational data (repos belong to organizations, activities belong to repos and users). PostgreSQL's `UniqueConstraint`, composite indexes, and `EXPLAIN ANALYZE` make it ideal for enforcing idempotency and optimizing complex queries.

### Why Redis for both caching and Celery broker?
Redis is already required for Celery. Using it for caching too (on a different database number - `0` for Celery, `1` for cache) avoids adding another infrastructure dependency while keeping concerns separated.

### Why Celery for async processing instead of Django's database-backed scheduler?
Celery with Redis as the broker gives true out-of-process async execution. The ingestion API responds in < 20ms, and slow normalization work happens in a separate worker process - this prevents one slow operation from blocking other API requests.

### Why database-level uniqueness constraints (not application-level)?
Application-level checks (e.g., `if Event.objects.filter(...).exists(): return`) are vulnerable to race conditions under concurrent requests. Two requests can both pass the check before either has written to the database. A `UniqueConstraint` at the database level catches this at the lowest layer, regardless of concurrency.

### Why composite indexes with `created_at DESC`?
Activity stream queries always combine a filter (`WHERE repository_id = X`) with a descending date sort (`ORDER BY created_at DESC LIMIT 50`). A composite index `(repository_id, created_at DESC)` stores entries pre-filtered and pre-sorted, so PostgreSQL can directly scan the first 50 matching entries without loading thousands of rows or performing an in-memory sort.

---

## 15. Glossary of Terms

| Term | Meaning |
|:---|:---|
| **Activity** | A normalized developer action stored in EventFlow's database (e.g., "PR #42 was opened on owasp/nest") |
| **Actor** | The GitHub user who performed an activity |
| **Celery** | A Python distributed task queue system for running code asynchronously in background worker processes |
| **Dead-Letter** | An event that has exhausted all retry attempts and is permanently marked as `FAILED` |
| **DRF** | Django REST Framework - a toolkit for building REST APIs with Django |
| **Event** | A raw, unprocessed payload received from GitHub, stored before normalization |
| **Exponential Backoff** | A retry strategy where wait time doubles with each failure (30s, 60s, 120s, ...) |
| **Idempotency** | The property that sending the same request multiple times produces the same result as sending it once |
| **Normalization** | The process of converting GitHub's many different raw event formats into a single consistent `Activity` schema |
| **OAuth 2.0** | An authorization protocol that lets users grant third-party apps access to their GitHub account without sharing a password |
| **Rate Limiting** | Restricting how many API requests a client can make in a time window to prevent abuse |
| **Redis** | An in-memory data store used here for both task queuing (Celery broker) and response caching |
| **Sync** | The process of fetching the latest events from GitHub and saving them to the local database |
| **TrackedRepository** | A user's subscription to a specific repository - they only see activities from their tracked repos |
| **UniqueConstraint** | A database rule that prevents two rows from having the same values in specified columns |
| **ViewSet** | A DRF class that groups multiple related API endpoint handlers (list, create, retrieve, etc.) under one URL pattern |
| **Webhook** | A GitHub push notification - GitHub sends an HTTP request to your server whenever an event occurs (as opposed to polling) |
| **X-Cache** | An HTTP response header added by EventFlow to indicate whether the response came from Redis cache (`HIT`) or the database (`MISS`) |

---

*Last updated: August 2026 - EventFlow v1.0 (Phase 15 complete)*
