# 📡 EventFlow - Developer Activity Aggregator (Backend Service)

EventFlow is a Django REST Framework backend service designed to connect to GitHub repositories, ingest raw event streams, normalize developer actions into a consistent format, and expose fast, queryable REST APIs for activity tracking and analytics.

---

## 🌟 Key Backend Capabilities

- **GitHub REST API Integration & Data Normalization**: Fetches repository event streams and normalizes heterogeneous GitHub payloads into standard activity records (`PR_OPENED`, `PR_MERGED`, `COMMIT_PUSHED`, `ISSUE_OPENED`, `RELEASE_PUBLISHED`).
- **Database-Enforced Idempotency**: Guarantees zero duplicate entries by enforcing PostgreSQL `UniqueConstraint` rules across repositories and event identifiers.
- **High-Performance Database Indexing**: Accelerated list and aggregation queries over large datasets using custom B-Tree composite database indexes (`repository + created_at`, `activity_type + created_at`).
- **Redis In-Memory Caching**: Caching layer (Cache-Aside pattern) for read-heavy activity stream and analytics endpoints (`GET /api/activities/`), serving responses under 2ms with automatic cache invalidation on data updates.
- **API Rate Limiting**: Built-in Redis-backed rate throttle (100 requests/minute per client IP or API key) to protect endpoints against abuse.
- **GitHub OAuth 2.0 & User Sessions**: OAuth authentication enabling users to log in with GitHub credentials and maintain personal tracked repository lists.

---

## 🛠️ Technology Stack

### Backend & Database (Primary Focus)
- **Framework**: Python 3.13, Django 5.1, Django REST Framework 3.15
- **Database**: PostgreSQL 17
- **Caching & Throttling**: Redis 7
- **Authentication**: GitHub OAuth 2.0 & Django Server-Side Sessions
- **Infrastructure**: Docker, Docker Compose, Makefile

### Frontend (User Interface)
- **Framework**: Next.js 15 (TypeScript, React, Tailwind CSS)
- **Purpose**: Lightweight UI dashboard consuming backend REST APIs.

---

## 📂 Project Architecture

```text
Event_FLow/
├── compose.yml             # Orchestrates Django backend, PostgreSQL, and Redis containers
├── Makefile                # Management shortcuts (make run, make migrate, make seed, etc.)
├── frontend/               # Next.js UI dashboard (consumes backend REST APIs)
└── backend/
    ├── config/             # Root settings, URLs, WSGI, and ASGI setup
    ├── core/               # Main domain application
    │   ├── models.py       # Data models (User, Repository, Activity, TrackedRepository)
    │   ├── views/          # REST API viewsets (activities, events, auth)
    │   ├── throttling.py   # Redis-backed rate limiter
    │   ├── serializers.py  # DRF serializers for API validation and JSON parsing
    │   └── admin.py        # Django Admin configurations
    └── github/             # External GitHub API integration
        ├── client.py       # HTTP client with rate-limit handling and timeouts
        ├── normalizers.py  # Mapping raw GitHub event JSON to normalized Activity objects
        └── services.py     # Synchronization logic for GitHub repositories
```

---

## 🖥️ Frontend Overview (User Interface)

EventFlow includes a dark-themed **Next.js** dashboard (`frontend/`) that consumes the backend REST APIs to present developer activity visually:

- **Activity Feed Timeline**: Displays a paginated stream of developer actions (`PR_OPENED`, `PR_MERGED`, `COMMIT_PUSHED`, etc.) with direct links to GitHub.
- **Metric Cards**: Shows real-time aggregate statistics (total activities, breakdown by activity type, top repositories).
- **Interactive Filtering**: Filter feed by repository, activity type, date range, search query, and bot event toggling.
- **User Dashboard & Track Repo Modal**: Allows users to log in via GitHub OAuth and manage their personally tracked repository subscriptions.

---

## 🗄️ Database Schema Summary

1. **User**: Extends Django's `AbstractUser` with GitHub OAuth attributes (`github_id`).
2. **Organization**: Represents a GitHub organization or user handle (e.g. `octocat`).
3. **Repository**: Tracks monitored repositories (`name`, `external_id`, `last_synced_at`, `last_sync_status`).
4. **Activity**: Central normalized event record (`activity_type`, `actor`, `repository`, `target_id`, `source_url`, `metadata`). Indexed for fast time-series filtering.
5. **TrackedRepository**: Maps an authenticated user to their personally monitored repositories.

---

## 🚀 API Endpoint Overview

### 🔑 Authentication
| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/auth/github/login/` | No | Initiates GitHub OAuth login flow |
| `GET` | `/api/auth/github/callback/` | No | Handles OAuth code exchange and establishes user session |
| `POST` | `/api/auth/logout/` | ✅ Yes | Logs out user and destroys active session |

### 📊 Activity Feed & Analytics
| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/activities/` | No | List activity stream with filters (`repository`, `activity_type`, `start_date`, `end_date`) |
| `GET` | `/api/activities/stats/` | No | Retrieve aggregate metrics (total activities, breakdown by type, breakdown by repo) |

### 🔄 Repository Sync
| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/github/repositories/{id}/sync/` | No | Syncs latest events from GitHub for a specific repository |
| `POST` | `/api/github/repositories/sync-all/` | No | Triggers bulk sync for all registered repositories |

### 👤 Personal Dashboard (User-Scoped)
| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/me/repositories/` | ✅ Yes | List user's tracked repositories |
| `POST` | `/api/me/repositories/` | ✅ Yes | Add a repository to user's tracking list |
| `DELETE` | `/api/me/repositories/{id}/` | ✅ Yes | Remove a repository from tracking list |
| `GET` | `/api/me/activities/` | ✅ Yes | View activity feed restricted to user's tracked repositories |

---

## ⚡ Performance Optimizations & Benchmarks

EventFlow was benchmarked on a seeded dataset of **100,000+ Activity records** using PostgreSQL `EXPLAIN ANALYZE` and direct API response timing tests.

### 1. PostgreSQL Database Composite Indexing
By adding composite B-Tree indexes on `(repository_id, created_at DESC)`, `(actor_id, created_at DESC)`, and `(activity_type, created_at DESC)`, PostgreSQL satisfies both filtering and sorting via a single index scan, completely eliminating in-memory CPU sorting:

| Query Pattern | Before Index | After Index | Speedup |
| :--- | :--- | :--- | :--- |
| **Filter by repository + sort by date** | 13.089 ms | 0.100 ms | **130.8x faster** |
| **Filter by actor + sort by date** | 12.373 ms | 0.068 ms | **181.9x faster** |
| **Filter by activity type + sort by date** | 11.400 ms | 0.074 ms | **154.0x faster** |

#### 🔍 Testing Process:
1. **Data Seeding**: Executed shortcut command `make seed` (or `docker compose exec backend python manage.py seed_performance_data --count 100000`) to generate 100,000 realistic activity records in bulk transactions.
2. **Query Profiling**: Connected to PostgreSQL CLI (`docker compose exec db psql -U postgres -d mybackend`) and ran `EXPLAIN ANALYZE` on common filtering & sorting query patterns.
3. **Plan Inspection**: Verified PostgreSQL transitioned from CPU-intensive `Top-N Heap Sort` and `Seq Scan` to sub-millisecond `Index Scan` queries.

---

### 2. Redis API Response Caching
Applying a Cache-Aside strategy for read-heavy query endpoints reduces response latency by over 60× (cached responses return `X-Cache: HIT` and automatically purge on data updates):

| Endpoint | Cold (DB Miss) | Warm (Cache Hit) | Speedup |
| :--- | :--- | :--- | :--- |
| `GET /api/activities/` | 93.704 ms | 1.230 ms | **76.2x faster** |
| `GET /api/activities/stats/` | 38.113 ms | 0.617 ms | **61.8x faster** |

#### 🔍 Testing Process:
1. **Cold Cache Request (DB Miss)**: Flushed Redis cache (`cache.clear()`) and issued GET requests to `/api/activities/`, measuring database response latency (returns HTTP header `X-Cache: MISS`).
2. **Warm Cache Request (Cache Hit)**: Re-issued identical GET request immediately; fetched JSON directly from Redis memory in under ~1.2ms (returns HTTP header `X-Cache: HIT`).
3. **Cache Invalidation**: Ingested a new activity record to confirm automatic purging of related Redis cache keys.

---

## 💻 How to Run Locally

### Prerequisites
- Docker & Docker Compose installed
- GitHub Personal Access Token or GitHub OAuth App Credentials (optional for local testing)

### Steps

1. **Clone the repository and set up environment variables**:
   ```bash
   cp .env.example .env
   ```

2. **Start Docker services**:
   ```bash
   make run
   ```

3. **Apply database migrations**:
   ```bash
   make migrate
   ```

4. **Seed 100,000 performance benchmark records (Optional)**:
   ```bash
   make seed
   ```

5. **Create a superuser for Django Admin (Optional)**:
   ```bash
   make create-superuser
   ```

6. **Access the Application**:
   - **Backend REST API**: `http://localhost:8000/api/`
   - **Django Admin Panel**: `http://localhost:8000/admin/`
   - **Frontend UI Dashboard**: `http://localhost:3000` (Next.js app consuming backend APIs)

---

## 🛠️ Handy Management Commands

| Command | Action |
| :--- | :--- |
| `make run` | Starts all Docker containers |
| `make down` | Stops and removes container instances |
| `make migrate` | Applies database migrations |
| `make seed` | Seeds 100,000 performance benchmark records into database |
| `make shell` | Opens interactive Python shell in backend container |
| `make logs` | Tails live container logs |
