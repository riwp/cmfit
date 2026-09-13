from datetime import datetime
from models import db, Workout, WorkoutExercise, WorkoutLog, SetLog, ExerciseHistory, Exercise
from .serializers import workout_to_dict, workout_log_to_dict, set_log_to_dict


def list_workouts():
    return Workout.query.order_by(Workout.id.desc()).all()


def get_workout(workout_id):
    return db.session.get(Workout, workout_id)


def create_workout(data):
    title = (data.get('title') or '').strip()
    if not title:
        raise ValueError('Workout title is required.')
    workout = Workout(title=title, description=data.get('description'))
    db.session.add(workout)
    db.session.commit()
    return workout


def update_workout(workout_id, data):
    workout = get_workout(workout_id)
    if not workout:
        return None
    if 'title' in data:
        workout.title = (data.get('title') or '').strip()
    if 'description' in data:
        workout.description = data.get('description')
    if not workout.title:
        raise ValueError('Workout title is required.')
    db.session.commit()
    return workout


def delete_workout(workout_id):
    workout = get_workout(workout_id)
    if not workout:
        return False
    db.session.delete(workout)
    db.session.commit()
    return True


def add_exercise(workout_id, data):
    workout = get_workout(workout_id)
    exercise = db.session.get(Exercise, data.get('exercise_id'))
    if not workout or not exercise:
        return None
    next_order = max([we.order or 0 for we in workout.exercises], default=-1) + 1
    item = WorkoutExercise(
        workout_id=workout.id, exercise_id=exercise.id,
        custom_sets=data.get('custom_sets'), custom_reps=data.get('custom_reps'),
        custom_duration=data.get('custom_duration'), custom_rest=data.get('custom_rest'),
        categories=data.get('categories'), category_targets=data.get('category_targets'),
        category=data.get('category'), order=data.get('order', next_order),
    )
    db.session.add(item)
    db.session.commit()
    return item


def start_workout(workout_id):
    if not get_workout(workout_id):
        return None
    log = WorkoutLog(workout_id=workout_id, start_time=datetime.utcnow())
    db.session.add(log)
    db.session.commit()
    return log


def get_workout_log(log_id):
    return db.session.get(WorkoutLog, log_id)


def log_set(log_id, data):
    log = get_workout_log(log_id)
    if not log:
        return None
    exercise_id = data.get('exercise_id')
    we_id = data.get('workout_exercise_id')
    we = db.session.get(WorkoutExercise, we_id) if we_id else None
    if not exercise_id and we:
        exercise_id = we.exercise_id
    if not exercise_id:
        raise ValueError('exercise_id or workout_exercise_id is required.')
    if db.session.get(Exercise, exercise_id) is None:
        raise ValueError('Exercise not found.')
    set_number = data.get('set_number')
    if set_number is None:
        set_number = (SetLog.query.filter_by(workout_log_id=log.id, exercise_id=exercise_id).count() + 1)
    item = SetLog(
        workout_log_id=log.id, exercise_id=exercise_id, workout_exercise_id=we_id,
        category=data.get('category') or (we.category if we else None), set_number=set_number,
        reps=data.get('reps'), weight=data.get('weight'), duration=data.get('duration'),
        time_seconds=data.get('time_seconds'), distance_meters=data.get('distance_meters'),
        rest=data.get('rest'), rest_start_heart_rate=data.get('rest_start_heart_rate'),
        rest_end_heart_rate=data.get('rest_end_heart_rate'), rest_seconds=data.get('rest_seconds'),
    )
    db.session.add(item)
    db.session.commit()
    return item


def save_rest(log_id, set_id, data):
    log = get_workout_log(log_id)
    item = db.session.get(SetLog, set_id)
    if not log or not item or item.workout_log_id != log.id:
        return None
    item.rest_start_heart_rate = data.get('rest_start_heart_rate')
    item.rest_end_heart_rate = data.get('rest_end_heart_rate')
    item.rest_seconds = data.get('rest_seconds')
    db.session.commit()
    return item


def finish_workout(log_id, notes=None):
    log = get_workout_log(log_id)
    if not log:
        return None
    log.end_time = datetime.utcnow()
    if notes is not None:
        log.notes = notes
    ExerciseHistory.query.filter_by(workout_log_id=log.id).delete(synchronize_session=False)
    for sl in log.sets:
        we = db.session.get(WorkoutExercise, sl.workout_exercise_id) if sl.workout_exercise_id else None
        db.session.add(ExerciseHistory(
            workout_log_id=log.id, workout_exercise_id=sl.workout_exercise_id,
            exercise_id=sl.exercise_id, category=sl.category or (we.category if we else None),
            set_number=sl.set_number, reps=sl.reps, weight=sl.weight, duration=sl.duration,
            time_seconds=sl.time_seconds, distance_meters=sl.distance_meters, rest=sl.rest,
            rest_start_heart_rate=sl.rest_start_heart_rate, rest_end_heart_rate=sl.rest_end_heart_rate,
            rest_seconds=sl.rest_seconds, logged_at=datetime.utcnow(),
        ))
    db.session.commit()
    return log


def as_dict(workout): return workout_to_dict(workout)
def log_as_dict(log): return workout_log_to_dict(log)
def set_as_dict(item): return set_log_to_dict(item)
