from models import db, Exercise
from .serializers import exercise_to_dict


def list_exercises():
    return Exercise.query.order_by(Exercise.order.asc(), Exercise.name.asc()).all()


def get_exercise(exercise_id):
    return db.session.get(Exercise, exercise_id)


def create_exercise(data):
    ex = Exercise(
        name=(data.get('name') or '').strip(),
        order=data.get('order', 0), muscles=data.get('muscles'),
        sets=data.get('sets', 3), reps=data.get('reps', 10), duration=data.get('duration'),
        rest=data.get('rest', 60), image=data.get('image'), image_urls=data.get('image_urls'),
        link=data.get('link'), instructions=data.get('instructions'),
        exercise_type=data.get('exercise_type', 'Strength'), categories=data.get('categories'),
        category_targets=data.get('category_targets'),
    )
    if not ex.name:
        raise ValueError('Exercise name is required.')
    db.session.add(ex)
    db.session.commit()
    return ex


def update_exercise(exercise_id, data):
    ex = get_exercise(exercise_id)
    if not ex:
        return None
    allowed = {'name','order','muscles','sets','reps','duration','rest','image','image_urls','link','instructions','exercise_type','categories','category_targets'}
    for key in allowed:
        if key in data:
            setattr(ex, key, data[key])
    if not (ex.name or '').strip():
        raise ValueError('Exercise name is required.')
    db.session.commit()
    return ex


def delete_exercise(exercise_id):
    ex = get_exercise(exercise_id)
    if not ex:
        return False
    db.session.delete(ex)
    db.session.commit()
    return True


def as_dict(ex):
    return exercise_to_dict(ex)
