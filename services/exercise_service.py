from models import db, Exercise, WorkoutExercise, SetLog, ExerciseHistory
from .serializers import exercise_to_dict


EDITABLE_FIELDS = {
    'name', 'order', 'muscles', 'sets', 'reps', 'duration', 'rest',
    'image', 'image_urls', 'link', 'instructions', 'exercise_type',
    'categories', 'category_targets'
}


def list_exercises():
    """Return exercises in the same order used by the existing UI."""
    return Exercise.query.order_by(Exercise.order.asc()).all()


def get_exercise(exercise_id):
    return db.session.get(Exercise, exercise_id)


def create_exercise(data):
    """Create an exercise from normalized application data."""
    name = (data.get('name') or '').strip()
    if not name:
        raise ValueError('Exercise name is required.')

    ex = Exercise(
        name=name,
        order=data.get('order', 0),
        muscles=data.get('muscles'),
        sets=data.get('sets', 3),
        reps=data.get('reps', 10),
        duration=data.get('duration'),
        rest=data.get('rest', 60),
        image=data.get('image'),
        image_urls=data.get('image_urls'),
        link=data.get('link'),
        instructions=data.get('instructions'),
        exercise_type=data.get('exercise_type', 'Strength'),
        categories=data.get('categories'),
        category_targets=data.get('category_targets'),
    )

    db.session.add(ex)
    db.session.commit()
    return ex


def update_exercise(exercise_id, data):
    """Update only supported exercise fields."""
    ex = get_exercise(exercise_id)
    if not ex:
        return None

    if 'name' in data:
        data = dict(data)
        data['name'] = (data.get('name') or '').strip()
        if not data['name']:
            raise ValueError('Exercise name is required.')

    for key in EDITABLE_FIELDS:
        if key in data:
            setattr(ex, key, data[key])

    db.session.commit()
    return ex


def reorder_exercises(order_data):
    """Persist the user-defined exercise ordering.

    Unknown exercise IDs are ignored to preserve the behavior of the
    original UI route.
    """
    for item in order_data or []:
        exercise_id = item.get('id')
        new_order = item.get('order')
        if exercise_id is None or new_order is None:
            continue

        exercise = get_exercise(exercise_id)
        if exercise:
            exercise.order = new_order

    db.session.commit()


def delete_exercise(exercise_id):
    """Delete an exercise and the same dependent records the legacy UI removed."""
    ex = get_exercise(exercise_id)
    if not ex:
        return False

    # Preserve the original application behavior. These records reference the
    # exercise independently of the Workout relationship and therefore must be
    # removed before deleting the Exercise row.
    WorkoutExercise.query.filter_by(exercise_id=ex.id).delete(synchronize_session=False)
    SetLog.query.filter_by(exercise_id=ex.id).delete(synchronize_session=False)
    ExerciseHistory.query.filter_by(exercise_id=ex.id).delete(synchronize_session=False)

    db.session.delete(ex)
    db.session.commit()
    return True


def as_dict(ex):
    return exercise_to_dict(ex)
