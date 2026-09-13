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

### Exercises — migrated to shared service

The existing exercise UI routes now use `services/exercise_service.py` for list, get, create, update, reorder, and delete operations. The UI adapter still owns HTTP-specific concerns such as multipart image uploads, filesystem image cleanup, redirects, flash messages, and template rendering. The REST API and MCP exercise tools reuse the same service layer.

The exercise UI route names, URLs, templates, CSS, JavaScript contracts, database schema, and redirect behavior remain unchanged.

## Next safe refactor

Refactor **Workout definitions/composition** next: workout list/create/edit/delete, adding/removing exercises, ordering, and category-specific targets. Keep the existing UI routes and templates unchanged while moving database/business operations into `workout_service`. Continue one capability at a time with route-contract checks after each move.
