"""CMFit MCP server.

Run with: python mcp_server.py
The MCP adapter reuses the same application services as the REST API.
"""
from functools import wraps
from mcp.server.mcpserver import MCPServer

from app import app
from services import exercise_service, workout_service, fitness_service

mcp = MCPServer("CMFit")


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
    item = workout_service.log_set(workout_log_id, {
        'workout_exercise_id': workout_exercise_id, 'reps': reps, 'weight': weight,
        'duration': duration, 'time_seconds': time_seconds, 'distance_meters': distance_meters,
    })
    return workout_service.set_as_dict(item) if item else {'error': 'Workout log not found'}




@mcp.tool()
@in_app_context
def save_rest(workout_log_id: int, set_id: int, rest_seconds: int,
              starting_heart_rate: int | None = None, ending_heart_rate: int | None = None) -> dict:
    """Save rest duration and optional starting/ending heart rate for a logged set."""
    item = workout_service.save_rest(workout_log_id, set_id, {
        'rest_seconds': rest_seconds,
        'rest_start_heart_rate': starting_heart_rate,
        'rest_end_heart_rate': ending_heart_rate,
    })
    return workout_service.set_as_dict(item) if item else {'error': 'Workout log/set not found'}


@mcp.tool()
@in_app_context
def finish_workout(workout_log_id: int, notes: str = '') -> dict:
    """Finish a workout session and snapshot completed sets into history."""
    log = workout_service.finish_workout(workout_log_id, notes)
    return workout_service.log_as_dict(log) if log else {'error': 'Workout log not found'}


@mcp.tool()
@in_app_context
def get_fitness_test_history(test_key: str = '', limit: int = 50) -> list[dict]:
    """Return fitness-test history, optionally filtered by test key."""
    return [fitness_service.as_dict(x) for x in fitness_service.list_results(test_key or None, min(limit, 500))]


if __name__ == '__main__':
    mcp.run()
