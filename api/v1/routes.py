from flask import Blueprint, jsonify, request
from services import exercise_service, workout_service, fitness_service

api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')


def body():
    return request.get_json(silent=True) or {}


def bad_request(exc):
    return jsonify({'error': str(exc)}), 400


@api_v1.get('/health')
def health():
    return jsonify({'status': 'ok', 'api_version': 'v1'})


@api_v1.get('/exercises')
def exercises_list():
    return jsonify([exercise_service.as_dict(x) for x in exercise_service.list_exercises()])


@api_v1.post('/exercises')
def exercises_create():
    try:
        ex = exercise_service.create_exercise(body())
        return jsonify(exercise_service.as_dict(ex)), 201
    except ValueError as exc:
        return bad_request(exc)


@api_v1.get('/exercises/<int:exercise_id>')
def exercises_get(exercise_id):
    ex = exercise_service.get_exercise(exercise_id)
    return (jsonify(exercise_service.as_dict(ex)), 200) if ex else (jsonify({'error': 'Exercise not found'}), 404)


@api_v1.patch('/exercises/<int:exercise_id>')
def exercises_update(exercise_id):
    try:
        ex = exercise_service.update_exercise(exercise_id, body())
        return (jsonify(exercise_service.as_dict(ex)), 200) if ex else (jsonify({'error': 'Exercise not found'}), 404)
    except ValueError as exc:
        return bad_request(exc)


@api_v1.delete('/exercises/<int:exercise_id>')
def exercises_delete(exercise_id):
    return ('', 204) if exercise_service.delete_exercise(exercise_id) else (jsonify({'error': 'Exercise not found'}), 404)


@api_v1.get('/workouts')
def workouts_list():
    return jsonify([workout_service.as_dict(x) for x in workout_service.list_workouts()])


@api_v1.post('/workouts')
def workouts_create():
    try:
        workout = workout_service.create_workout(body())
        return jsonify(workout_service.as_dict(workout)), 201
    except ValueError as exc:
        return bad_request(exc)


@api_v1.get('/workouts/<int:workout_id>')
def workouts_get(workout_id):
    workout = workout_service.get_workout(workout_id)
    return (jsonify(workout_service.as_dict(workout)), 200) if workout else (jsonify({'error': 'Workout not found'}), 404)


@api_v1.patch('/workouts/<int:workout_id>')
def workouts_update(workout_id):
    try:
        workout = workout_service.update_workout(workout_id, body())
        return (jsonify(workout_service.as_dict(workout)), 200) if workout else (jsonify({'error': 'Workout not found'}), 404)
    except ValueError as exc:
        return bad_request(exc)


@api_v1.delete('/workouts/<int:workout_id>')
def workouts_delete(workout_id):
    return ('', 204) if workout_service.delete_workout(workout_id) else (jsonify({'error': 'Workout not found'}), 404)


@api_v1.post('/workouts/<int:workout_id>/exercises')
def workouts_add_exercise(workout_id):
    item = workout_service.add_exercise(workout_id, body())
    return (jsonify({'id': item.id, 'workout_id': item.workout_id, 'exercise_id': item.exercise_id}), 201) if item else (jsonify({'error': 'Workout or exercise not found'}), 404)


@api_v1.put('/workouts/<int:workout_id>/composition')
def workouts_replace_composition(workout_id):
    data = body()
    selections = data.get('selections')
    if not isinstance(selections, list):
        return jsonify({'error': 'selections must be a list'}), 400
    workout = workout_service.replace_workout_exercises(workout_id, selections)
    return (jsonify(workout_service.as_dict(workout)), 200) if workout else (jsonify({'error': 'Workout not found'}), 404)


@api_v1.put('/workouts/<int:workout_id>/exercises/order')
def workouts_reorder_exercises(workout_id):
    try:
        workout = workout_service.reorder_workout_exercises(workout_id, body().get('order'))
        return (jsonify(workout_service.as_dict(workout)), 200) if workout else (jsonify({'error': 'Workout not found'}), 404)
    except ValueError as exc:
        return bad_request(exc)


@api_v1.delete('/workouts/<int:workout_id>/exercises/<int:workout_exercise_id>')
def workouts_remove_exercise(workout_id, workout_exercise_id):
    if not workout_service.get_workout(workout_id):
        return jsonify({'error': 'Workout not found'}), 404
    return ('', 204) if workout_service.remove_workout_exercise(workout_id, workout_exercise_id) else (jsonify({'error': 'Workout exercise not found'}), 404)


@api_v1.post('/workouts/<int:workout_id>/start')
def workouts_start(workout_id):
    log = workout_service.start_workout(workout_id)
    return (jsonify(workout_service.log_as_dict(log)), 201) if log else (jsonify({'error': 'Workout not found'}), 404)


@api_v1.get('/workout-logs/<int:log_id>')
def logs_get(log_id):
    log = workout_service.get_workout_log(log_id)
    return (jsonify(workout_service.log_as_dict(log)), 200) if log else (jsonify({'error': 'Workout log not found'}), 404)


@api_v1.post('/workout-logs/<int:log_id>/sets')
def logs_add_set(log_id):
    try:
        item = workout_service.log_set(log_id, body())
        return (jsonify(workout_service.set_as_dict(item)), 201) if item else (jsonify({'error': 'Workout log not found'}), 404)
    except ValueError as exc:
        return bad_request(exc)
    except LookupError as exc:
        return jsonify({'error': str(exc)}), 404


@api_v1.patch('/workout-logs/<int:log_id>/sets/<int:set_id>/rest')
def logs_update_rest(log_id, set_id):
    try:
        item = workout_service.save_rest(log_id, set_id, body())
        return (jsonify(workout_service.set_as_dict(item)), 200) if item else (jsonify({'error': 'Workout log/set not found'}), 404)
    except ValueError as exc:
        return bad_request(exc)


@api_v1.post('/workout-logs/<int:log_id>/finish')
def logs_finish(log_id):
    log = workout_service.finish_workout(log_id, body().get('notes'))
    return (jsonify(workout_service.log_as_dict(log)), 200) if log else (jsonify({'error': 'Workout log not found'}), 404)


@api_v1.get('/fitness-tests')
def fitness_tests_list():
    limit = min(request.args.get('limit', 100, type=int), 500)
    results = fitness_service.list_results(request.args.get('test_key'), limit)
    return jsonify([fitness_service.as_dict(x) for x in results])


@api_v1.post('/fitness-tests')
def fitness_tests_create():
    try:
        result = fitness_service.create_result(body())
        return jsonify(fitness_service.as_dict(result)), 201
    except (ValueError, TypeError) as exc:
        return bad_request(exc)
