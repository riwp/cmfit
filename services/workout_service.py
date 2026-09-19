from datetime import datetime
from models import db, Workout, WorkoutExercise, WorkoutLog, SetLog, ExerciseHistory, Exercise
from .serializers import workout_to_dict, workout_log_to_dict, set_log_to_dict


def _safe_int(value, default=None, minimum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed is None:
        return None
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed


def _safe_float(value, default=None, minimum=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if parsed is None:
        return None
    if minimum is not None:
        parsed = max(minimum, parsed)
    return parsed


def list_workouts():
    """Return workout definitions in the user's saved order."""
    return (
        Workout.query
        .order_by(Workout.order.asc(), Workout.id.asc())
        .all()
    )


def get_workout(workout_id):
    return db.session.get(Workout, workout_id)


def create_workout(data):
    """Create a workout at the top while preserving existing workout order."""
    title = (data.get('title') or '').strip()
    if not title:
        raise ValueError('Workout title is required.')

    existing_workouts = (
        Workout.query
        .order_by(Workout.order.asc(), Workout.id.asc())
        .all()
    )

    for existing in existing_workouts:
        existing.order += 1

    workout = Workout(
        title=title,
        description=(data.get('description') or '').strip() or None,
        order=0,
    )
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
        workout.description = (data.get('description') or '').strip() or None

    if not workout.title:
        raise ValueError('Workout title is required.')

    db.session.commit()
    return workout


def reorder_workouts(order_data):
    """Validate and persist the complete workout ordering."""
    if not isinstance(order_data, list):
        raise ValueError('Invalid payload')

    workouts = Workout.query.all()
    workout_map = {workout.id: workout for workout in workouts}
    submitted_ids = []
    seen_ids = set()

    for item in order_data:
        if not isinstance(item, dict):
            raise ValueError('Invalid order item')

        try:
            workout_id = int(item.get('id'))
        except (TypeError, ValueError):
            raise ValueError('Invalid workout ID')

        if workout_id not in workout_map or workout_id in seen_ids:
            raise ValueError('Invalid or duplicate workout ID')

        seen_ids.add(workout_id)
        submitted_ids.append(workout_id)

    if len(submitted_ids) != len(workouts):
        raise ValueError('Incomplete workout order')

    for position, workout_id in enumerate(submitted_ids):
        workout_map[workout_id].order = position

    db.session.commit()
    return list_workouts()


def delete_workout(workout_id):
    """Delete a workout definition using the same semantics as the legacy UI."""
    workout = get_workout(workout_id)
    if not workout:
        return False

    db.session.delete(workout)
    db.session.flush()

    remaining = (
        Workout.query
        .order_by(Workout.order.asc(), Workout.id.asc())
        .all()
    )
    for position, item in enumerate(remaining):
        item.order = position

    db.session.commit()
    return True


def list_available_exercises():
    """Return exercises in the order used by the workout composition screen."""
    return Exercise.query.order_by(Exercise.name.asc()).all()


def get_composition_state(workout_id, valid_categories):
    """Build the existing workout-composition state expected by the current UI.

    This preserves the existing template contract without putting SQLAlchemy query
    logic back into the route layer.
    """
    workout = get_workout(workout_id)
    if not workout:
        return None

    all_exercises = list_available_exercises()
    existing_we = (
        WorkoutExercise.query
        .filter_by(workout_id=workout.id)
        .order_by(WorkoutExercise.order)
        .all()
    )

    existing_map = {}
    for we in existing_we:
        ex = we.exercise
        if not ex:
            continue

        entry = existing_map.setdefault(ex.id, {'categories': [], 'targets': {}})
        category = we.category
        if not category:
            cats = we.categories if isinstance(we.categories, list) else []
            category = cats[0] if cats else ex.exercise_type

        if category not in entry['categories']:
            entry['categories'].append(category)

        targets = we.category_targets if isinstance(we.category_targets, dict) else {}
        target = targets.get(category, {
            'sets': we.custom_sets if we.custom_sets is not None else (ex.sets or 3),
            'reps': we.custom_reps if we.custom_reps is not None else (ex.reps or 10),
            'duration': we.custom_duration if we.custom_duration is not None else (ex.duration or 30),
            'weight': 0,
            'rest': we.custom_rest if we.custom_rest is not None else (ex.rest or 60),
        })
        entry['targets'][category] = target

    for ex in all_exercises:
        category_defaults = {
            category: {
                'sets': ex.sets or 3,
                'reps': ex.reps or 10,
                'duration': ex.duration or 30,
                'weight': 0,
                'rest': ex.rest or 60,
            }
            for category in valid_categories
        }

        configured = ex.categories if isinstance(ex.categories, list) else []
        if not configured:
            configured = [ex.exercise_type] if ex.exercise_type in valid_categories else ['Strength']

        # These are transient attributes used by the existing Jinja template.
        ex.types_list = configured
        stored_targets = ex.category_targets if isinstance(ex.category_targets, dict) else {}
        ex.category_targets = {
            category: stored_targets.get(
                category,
                category_defaults.get(category, {
                    'sets': ex.sets or 3,
                    'reps': ex.reps or 10,
                    'duration': ex.duration or 30,
                    'weight': 0,
                    'rest': ex.rest or 60,
                }),
            )
            for category in configured
        }

    return {
        'workout': workout,
        'all_exercises': all_exercises,
        'existing_map': existing_map,
    }


def replace_workout_exercises(workout_id, selections):
    """Update a workout's exercise/category composition without losing saved order.

    Existing WorkoutExercise rows retain their relative order and IDs.
    Newly added exercise/category rows are inserted at the top of the workout.
    Rows that are no longer selected are removed.
    """
    workout = get_workout(workout_id)
    if not workout:
        return None

    # ------------------------------------------------------------------
    # Normalize the submitted selections.
    #
    # Each exercise/category combination corresponds to one
    # WorkoutExercise row.
    # ------------------------------------------------------------------
    submitted = {}

    for selection in selections or []:
        exercise_id = _safe_int(selection.get('exercise_id'))
        exercise = (
            db.session.get(Exercise, exercise_id)
            if exercise_id is not None
            else None
        )

        if not exercise:
            continue

        categories = selection.get('categories') or []
        if not isinstance(categories, list):
            continue

        supplied_targets = (
            selection.get('targets')
            if isinstance(selection.get('targets'), dict)
            else {}
        )

        for category in categories:
            raw_target = (
                supplied_targets.get(category, {})
                if isinstance(supplied_targets, dict)
                else {}
            )

            target = {
                'sets': _safe_int(
                    raw_target.get('sets'),
                    exercise.sets or 3,
                    minimum=1,
                ),
                'reps': _safe_int(
                    raw_target.get('reps'),
                    exercise.reps or 10,
                    minimum=1,
                ),
                'duration': _safe_float(
                    raw_target.get('duration'),
                    exercise.duration or 30,
                    minimum=0.0,
                ),
                'weight': _safe_float(
                    raw_target.get('weight'),
                    0.0,
                    minimum=0.0,
                ),
                'rest': _safe_int(
                    raw_target.get('rest'),
                    exercise.rest or 60,
                    minimum=0,
                ),
            }

            submitted[(exercise.id, category)] = {
                'exercise': exercise,
                'category': category,
                'target': target,
            }

    # ------------------------------------------------------------------
    # Load existing rows in the user's SAVED order.
    # ------------------------------------------------------------------
    existing_rows = (
        WorkoutExercise.query
        .filter_by(workout_id=workout.id)
        .order_by(
            WorkoutExercise.order.asc(),
            WorkoutExercise.id.asc(),
        )
        .all()
    )

    existing_map = {}

    for item in existing_rows:
        category = item.category

        if not category:
            categories = (
                item.categories
                if isinstance(item.categories, list)
                else []
            )
            category = (
                categories[0]
                if categories
                else (
                    item.exercise.exercise_type
                    if item.exercise
                    else None
                )
            )

        existing_map[(item.exercise_id, category)] = item

    submitted_keys = set(submitted.keys())
    existing_keys = set(existing_map.keys())

    # ------------------------------------------------------------------
    # Remove only rows the user actually deselected.
    # ------------------------------------------------------------------
    for key in existing_keys - submitted_keys:
        db.session.delete(existing_map[key])

    # ------------------------------------------------------------------
    # Update existing rows WITHOUT changing their order.
    # ------------------------------------------------------------------
    retained_rows = []

    for item in existing_rows:
        category = item.category

        if not category:
            categories = (
                item.categories
                if isinstance(item.categories, list)
                else []
            )
            category = (
                categories[0]
                if categories
                else (
                    item.exercise.exercise_type
                    if item.exercise
                    else None
                )
            )

        key = (item.exercise_id, category)

        if key not in submitted:
            continue

        target = submitted[key]['target']

        item.custom_sets = target['sets']
        item.custom_reps = target['reps']
        item.custom_duration = target['duration']
        item.custom_rest = target['rest']
        item.categories = [category]
        item.category_targets = {category: target}
        item.category = category

        retained_rows.append(item)

    # ------------------------------------------------------------------
    # Create only genuinely NEW rows.
    #
    # They will be placed before the existing rows.
    # ------------------------------------------------------------------
    new_rows = []

    for key, entry in submitted.items():
        if key in existing_map:
            continue

        exercise = entry['exercise']
        category = entry['category']
        target = entry['target']

        item = WorkoutExercise(
            workout_id=workout.id,
            exercise_id=exercise.id,
            custom_sets=target['sets'],
            custom_reps=target['reps'],
            custom_duration=target['duration'],
            custom_rest=target['rest'],
            categories=[category],
            category_targets={category: target},
            category=category,
        )

        db.session.add(item)
        new_rows.append(item)

    # ------------------------------------------------------------------
    # Final order:
    #
    # NEW exercises first
    # EXISTING exercises afterward in their previously saved order
    # ------------------------------------------------------------------
    final_rows = new_rows + retained_rows

    for position, item in enumerate(final_rows):
        item.order = position

    db.session.commit()
    return workout

def add_exercise(workout_id, data):
    """Add one WorkoutExercise row for API/MCP consumers."""
    workout = get_workout(workout_id)
    exercise = db.session.get(Exercise, data.get('exercise_id'))
    if not workout or not exercise:
        return None

    next_order = max([we.order or 0 for we in workout.exercises], default=-1) + 1
    item = WorkoutExercise(
        workout_id=workout.id,
        exercise_id=exercise.id,
        custom_sets=data.get('custom_sets'),
        custom_reps=data.get('custom_reps'),
        custom_duration=data.get('custom_duration'),
        custom_rest=data.get('custom_rest'),
        categories=data.get('categories'),
        category_targets=data.get('category_targets'),
        category=data.get('category'),
        order=data.get('order', next_order),
    )
    db.session.add(item)
    db.session.commit()
    return item


def remove_workout_exercise(workout_id, workout_exercise_id):
    item = WorkoutExercise.query.filter_by(
        id=workout_exercise_id,
        workout_id=workout_id,
    ).first()
    if not item:
        return False

    db.session.delete(item)
    db.session.commit()
    return True


def reorder_workout_exercises(workout_id, order_data):
    """Validate and persist the complete workout exercise ordering."""
    workout = get_workout(workout_id)
    if not workout:
        return None

    if not isinstance(order_data, list):
        raise ValueError('Invalid payload')

    exercises = WorkoutExercise.query.filter_by(workout_id=workout.id).all()
    exercise_map = {item.id: item for item in exercises}
    submitted_ids = []
    seen_ids = set()

    for item in order_data:
        if not isinstance(item, dict):
            raise ValueError('Invalid order item')
        try:
            workout_exercise_id = int(item.get('id'))
        except (TypeError, ValueError):
            raise ValueError('Invalid exercise ID')

        if workout_exercise_id not in exercise_map or workout_exercise_id in seen_ids:
            raise ValueError('Invalid or duplicate exercise ID')

        seen_ids.add(workout_exercise_id)
        submitted_ids.append(workout_exercise_id)

    if len(submitted_ids) != len(exercises):
        raise ValueError('Incomplete exercise order')

    for position, workout_exercise_id in enumerate(submitted_ids):
        exercise_map[workout_exercise_id].order = position

    db.session.commit()
    return workout


def start_workout(workout_id):
    """Create an active workout session for an existing workout definition."""
    if not get_workout(workout_id):
        return None

    log = WorkoutLog(workout_id=workout_id, start_time=datetime.utcnow())
    db.session.add(log)
    db.session.commit()
    return log


def get_workout_log(log_id):
    return db.session.get(WorkoutLog, log_id)


def _optional_int(value):
    if value is None or str(value).strip() == '':
        return None
    return _safe_int(value)


def _optional_float(value):
    if value is None or str(value).strip() == '':
        return None
    return _safe_float(value)


def _category_for_workout_exercise(item):
    if item.category:
        return item.category
    if isinstance(item.categories, list) and item.categories:
        return item.categories[0]
    return item.exercise.exercise_type if item.exercise else None


def _target_for_workout_exercise(item):
    exercise = item.exercise
    category = _category_for_workout_exercise(item)
    target = {}

    if isinstance(item.category_targets, dict):
        target = item.category_targets.get(category, {})

    if not target:
        target = {
            'sets': item.custom_sets if item.custom_sets is not None else (exercise.sets or 3),
            'reps': item.custom_reps if item.custom_reps is not None else (exercise.reps or 10),
            'duration': item.custom_duration if item.custom_duration is not None else (exercise.duration or 30),
            'weight': 0,
            'rest': item.custom_rest if item.custom_rest is not None else (exercise.rest or 60),
        }

    return category, target


def _last_value(rows, attr, fallback=None):
    for row in reversed(rows):
        value = getattr(row, attr, None)
        if value is not None:
            return value
    return fallback


def get_log_view_state(log_id):
    """Build the exact data contract expected by log_workout.html.

    Only completed prior sessions are used for defaults and personal-best values,
    matching the legacy route behavior. The active session is never treated as
    history until it is explicitly finished.
    """
    log = get_workout_log(log_id)
    if not log:
        return None

    exercise_cards = []
    for item in sorted(log.workout.exercises, key=lambda x: x.order):
        exercise = item.exercise
        category, target = _target_for_workout_exercise(item)

        history_rows = (
            ExerciseHistory.query
            .join(WorkoutLog, ExerciseHistory.workout_log_id == WorkoutLog.id)
            .filter(
                ExerciseHistory.exercise_id == exercise.id,
                ExerciseHistory.category == category,
                WorkoutLog.end_time.isnot(None),
                WorkoutLog.id != log.id,
            )
            .order_by(WorkoutLog.end_time.desc(), ExerciseHistory.set_number.asc())
            .all()
        )

        max_weight = max(
            (row.weight for row in history_rows if row.weight is not None),
            default=None,
        )
        max_duration = max(
            (row.duration for row in history_rows if row.duration is not None),
            default=None,
        )

        last_session_id = history_rows[0].workout_log_id if history_rows else None
        last_session_rows = [
            row for row in history_rows if row.workout_log_id == last_session_id
        ]
        last_session_rows.sort(key=lambda row: row.set_number)

        current_sets = [
            item_set for item_set in log.sets
            if item_set.workout_exercise_id == item.id
        ]

        exercise_cards.append({
            'item': item,
            'exercise': exercise,
            'category': category,
            'target': target,
            'history_max_weight': max_weight,
            'history_max_duration': max_duration,
            'last_reps': _last_value(last_session_rows, 'reps', target.get('reps')),
            'last_weight': _last_value(last_session_rows, 'weight', target.get('weight', 0)),
            'last_duration': _last_value(last_session_rows, 'duration', target.get('duration')),
            'last_rest': _last_value(last_session_rows, 'rest', target.get('rest', exercise.rest or 60)),
            'logged_sets': sorted(current_sets, key=lambda item_set: item_set.set_number),
        })

    return {'log': log, 'exercise_cards': exercise_cards}


def log_ui_set(log_id, data):
    """Persist a set using the current log_workout.html request contract."""
    log = get_workout_log(log_id)
    if not log:
        return None

    try:
        workout_exercise_id = int(data.get('workout_exercise_id'))
        set_number = int(data.get('set_number'))
    except (TypeError, ValueError):
        raise ValueError('Invalid workout exercise or set number.')

    item = WorkoutExercise.query.filter_by(
        id=workout_exercise_id,
        workout_id=log.workout_id,
    ).first()
    if not item:
        raise LookupError('Workout exercise/category was not found.')

    category = _category_for_workout_exercise(item)
    rest_default = (
        item.custom_rest
        if item.custom_rest is not None
        else (item.exercise.rest or 60)
    )

    set_log = SetLog(
        workout_log_id=log.id,
        exercise_id=item.exercise_id,
        workout_exercise_id=item.id,
        category=category,
        set_number=set_number,
        reps=_optional_int(data.get('reps')),
        weight=_optional_float(data.get('weight')),
        duration=_optional_float(data.get('duration')),
        time_seconds=_optional_int(data.get('time_seconds')),
        distance_meters=_optional_float(data.get('distance_meters')),
        rest=_safe_int(data.get('rest'), rest_default),
    )
    db.session.add(set_log)
    db.session.commit()
    return set_log


def log_set(log_id, data):
    """Log a set for API/MCP consumers using the same session rules as the UI."""
    log = get_workout_log(log_id)
    if not log:
        return None

    workout_exercise_id = _safe_int(data.get('workout_exercise_id'))
    item = None
    if workout_exercise_id is not None:
        item = WorkoutExercise.query.filter_by(
            id=workout_exercise_id,
            workout_id=log.workout_id,
        ).first()
        if not item:
            raise LookupError('Workout exercise/category was not found.')

    exercise_id = _safe_int(data.get('exercise_id'))
    if exercise_id is None and item:
        exercise_id = item.exercise_id
    if exercise_id is None:
        raise ValueError('exercise_id or workout_exercise_id is required.')

    exercise = db.session.get(Exercise, exercise_id)
    if not exercise:
        raise LookupError('Exercise not found.')

    set_number = _safe_int(data.get('set_number'))
    if set_number is None:
        count_query = SetLog.query.filter_by(
            workout_log_id=log.id,
            exercise_id=exercise_id,
        )
        if item:
            count_query = count_query.filter_by(workout_exercise_id=item.id)
        set_number = count_query.count() + 1

    category = data.get('category') or (
        _category_for_workout_exercise(item) if item else None
    )
    rest_default = (
        item.custom_rest
        if item and item.custom_rest is not None
        else (exercise.rest or 60)
    )

    set_log = SetLog(
        workout_log_id=log.id,
        exercise_id=exercise_id,
        workout_exercise_id=item.id if item else None,
        category=category,
        set_number=set_number,
        reps=_optional_int(data.get('reps')),
        weight=_optional_float(data.get('weight')),
        duration=_optional_float(data.get('duration')),
        time_seconds=_optional_int(data.get('time_seconds')),
        distance_meters=_optional_float(data.get('distance_meters')),
        rest=_safe_int(data.get('rest'), rest_default),
        rest_start_heart_rate=_optional_int(data.get('rest_start_heart_rate')),
        rest_end_heart_rate=_optional_int(data.get('rest_end_heart_rate')),
        rest_seconds=_optional_int(data.get('rest_seconds')),
    )
    db.session.add(set_log)
    db.session.commit()
    return set_log


def save_rest(log_id, set_id, data):
    """Persist rest metrics for a set. Heart-rate values are optional for API/MCP."""
    log = get_workout_log(log_id)
    if not log:
        return None

    item = SetLog.query.filter_by(id=set_id, workout_log_id=log.id).first()
    if not item:
        return None

    start_hr = data.get('rest_start_heart_rate', data.get('starting_heart_rate'))
    end_hr = data.get('rest_end_heart_rate', data.get('ending_heart_rate'))
    rest_seconds = data.get('rest_seconds')

    if start_hr is not None and str(start_hr).strip() != '':
        start_hr = _safe_int(start_hr)
        if start_hr is None or not 1 <= start_hr <= 300:
            raise ValueError('Heart rate must be between 1 and 300 BPM.')
        item.rest_start_heart_rate = start_hr

    if end_hr is not None and str(end_hr).strip() != '':
        end_hr = _safe_int(end_hr)
        if end_hr is None or not 1 <= end_hr <= 300:
            raise ValueError('Heart rate must be between 1 and 300 BPM.')
        item.rest_end_heart_rate = end_hr

    if rest_seconds is not None and str(rest_seconds).strip() != '':
        parsed_rest_seconds = _safe_int(rest_seconds)
        if parsed_rest_seconds is None:
            raise ValueError('Rest time must be a whole number of seconds.')
        item.rest_seconds = max(0, parsed_rest_seconds)

    db.session.commit()
    return item


def save_ui_rest(log_id, data):
    """Persist rest data using the stricter current UI contract."""
    log = get_workout_log(log_id)
    if not log:
        return None

    try:
        set_id = int(data.get('set_id'))
        starting_heart_rate = int(data.get('starting_heart_rate'))
        ending_heart_rate = int(data.get('ending_heart_rate'))
        rest_seconds = max(0, int(data.get('rest_seconds')))
    except (TypeError, ValueError):
        raise ValueError(
            'Starting heart rate, ending heart rate, and rest time are required.'
        )

    if not 1 <= starting_heart_rate <= 300 or not 1 <= ending_heart_rate <= 300:
        raise ValueError('Heart rate must be between 1 and 300 BPM.')

    set_log = SetLog.query.filter_by(id=set_id, workout_log_id=log.id).first()
    if not set_log:
        raise LookupError('The logged set was not found.')

    set_log.rest_start_heart_rate = starting_heart_rate
    set_log.rest_end_heart_rate = ending_heart_rate
    set_log.rest_seconds = rest_seconds
    db.session.commit()
    return set_log


def finish_workout(log_id, notes=None):
    """Finish a session and snapshot only its completed sets into history."""
    log = get_workout_log(log_id)
    if not log:
        return None

    log.end_time = datetime.utcnow()
    if notes is not None:
        log.notes = notes

    # Rebuild the snapshot so retrying finish is idempotent for this session.
    ExerciseHistory.query.filter_by(
        workout_log_id=log.id
    ).delete(synchronize_session=False)

    for set_log in log.sets:
        workout_exercise = (
            db.session.get(WorkoutExercise, set_log.workout_exercise_id)
            if set_log.workout_exercise_id
            else None
        )
        category = set_log.category or (
            workout_exercise.category if workout_exercise else None
        )
        db.session.add(ExerciseHistory(
            workout_log_id=log.id,
            workout_exercise_id=set_log.workout_exercise_id,
            exercise_id=set_log.exercise_id,
            category=category,
            set_number=set_log.set_number,
            reps=set_log.reps,
            weight=set_log.weight,
            duration=set_log.duration,
            time_seconds=set_log.time_seconds,
            distance_meters=set_log.distance_meters,
            rest=set_log.rest,
            rest_start_heart_rate=set_log.rest_start_heart_rate,
            rest_end_heart_rate=set_log.rest_end_heart_rate,
            rest_seconds=set_log.rest_seconds,
            logged_at=datetime.utcnow(),
        ))

    db.session.commit()
    return log



def get_recent_workout_logs(limit=10):
    """Return recently completed workout sessions, newest first."""
    limit = _safe_int(limit, 10, minimum=1)
    limit = min(limit, 100)
    return (
        WorkoutLog.query
        .filter(WorkoutLog.end_time.isnot(None))
        .order_by(WorkoutLog.end_time.desc(), WorkoutLog.id.desc())
        .limit(limit)
        .all()
    )


def get_workout_history(workout_id=None, limit=20):
    """Return completed workout sessions, optionally filtered by workout definition."""
    limit = _safe_int(limit, 20, minimum=1)
    limit = min(limit, 100)

    query = WorkoutLog.query.filter(WorkoutLog.end_time.isnot(None))
    if workout_id:
        workout_id = _safe_int(workout_id)
        if workout_id is None or not get_workout(workout_id):
            return None
        query = query.filter(WorkoutLog.workout_id == workout_id)

    return (
        query
        .order_by(WorkoutLog.end_time.desc(), WorkoutLog.id.desc())
        .limit(limit)
        .all()
    )


def get_exercise_history(exercise_id, limit=50):
    """Return completed historical set snapshots for one exercise, newest first."""
    exercise_id = _safe_int(exercise_id)
    exercise = db.session.get(Exercise, exercise_id) if exercise_id is not None else None
    if not exercise:
        return None

    limit = _safe_int(limit, 50, minimum=1)
    limit = min(limit, 500)

    rows = (
        ExerciseHistory.query
        .join(WorkoutLog, ExerciseHistory.workout_log_id == WorkoutLog.id)
        .filter(
            ExerciseHistory.exercise_id == exercise.id,
            WorkoutLog.end_time.isnot(None),
        )
        .order_by(
            WorkoutLog.end_time.desc(),
            ExerciseHistory.set_number.asc(),
            ExerciseHistory.id.asc(),
        )
        .limit(limit)
        .all()
    )

    return {
        'exercise': {
            'id': exercise.id,
            'name': exercise.name,
            'exercise_type': exercise.exercise_type,
        },
        'history': [
            {
                'id': row.id,
                'workout_log_id': row.workout_log_id,
                'workout_exercise_id': row.workout_exercise_id,
                'category': row.category,
                'set_number': row.set_number,
                'reps': row.reps,
                'weight': row.weight,
                'duration': row.duration,
                'time_seconds': row.time_seconds,
                'distance_meters': row.distance_meters,
                'rest': row.rest,
                'rest_start_heart_rate': row.rest_start_heart_rate,
                'rest_end_heart_rate': row.rest_end_heart_rate,
                'rest_seconds': row.rest_seconds,
                'logged_at': row.logged_at.isoformat() if row.logged_at else None,
            }
            for row in rows
        ],
    }


def get_training_history(start_date, end_date):
    """Return completed workout sessions whose completion time falls in an inclusive date range."""
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
    except (TypeError, ValueError):
        raise ValueError('Dates must use YYYY-MM-DD format.')

    if end < start:
        raise ValueError('end_date must be on or after start_date.')

    # Make the end date inclusive without relying on database-specific date functions.
    from datetime import timedelta
    end_exclusive = end + timedelta(days=1)

    return (
        WorkoutLog.query
        .filter(
            WorkoutLog.end_time.isnot(None),
            WorkoutLog.end_time >= start,
            WorkoutLog.end_time < end_exclusive,
        )
        .order_by(WorkoutLog.end_time.desc(), WorkoutLog.id.desc())
        .all()
    )

def as_dict(workout):
    return workout_to_dict(workout)


def log_as_dict(log):
    return workout_log_to_dict(log)


def set_as_dict(item):
    return set_log_to_dict(item)
