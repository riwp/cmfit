# CMFit architecture

This refactor preserves the existing web UI and database contract while adding supported integration surfaces.

## Layers

- **UI adapter (`app.py`)**: the existing Flask/Jinja routes and behavior. Route names, URLs, templates, JavaScript contracts, and CSS are preserved.
- **Data model (`models.py`)**: the existing SQLAlchemy models and additive SQLite migrations, using the existing `data/cmfit.db` database.
- **Application services (`services/`)**: reusable operations for exercises, workouts/workout logs, and fitness results. New consumers should call this layer rather than directly duplicating database logic.
- **REST API (`api/v1/`)**: versioned `/api/v1` endpoints backed by the application services.
- **MCP adapter (`mcp_server.py`)**: MCP tools backed by the same application services for AI-agent consumers.

## Compatibility rule

The current UI is the compatibility contract. Refactoring should not require template, CSS, JavaScript, route-name, or database-schema changes unless a product change is explicitly intended.

## REST API

Health:
- `GET /api/v1/health`

Exercises:
- `GET /api/v1/exercises`
- `POST /api/v1/exercises`
- `GET /api/v1/exercises/{id}`
- `PATCH /api/v1/exercises/{id}`
- `DELETE /api/v1/exercises/{id}`

Workouts and sessions:
- `GET /api/v1/workouts`
- `POST /api/v1/workouts`
- `GET /api/v1/workouts/{id}`
- `PATCH /api/v1/workouts/{id}`
- `DELETE /api/v1/workouts/{id}`
- `POST /api/v1/workouts/{id}/exercises`
- `POST /api/v1/workouts/{id}/start`
- `GET /api/v1/workout-logs/{id}`
- `POST /api/v1/workout-logs/{id}/sets`
- `PATCH /api/v1/workout-logs/{log_id}/sets/{set_id}/rest`
- `POST /api/v1/workout-logs/{id}/finish`

Fitness tests:
- `GET /api/v1/fitness-tests`
- `POST /api/v1/fitness-tests`

## MCP

Run `python mcp_server.py` after installing requirements. MCP tools currently cover exercise/workout discovery and creation, workout session start/log/rest/finish, and fitness-test history.
## Refactor status

- Exercise UI routes use `exercise_service` for shared CRUD/reordering behavior.
- Workout definition/composition UI routes use `workout_service` for create/list/get/delete, composition replacement, remove, reorder, and start.
- REST API and MCP adapters reuse the same services.
- Existing UI route URLs, templates, CSS, JavaScript, and `data/cmfit.db` remain unchanged.
- Next safe refactor area: active workout logging/rest/finish, followed by progress/fitness tests and admin/settings.

## Active workout logging refactor

The active workout flow now uses `services/workout_service.py` for shared business logic while preserving the existing UI contract:

- start workout session
- build log-screen exercise cards and prior-session defaults
- save completed sets
- save rest duration and heart-rate recovery values
- finish a workout and snapshot completed sets to `ExerciseHistory`

`app.py` remains responsible for Flask request/response behavior, redirects, AJAX status codes, flashes, and template rendering. REST API and MCP consumers call the same service-layer rules. No templates or CSS are changed by this refactor.


## Progress and fitness-test service refactor

The progress dashboard and fitness-test UI now delegate calculations, validation, and persistence to `services/fitness_service.py`.

- Existing UI routes remain `/progress` and `/progress/fitness-test`.
- Existing `progress.html` inputs are unchanged.
- `GET /api/v1/progress` exposes a JSON-safe dashboard snapshot.
- Existing fitness-test API routes continue to use the same shared service.
- MCP exposes `get_progress_summary` and existing fitness-test history through the same service layer.
