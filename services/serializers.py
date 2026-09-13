def iso(value):
    return value.isoformat() if value else None


def exercise_to_dict(ex):
    return {
        'id': ex.id, 'name': ex.name, 'order': ex.order, 'muscles': ex.muscles,
        'sets': ex.sets, 'reps': ex.reps, 'duration': ex.duration, 'rest': ex.rest,
        'image': ex.image, 'image_urls': ex.image_urls, 'link': ex.link,
        'instructions': ex.instructions, 'exercise_type': ex.exercise_type,
        'categories': ex.categories, 'category_targets': ex.category_targets,
    }


def workout_exercise_to_dict(we, include_logs=False):
    result = {
        'id': we.id, 'workout_id': we.workout_id, 'exercise_id': we.exercise_id,
        'exercise': exercise_to_dict(we.exercise) if we.exercise else None,
        'custom_sets': we.custom_sets, 'custom_reps': we.custom_reps,
        'custom_duration': we.custom_duration, 'custom_rest': we.custom_rest,
        'categories': we.categories, 'category_targets': we.category_targets,
        'category': we.category, 'order': we.order,
    }
    return result


def workout_to_dict(workout):
    return {
        'id': workout.id, 'title': workout.title, 'description': workout.description,
        'exercises': [workout_exercise_to_dict(we) for we in sorted(workout.exercises, key=lambda x: x.order or 0)],
    }


def set_log_to_dict(item):
    return {
        'id': item.id, 'workout_log_id': item.workout_log_id,
        'exercise_id': item.exercise_id, 'workout_exercise_id': item.workout_exercise_id,
        'category': item.category, 'set_number': item.set_number, 'reps': item.reps,
        'weight': item.weight, 'duration': item.duration, 'time_seconds': item.time_seconds,
        'distance_meters': item.distance_meters, 'rest': item.rest,
        'rest_start_heart_rate': item.rest_start_heart_rate,
        'rest_end_heart_rate': item.rest_end_heart_rate, 'rest_seconds': item.rest_seconds,
    }


def workout_log_to_dict(log):
    return {
        'id': log.id, 'workout_id': log.workout_id, 'start_time': iso(log.start_time),
        'end_time': iso(log.end_time), 'notes': log.notes,
        'workout': workout_to_dict(log.workout) if log.workout else None,
        'sets': [set_log_to_dict(s) for s in log.sets],
    }


def fitness_test_to_dict(result):
    return {
        'id': result.id, 'test_key': result.test_key, 'category': result.category,
        'value': result.value, 'unit': result.unit, 'notes': result.notes,
        'tested_at': iso(result.tested_at), 'details': result.details,
    }
