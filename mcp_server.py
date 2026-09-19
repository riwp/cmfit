"""CMFit MCP server.

Run with: python mcp_server.py
The MCP adapter reuses the same application services as the REST API.
"""
from functools import wraps
from mcp.server.mcpserver import MCPServer
from app import app
from services import exercise_service, workout_service, fitness_service

mcp = MCPServer('cmfit')


def in_app_context(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        with app.app_context():
            return fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


@mcp.tool()
@in_app_context
def list_exercises() -> list[dict]:
    """List all exercises and their configured targets."""
    return [exercise_service.as_dict(x) for x in exercise_service.list_exercises()]


@mcp.tool()
@in_app_context
def get_exercise(exercise_id: int) -> dict:
    """Get one exercise by ID."""
    item = exercise_service.get_exercise(exercise_id)
    return exercise_service.as_dict(item) if item else {'error': 'Exercise not found'}


@mcp.tool()
@in_app_context
def create_exercise(name: str, exercise_type: str = 'Strength', instructions: str = '') -> dict:
    """Create a new exercise using the same service layer as the REST API."""
    item = exercise_service.create_exercise({
        'name': name, 'exercise_type': exercise_type, 'instructions': instructions
    })
    return exercise_service.as_dict(item)


@mcp.tool()
@in_app_context
def create_workout(title: str, description: str = '') -> dict:
    """Create a new workout definition."""
    item = workout_service.create_workout({'title': title, 'description': description})
    return workout_service.as_dict(item)


@mcp.tool()
@in_app_context
def list_workouts() -> list[dict]:
    """List workout definitions and their exercises."""
    return [workout_service.as_dict(x) for x in workout_service.list_workouts()]


@mcp.tool()
@in_app_context
def get_workout(workout_id: int) -> dict:
    """Get a workout definition by ID."""
    item = workout_service.get_workout(workout_id)
    return workout_service.as_dict(item) if item else {'error': 'Workout not found'}


@mcp.tool()
@in_app_context
def add_workout_exercise(workout_id: int, exercise_id: int, category: str,
                         sets: int | None = None, reps: int | None = None,
                         duration: float | None = None, rest: int | None = None,
                         weight: float | None = None) -> dict:
    """Add an exercise/category row to a workout definition."""
    target = {
        'sets': sets, 'reps': reps, 'duration': duration,
        'rest': rest, 'weight': weight,
    }
    item = workout_service.add_exercise(workout_id, {
        'exercise_id': exercise_id,
        'category': category,
        'categories': [category],
        'custom_sets': sets,
        'custom_reps': reps,
        'custom_duration': duration,
        'custom_rest': rest,
        'category_targets': {category: target},
    })
    if not item:
        return {'error': 'Workout or exercise not found'}
    return workout_service.as_dict(workout_service.get_workout(workout_id))


@mcp.tool()
@in_app_context
def remove_workout_exercise(workout_id: int, workout_exercise_id: int) -> dict:
    """Remove one exercise/category row from a workout definition."""
    if not workout_service.get_workout(workout_id):
        return {'error': 'Workout not found'}
    if not workout_service.remove_workout_exercise(workout_id, workout_exercise_id):
        return {'error': 'Workout exercise not found'}
    return workout_service.as_dict(workout_service.get_workout(workout_id))


@mcp.tool()
@in_app_context
def reorder_workout_exercises(workout_id: int, workout_exercise_ids: list[int]) -> dict:
    """Set the complete order of exercise/category rows in a workout."""
    try:
        workout = workout_service.reorder_workout_exercises(
            workout_id, [{'id': item_id} for item_id in workout_exercise_ids]
        )
    except ValueError as exc:
        return {'error': str(exc)}
    return workout_service.as_dict(workout) if workout else {'error': 'Workout not found'}


@mcp.tool()
@in_app_context
def start_workout(workout_id: int) -> dict:
    """Start a workout and return its workout-log session."""
    log = workout_service.start_workout(workout_id)
    return workout_service.log_as_dict(log) if log else {'error': 'Workout not found'}


@mcp.tool()
@in_app_context
def log_set(workout_log_id: int, workout_exercise_id: int, reps: int | None = None,
            weight: float | None = None, duration: float | None = None,
            time_seconds: int | None = None, distance_meters: float | None = None) -> dict:
    """Log a completed set in an active workout session."""
    try:
        item = workout_service.log_set(workout_log_id, {
            'workout_exercise_id': workout_exercise_id, 'reps': reps, 'weight': weight,
            'duration': duration, 'time_seconds': time_seconds, 'distance_meters': distance_meters,
        })
    except (ValueError, LookupError) as exc:
        return {'error': str(exc)}
    return workout_service.set_as_dict(item) if item else {'error': 'Workout log not found'}


@mcp.tool()
@in_app_context
def save_rest(workout_log_id: int, set_id: int, rest_seconds: int,
              starting_heart_rate: int | None = None, ending_heart_rate: int | None = None) -> dict:
    """Save rest duration and optional starting/ending heart rate for a logged set."""
    try:
        item = workout_service.save_rest(workout_log_id, set_id, {
            'rest_seconds': rest_seconds,
            'rest_start_heart_rate': starting_heart_rate,
            'rest_end_heart_rate': ending_heart_rate,
        })
    except ValueError as exc:
        return {'error': str(exc)}
    return workout_service.set_as_dict(item) if item else {'error': 'Workout log/set not found'}


@mcp.tool()
@in_app_context
def finish_workout(workout_log_id: int, notes: str = '') -> dict:
    """Finish a workout session and snapshot completed sets into history."""
    log = workout_service.finish_workout(workout_log_id, notes)
    return workout_service.log_as_dict(log) if log else {'error': 'Workout log not found'}


@mcp.tool()
@in_app_context
def get_progress_summary(year: int = 0, month: int = 0) -> dict:
    """Return workout progress, training-category trends, and fitness-test statistics."""
    return fitness_service.progress_snapshot(year or None, month or None)


@mcp.tool()
@in_app_context
def get_fitness_test_history(test_key: str = '', limit: int = 50) -> list[dict]:
    """Return fitness-test history, optionally filtered by test key."""
    return [fitness_service.as_dict(x) for x in fitness_service.list_results(test_key or None, min(limit, 500))]


# ------------------------- Read/query tools -------------------------

@mcp.tool()
@in_app_context
def get_recent_workouts(limit: int = 10) -> list[dict]:
    """Return recently completed workout sessions, newest first."""
    return [workout_service.log_as_dict(x) for x in workout_service.get_recent_workout_logs(limit)]


@mcp.tool()
@in_app_context
def get_workout_history(workout_id: int = 0, limit: int = 20) -> list[dict] | dict:
    """Return completed workout sessions, optionally filtered by workout definition."""
    rows = workout_service.get_workout_history(workout_id or None, limit)
    if rows is None:
        return {'error': 'Workout not found'}
    return [workout_service.log_as_dict(x) for x in rows]


@mcp.tool()
@in_app_context
def get_exercise_history(exercise_id: int, limit: int = 50) -> dict:
    """Return completed historical sets and performance for one exercise."""
    result = workout_service.get_exercise_history(exercise_id, limit)
    return result if result is not None else {'error': 'Exercise not found'}


@mcp.tool()
@in_app_context
def get_fitness_tests() -> list[dict]:
    """Return available fitness-test definitions, keys, units, and test instructions."""
    return fitness_service.get_fitness_test_definitions()


@mcp.tool()
@in_app_context
def get_latest_fitness_test_session() -> dict:
    """Return all results from the most recent fitness-test date."""
    result = fitness_service.get_latest_fitness_test_session()
    return result if result is not None else {'date': None, 'results': []}


@mcp.tool()
@in_app_context
def get_training_history(start_date: str, end_date: str) -> list[dict] | dict:
    """Return completed workout sessions in an inclusive YYYY-MM-DD date range."""
    try:
        rows = workout_service.get_training_history(start_date, end_date)
    except ValueError as exc:
        return {'error': str(exc)}
    return [workout_service.log_as_dict(x) for x in rows]


if __name__ == '__main__':
    mcp.run()
