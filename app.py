import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from werkzeug.utils import secure_filename
from models import (
    db, run_migrations, Exercise, Workout, WorkoutExercise, WorkoutLog, SetLog,
    ExerciseHistory, FitnessTestResult, SoundFile, AppSetting, TrainingPlan, TrainingPlanMonth
)
from api.v1.routes import api_v1
from services import exercise_service, workout_service, fitness_service

import calendar as pycalendar
from datetime import date, timedelta
from collections import defaultdict

# Load environment variables
load_dotenv()

# Absolute path to project root
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# Secret key & absolute DB path locking
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key-change-in-prod')
db_dir = os.path.join(basedir, 'data')
os.makedirs(db_dir, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(db_dir, 'cmfit.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')
app.config['SOUND_FOLDER'] = os.path.join(basedir, 'static', 'sounds')

db.init_app(app)
app.register_blueprint(api_v1)

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SOUND_FOLDER'], exist_ok=True)

# Valid Exercise Types
VALID_EXERCISE_TYPES = [
    'Movement',
    'Aerobic Capacity',
    'Strength',
    'Speed',
    'ALactic ATP',
    'Anaerobic (HIT)'
]

PLAN_CATEGORIES = [
    'Aerobic Capacity',
    'Strength',
    'Speed',
    'ALactic ATP',
    'Anaerobic (HIT)'
]

PLAN_CATEGORY_SHORT = {
    'Aerobic Capacity': 'Aerobic',
    'Strength': 'Strength',
    'Speed': 'Speed',
    'ALactic ATP': 'Alactic',
    'Anaerobic (HIT)': 'HIT'
}

DEFAULT_PLAN_MIXES = [
    {'Aerobic Capacity': 35, 'Strength': 25, 'Speed': 15, 'ALactic ATP': 10, 'Anaerobic (HIT)': 15},
    {'Aerobic Capacity': 30, 'Strength': 35, 'Speed': 10, 'ALactic ATP': 10, 'Anaerobic (HIT)': 15},
    {'Aerobic Capacity': 20, 'Strength': 50, 'Speed': 10, 'ALactic ATP': 10, 'Anaerobic (HIT)': 10},
    {'Aerobic Capacity': 15, 'Strength': 55, 'Speed': 10, 'ALactic ATP': 10, 'Anaerobic (HIT)': 10},
    {'Aerobic Capacity': 15, 'Strength': 45, 'Speed': 15, 'ALactic ATP': 15, 'Anaerobic (HIT)': 10},
    {'Aerobic Capacity': 10, 'Strength': 35, 'Speed': 20, 'ALactic ATP': 25, 'Anaerobic (HIT)': 10},
    {'Aerobic Capacity': 10, 'Strength': 30, 'Speed': 25, 'ALactic ATP': 25, 'Anaerobic (HIT)': 10},
    {'Aerobic Capacity': 10, 'Strength': 25, 'Speed': 25, 'ALactic ATP': 25, 'Anaerobic (HIT)': 15},
    {'Aerobic Capacity': 10, 'Strength': 20, 'Speed': 30, 'ALactic ATP': 25, 'Anaerobic (HIT)': 15},
    {'Aerobic Capacity': 10, 'Strength': 20, 'Speed': 30, 'ALactic ATP': 25, 'Anaerobic (HIT)': 15},
    {'Aerobic Capacity': 15, 'Strength': 25, 'Speed': 30, 'ALactic ATP': 20, 'Anaerobic (HIT)': 10},
    {'Aerobic Capacity': 20, 'Strength': 30, 'Speed': 25, 'ALactic ATP': 15, 'Anaerobic (HIT)': 10},
]

DEFAULT_PLAN_PHASES = [
    ('Foundation', 'Build aerobic capacity, movement quality and work capacity'),
    ('Foundation', 'Build aerobic capacity and prepare for heavier work'),
    ('Strength', 'Strength emphasis'),
    ('Strength', 'Strength emphasis'),
    ('Strength → Power', 'Transition from strength toward high output'),
    ('Power', 'Power and alactic emphasis'),
    ('Power', 'Power development'),
    ('Power', 'Power development'),
    ('Peak', 'Speed and alactic emphasis'),
    ('Peak', 'Speed and alactic emphasis'),
    ('Peak', 'Maintain strength while emphasizing speed'),
    ('Peak / Transition', 'Consolidate gains and prepare for the next cycle'),
]


# Helpers
def save_image(file):
    if file and file.filename != '':
        ext = os.path.splitext(secure_filename(file.filename))[1]
        unique_name = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        file.save(filepath)
        return unique_name
    return None


def save_multiple_images(files):
    filenames = []
    for file in files:
        if file and file.filename != '':
            saved_name = save_image(file)
            if saved_name:
                filenames.append(saved_name)
    return filenames


def save_sound(file):
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['SOUND_FOLDER'], filename)
        file.save(filepath)
        return filename
    return None


def safe_int(val, default=0):
    try:
        return int(val) if val is not None and str(val).strip() != '' else default
    except (ValueError, TypeError):
        return default


def safe_float(val, default=0.0):
    try:
        return float(val) if val is not None and str(val).strip() != '' else default
    except (ValueError, TypeError):
        return default


def get_sound_settings():
    settings = {s.key: s.value for s in AppSetting.query.all()}

    def get_file(key):
        file_id = safe_int(settings.get(key, 0))
        return SoundFile.query.get(file_id) if file_id > 0 else None

    start_file = get_file('sound_start_file_id')
    notice_file = get_file('sound_notice_file_id')
    rest_end_file = get_file('sound_rest_end_file_id')
    end_file = get_file('sound_end_file_id')
    log_set_file = get_file('sound_log_set_file_id')

    return {
        'start_enabled': settings.get('sound_start_enabled', 'false') == 'true',
        'start_url': url_for('static', filename=f'sounds/{start_file.filename}') if start_file else None,
        'notice_enabled': settings.get('sound_notice_enabled', 'false') == 'true',
        'notice_url': url_for('static', filename=f'sounds/{notice_file.filename}') if notice_file else None,
        'notice_seconds': safe_int(settings.get('sound_notice_seconds'), 5),
        'rest_end_enabled': settings.get('sound_rest_end_enabled', 'false') == 'true',
        'rest_end_url': url_for('static', filename=f'sounds/{rest_end_file.filename}') if rest_end_file else None,
        'end_enabled': settings.get('sound_end_enabled', 'false') == 'true',
        'end_url': url_for('static', filename=f'sounds/{end_file.filename}') if end_file else None,
        'log_set_enabled': settings.get('sound_log_set_enabled', 'false') == 'true',
        'log_set_url': url_for('static', filename=f'sounds/{log_set_file.filename}') if log_set_file else None,
    }


@app.context_processor
def inject_sound_config():
    try:
        return dict(sound_config=get_sound_settings())
    except Exception:
        return dict(sound_config={})


# Routes
@app.route('/')
def index():
    return redirect(url_for('workout_list'))


@app.route('/exercises')
def exercise_list():
    all_exercises = exercise_service.list_exercises()
    return render_template('exercise_list.html', all_exercises=all_exercises)


@app.route('/exercise/new', methods=['GET', 'POST'])
def add_new_exercise():
    return_workout_id = request.args.get('return_workout_id', '')

    if request.method == 'POST':
        return_workout_id = request.form.get('return_workout_id', '')
        name = (request.form.get('name') or '').strip()
        selected_categories = [c for c in request.form.getlist('categories') if c in VALID_EXERCISE_TYPES]

        if not name:
            flash('Exercise name is required.', 'error')
            return redirect(request.url)
        if not selected_categories:
            flash('Please select at least one category/type.', 'error')
            return redirect(request.url)

        category_targets = {}
        for category in selected_categories:
            category_targets[category] = {
                'sets': max(1, safe_int(request.form.get(f'sets_{category}'), 3)),
                'reps': max(1, safe_int(request.form.get(f'reps_{category}'), 10)),
                'duration': max(0.0, safe_float(request.form.get(f'duration_{category}'), 30.0)),
                'weight': max(0.0, safe_float(request.form.get(f'weight_{category}'), 0.0)),
                'rest': max(0, safe_int(request.form.get(f'rest_{category}'), 60)),
            }

        muscles = request.form.getlist('muscles')
        link = request.form.get('link')
        instructions = request.form.get('instructions')
        uploaded_files = request.files.getlist('images') or request.files.getlist('image')
        image_list = save_multiple_images(uploaded_files)

        exercise_service.create_exercise({
            'name': name,
            'exercise_type': selected_categories[0],
            'categories': selected_categories,
            'category_targets': category_targets,
            'muscles': muscles,
            'sets': category_targets[selected_categories[0]]['sets'],
            'reps': category_targets[selected_categories[0]]['reps'],
            'duration': category_targets[selected_categories[0]]['duration'],
            'rest': category_targets[selected_categories[0]]['rest'],
            'image': image_list[0] if image_list else None,
            'image_urls': image_list if image_list else None,
            'link': link,
            'instructions': instructions,
        })

        if return_workout_id:
            return redirect(url_for('add_exercise', workout_id=return_workout_id))
        return redirect(url_for('exercise_list'))

    muscle_groups = ['Chest', 'Back', 'Shoulders', 'Biceps', 'Triceps', 'Legs', 'Abs', 'Cardio']
    return render_template('display_exercise.html', muscle_groups=muscle_groups,
                           valid_exercise_types=VALID_EXERCISE_TYPES,
                           return_workout_id=return_workout_id)


@app.route('/exercises/reorder', methods=['POST'])
def reorder_exercises():
    data = request.get_json() or {}
    exercise_service.reorder_exercises(data.get('order', []))
    return jsonify({'status': 'success', 'message': 'Exercises reordered successfully'})


@app.route('/exercise/<int:id>', methods=['GET', 'POST'])
def display_exercise(id):
    exercise = exercise_service.get_exercise(id) or abort(404)
    return_workout_id = request.args.get('return_workout_id', '')

    if request.method == 'POST':
        return_workout_id = request.form.get('return_workout_id', '')
        name = (request.form.get('name') or exercise.name).strip()
        selected_categories = [c for c in request.form.getlist('categories') if c in VALID_EXERCISE_TYPES]
        if not selected_categories:
            flash('Please select at least one category/type.', 'error')
            return redirect(request.url)

        category_targets = {}
        for category in selected_categories:
            category_targets[category] = {
                'sets': max(1, safe_int(request.form.get(f'sets_{category}'), 3)),
                'reps': max(1, safe_int(request.form.get(f'reps_{category}'), 10)),
                'duration': max(0.0, safe_float(request.form.get(f'duration_{category}'), 30.0)),
                'weight': max(0.0, safe_float(request.form.get(f'weight_{category}'), 0.0)),
                'rest': max(0, safe_int(request.form.get(f'rest_{category}'), 60)),
            }

        if isinstance(exercise.image_urls, list):
            existing_images = list(exercise.image_urls)
        elif exercise.image:
            existing_images = [exercise.image]
        else:
            existing_images = []

        for img_to_delete in request.form.getlist('delete_images'):
            if img_to_delete in existing_images:
                existing_images.remove(img_to_delete)
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], img_to_delete))
                except OSError:
                    pass

        uploaded_files = request.files.getlist('images') or request.files.getlist('image')
        new_image_list = save_multiple_images(uploaded_files)
        combined_images = existing_images + new_image_list

        exercise_service.update_exercise(id, {
            'name': name,
            'categories': selected_categories,
            'category_targets': category_targets,
            'exercise_type': selected_categories[0],
            'sets': category_targets[selected_categories[0]]['sets'],
            'reps': category_targets[selected_categories[0]]['reps'],
            'duration': category_targets[selected_categories[0]]['duration'],
            'rest': category_targets[selected_categories[0]]['rest'],
            'instructions': request.form.get('instructions', ''),
            'link': request.form.get('link', ''),
            'muscles': request.form.getlist('muscles'),
            'image_urls': combined_images if combined_images else None,
            'image': combined_images[0] if combined_images else None,
        })

        flash('Exercise updated successfully.', 'success')
        if return_workout_id:
            return redirect(url_for('add_exercise', workout_id=return_workout_id))
        return redirect(url_for('exercise_list'))

    muscle_groups = ['Chest', 'Back', 'Shoulders', 'Biceps', 'Triceps', 'Legs', 'Abs', 'Cardio']
    return render_template('display_exercise.html', exercise=exercise,
                           muscle_groups=muscle_groups,
                           valid_exercise_types=VALID_EXERCISE_TYPES,
                           return_workout_id=return_workout_id)


@app.route('/exercise/<int:exercise_id>/delete', methods=['POST'])
def delete_exercise(exercise_id):
    exercise = exercise_service.get_exercise(exercise_id) or abort(404)
    return_workout_id = request.form.get('return_workout_id', '')

    images_to_delete = []
    if exercise.image_urls and isinstance(exercise.image_urls, list):
        images_to_delete.extend(exercise.image_urls)
    elif exercise.image:
        images_to_delete.append(exercise.image)

    for img_file in set(images_to_delete):
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], img_file))
        except OSError:
            pass

    exercise_service.delete_exercise(exercise_id)

    flash('Exercise deleted successfully.', 'success')

    if return_workout_id:
        return redirect(url_for('add_exercise', workout_id=return_workout_id))
    return redirect(url_for('exercise_list'))


@app.route('/workouts')
def workout_list():
    workouts = workout_service.list_workouts()
    return render_template('workout_list.html', workouts=workouts)


@app.route('/workout/add', methods=['GET', 'POST'])
def add_workout():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()

        try:
            workout = workout_service.create_workout({
                'title': title,
                'description': description,
            })
        except ValueError:
            flash('Workout title is required.', 'error')
            return render_template(
                'add_workout.html', title=title, description=description
            )

        return redirect(url_for('add_exercise', workout_id=workout.id))

    return render_template('add_workout.html')


@app.route('/workout/<int:workout_id>')
def view_workout(workout_id):
    workout = workout_service.get_workout(workout_id)
    if not workout:
        abort(404)
    sorted_exercises = sorted(workout.exercises, key=lambda x: x.order)
    return render_template(
        'view_workout.html', workout=workout, sorted_exercises=sorted_exercises
    )


def _workout_composition_from_form(selected_ids):
    """Translate the existing workout-composition form into application data."""
    selections = []
    for ex_id in selected_ids:
        try:
            ex_id_int = int(ex_id)
        except (TypeError, ValueError):
            continue

        selected_categories = request.form.getlist(f'categories_{ex_id_int}')
        if not selected_categories:
            continue

        targets = {}
        for category in selected_categories:
            targets[category] = {
                'sets': request.form.get(f'sets_{ex_id_int}_{category}'),
                'reps': request.form.get(f'reps_{ex_id_int}_{category}'),
                'duration': request.form.get(f'duration_{ex_id_int}_{category}'),
                'weight': request.form.get(f'weight_{ex_id_int}_{category}'),
                'rest': request.form.get(f'rest_{ex_id_int}_{category}'),
            }

        selections.append({
            'exercise_id': ex_id_int,
            'categories': selected_categories,
            'targets': targets,
        })
    return selections


@app.route('/workout/<int:workout_id>/add_exercise', methods=['GET', 'POST'])
def add_exercise(workout_id):
    workout = workout_service.get_workout(workout_id)
    if not workout:
        abort(404)

    if request.method == 'POST':
        selections = _workout_composition_from_form(request.form.getlist('exercise_ids'))
        workout_service.replace_workout_exercises(workout.id, selections)
        return redirect(url_for('view_workout', workout_id=workout.id))

    state = workout_service.get_composition_state(workout.id, VALID_EXERCISE_TYPES)
    return render_template(
        'add_exercise_to_workout.html',
        workout=state['workout'],
        all_exercises=state['all_exercises'],
        existing_map=state['existing_map'],
    )


@app.route('/workout/<int:workout_id>/reorder', methods=['POST'])
def reorder_workout_exercises(workout_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'status': 'error', 'message': 'Invalid payload'}), 400

    try:
        workout = workout_service.reorder_workout_exercises(workout_id, data.get('order'))
    except ValueError as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 400

    if not workout:
        abort(404)
    return jsonify({'status': 'success'})


@app.route('/workout/<int:workout_id>/remove_exercise/<int:we_id>', methods=['POST'])
def remove_exercise_from_workout(workout_id, we_id):
    if not workout_service.get_workout(workout_id):
        abort(404)
    if not workout_service.remove_workout_exercise(workout_id, we_id):
        abort(404)

    flash('Exercise removed from workout.', 'success')
    return redirect(url_for('view_workout', workout_id=workout_id))


@app.route('/workout/<int:workout_id>/delete', methods=['POST'])
def delete_workout(workout_id):
    if not workout_service.delete_workout(workout_id):
        abort(404)
    flash('Workout deleted successfully.', 'success')
    return redirect(url_for('workout_list'))


@app.route('/workout/<int:workout_id>/start')
def start_workout(workout_id):
    log = workout_service.start_workout(workout_id)
    if not log:
        abort(404)
    return redirect(url_for('log_exercise', log_id=log.id))


@app.route('/log/<int:log_id>', methods=['GET', 'POST'])
def log_exercise(log_id):
    state = workout_service.get_log_view_state(log_id)
    if not state:
        abort(404)

    log = state['log']

    if request.method == 'POST':
        data = request.get_json(silent=True) if request.is_json else request.form
        try:
            set_log = workout_service.log_ui_set(log_id, data)
        except ValueError as exc:
            return jsonify({'status': 'error', 'message': str(exc)}), 400
        except LookupError as exc:
            return jsonify({'status': 'error', 'message': str(exc)}), 404

        is_ajax = (
            request.is_json
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Accept', '')
        )
        if is_ajax:
            return jsonify({'status': 'success', 'set_id': set_log.id}), 200
        return redirect(url_for('log_exercise', log_id=log.id))

    return render_template(
        'log_workout.html',
        log=log,
        exercise_cards=state['exercise_cards'],
    )


@app.route('/log/<int:log_id>/rest', methods=['POST'])
def save_rest_info(log_id):
    if not workout_service.get_workout_log(log_id):
        abort(404)

    data = request.get_json(silent=True) if request.is_json else request.form

    try:
        set_log = workout_service.save_ui_rest(log_id, data)
    except ValueError as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 400
    except LookupError as exc:
        return jsonify({'status': 'error', 'message': str(exc)}), 404
    except Exception:
        db.session.rollback()
        app.logger.exception(
            'Failed to save rest information for workout log %s', log_id
        )
        return jsonify({
            'status': 'error',
            'message': 'Database error while saving rest information. Check the Flask console for details.'
        }), 500

    return jsonify({'status': 'success', 'set_id': set_log.id}), 200


@app.route('/log/<int:log_id>/finish', methods=['POST'])
def finish_workout(log_id):
    log = workout_service.finish_workout(log_id, request.form.get('notes', ''))
    if not log:
        abort(404)
    return render_template('finished_workout.html', log=log)


@app.route('/progress')
def progress():
    state = fitness_service.get_progress_view_state(
        request.args.get('year'),
        request.args.get('month'),
    )
    return render_template('progress.html', **state)


@app.route('/progress/fitness-test', methods=['POST'])
def save_fitness_test():
    key = (request.form.get('test_key') or '').strip()
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
    )
    try:
        result, definition = fitness_service.save_ui_fitness_test(request.form)
    except LookupError as exc:
        if is_ajax:
            return jsonify({'status': 'error', 'message': str(exc)}), 400
        flash(str(exc), 'error')
        return redirect(url_for('progress', tab='fitness'))
    except ValueError as exc:
        if is_ajax:
            return jsonify({'status': 'error', 'message': str(exc)}), 400
        flash(str(exc), 'error')
        return redirect(url_for('progress', tab='fitness', test=key))

    if is_ajax:
        return jsonify({
            'status': 'success',
            'message': f"{definition['name']} saved successfully.",
            'result': fitness_service.as_dict(result),
        }), 200

    flash(f"{definition['name']} saved successfully.", 'success')
    return redirect(url_for('progress', tab='fitness', test=key))


def _plan_month_payload(month_number, form):
    mix = {}
    for category in PLAN_CATEGORIES:
        mix[category] = max(0, min(100, safe_int(form.get(f'mix_{month_number}_{category}'), 0)))
    if sum(mix.values()) != 100:
        return None
    return {
        'name': (form.get(f'name_{month_number}') or f'Month {month_number}').strip()[:80] or f'Month {month_number}',
        'phase': (form.get(f'phase_{month_number}') or '').strip()[:80],
        'focus': (form.get(f'focus_{month_number}') or '').strip()[:160],
        'sessions_per_week': max(0, min(14, safe_float(form.get(f'sessions_{month_number}'), 3))),
        'category_mix': mix,
        'notes': (form.get(f'notes_{month_number}') or '').strip(),
    }


def _make_default_plan_months():
    months = []
    for i in range(12):
        phase, focus = DEFAULT_PLAN_PHASES[i]
        months.append({
            'month_number': i + 1,
            'name': f'Month {i + 1}',
            'phase': phase,
            'focus': focus,
            'sessions_per_week': 3,
            'category_mix': dict(DEFAULT_PLAN_MIXES[i]),
            'notes': ''
        })
    return months


@app.route('/plan')
def plan():
    plans = TrainingPlan.query.order_by(TrainingPlan.updated_at.desc(), TrainingPlan.id.desc()).all()
    selected_id = safe_int(request.args.get('id'), 0)
    selected = db.session.get(TrainingPlan, selected_id) if selected_id else (plans[0] if plans else None)
    if selected and selected not in plans:
        selected = None
    return render_template(
        'plan.html',
        plans=plans,
        selected_plan=selected,
        default_months=_make_default_plan_months(),
        plan_categories=PLAN_CATEGORIES,
        category_short=PLAN_CATEGORY_SHORT,
    )


@app.route('/plan/new', methods=['POST'])
def create_plan():
    title = (request.form.get('title') or '12-Month Training Plan').strip()[:120]
    raw_start = (request.form.get('start_date') or '').strip()
    try:
        start_date = date.fromisoformat(raw_start) if raw_start else date.today()
    except ValueError:
        start_date = date.today()

    plan_obj = TrainingPlan(title=title or '12-Month Training Plan', start_date=start_date)
    db.session.add(plan_obj)
    db.session.flush()
    for item in _make_default_plan_months():
        db.session.add(TrainingPlanMonth(plan_id=plan_obj.id, **item))
    db.session.commit()
    flash('12-month training plan created.', 'success')
    return redirect(url_for('plan', id=plan_obj.id))


@app.route('/plan/<int:plan_id>/save', methods=['POST'])
def save_plan(plan_id):
    plan_obj = TrainingPlan.query.get_or_404(plan_id)
    title = (request.form.get('title') or '').strip()[:120]
    if not title:
        flash('Plan name is required.', 'error')
        return redirect(url_for('plan', id=plan_id))

    try:
        start_date = date.fromisoformat((request.form.get('start_date') or '').strip())
    except ValueError:
        flash('Please enter a valid plan start date.', 'error')
        return redirect(url_for('plan', id=plan_id))

    payloads = []
    for month_number in range(1, 13):
        payload = _plan_month_payload(month_number, request.form)
        if payload is None:
            flash(f'Month {month_number}: category percentages must total 100%.', 'error')
            return redirect(url_for('plan', id=plan_id))
        payloads.append(payload)

    plan_obj.title = title
    plan_obj.start_date = start_date
    plan_obj.notes = (request.form.get('plan_notes') or '').strip()
    existing = {month.month_number: month for month in plan_obj.months}
    for month_number, payload in enumerate(payloads, start=1):
        month = existing.get(month_number)
        if month is None:
            month = TrainingPlanMonth(plan_id=plan_obj.id, month_number=month_number)
            db.session.add(month)
        for key, value in payload.items():
            setattr(month, key, value)
    db.session.commit()
    flash('Training plan saved.', 'success')
    return redirect(url_for('plan', id=plan_id))


@app.route('/plan/<int:plan_id>/delete', methods=['POST'])
def delete_plan(plan_id):
    plan_obj = TrainingPlan.query.get_or_404(plan_id)
    db.session.delete(plan_obj)
    db.session.commit()
    flash('Training plan deleted.', 'success')
    return redirect(url_for('plan'))


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'upload_sound':
            sound_name = request.form.get('sound_name', '').strip()
            file = request.files.get('sound_file')
            if file and sound_name:
                filename = save_sound(file)
                if filename:
                    sf = SoundFile(name=sound_name, filename=filename)
                    db.session.add(sf)
                    db.session.commit()
                    flash('Sound file uploaded to library.', 'success')
            else:
                flash('Please provide a sound name and valid file.', 'error')

        elif action == 'save_sound_settings':
            # Collect all inputs; getlist returns ['0', '1'] if checked, or ['0'] if unchecked.
            # Checking if '1' is in the resulting list gives exact toggle state.
            def posted_toggle(name):
                # Accept either the hidden 0 + checkbox 1 pattern or a plain
                # checkbox.  This also tolerates older admin.html versions.
                values = request.form.getlist(name)
                return '1' in values or 'true' in [str(v).lower() for v in values]

            start_on = posted_toggle('start_enabled')
            log_set_on = posted_toggle('log_set_enabled')
            notice_on = posted_toggle('notice_enabled')
            rest_end_on = posted_toggle('rest_end_enabled')
            end_on = posted_toggle('end_enabled')

            settings_to_update = {
                'sound_start_enabled': 'true' if start_on else 'false',
                'sound_start_file_id': request.form.get('start_file_id', ''),
                'sound_log_set_enabled': 'true' if log_set_on else 'false',
                'sound_log_set_file_id': request.form.get('log_set_file_id', ''),
                'sound_notice_enabled': 'true' if notice_on else 'false',
                'sound_notice_file_id': request.form.get('notice_file_id', ''),
                'sound_notice_seconds': request.form.get('notice_seconds', '5'),
                'sound_rest_end_enabled': 'true' if rest_end_on else 'false',
                'sound_rest_end_file_id': request.form.get('rest_end_file_id', ''),
                'sound_end_enabled': 'true' if end_on else 'false',
                'sound_end_file_id': request.form.get('end_file_id', ''),
            }

            for key, val in settings_to_update.items():
                setting = AppSetting.query.filter_by(key=key).first()
                if not setting:
                    setting = AppSetting(key=key, value=val)
                    db.session.add(setting)
                else:
                    setting.value = str(val)

            db.session.commit()
            flash('Sound settings updated.', 'success')

        return redirect(url_for('admin'))

    # GET request processing
    sounds = SoundFile.query.order_by(SoundFile.name.asc()).all()
    raw_settings = {s.key: s.value for s in AppSetting.query.all()}

    settings = {
        'start_enabled': raw_settings.get('sound_start_enabled') == 'true',
        'start_file_id': safe_int(raw_settings.get('sound_start_file_id'), None),
        'log_set_enabled': raw_settings.get('sound_log_set_enabled') == 'true',
        'log_set_file_id': safe_int(raw_settings.get('sound_log_set_file_id'), None),
        'notice_enabled': raw_settings.get('sound_notice_enabled') == 'true',
        'notice_file_id': safe_int(raw_settings.get('sound_notice_file_id'), None),
        'notice_seconds': safe_int(raw_settings.get('sound_notice_seconds'), 5),
        'rest_end_enabled': raw_settings.get('sound_rest_end_enabled') == 'true',
        'rest_end_file_id': safe_int(raw_settings.get('sound_rest_end_file_id'), None),
        'end_enabled': raw_settings.get('sound_end_enabled') == 'true',
        'end_file_id': safe_int(raw_settings.get('sound_end_file_id'), None),
    }

    return render_template('admin.html', sounds=sounds, settings=settings)

@app.route('/admin/sound/<int:sound_id>/delete', methods=['POST'])
def delete_sound(sound_id):
    sf = SoundFile.query.get_or_404(sound_id)
    try:
        os.remove(os.path.join(app.config['SOUND_FOLDER'], sf.filename))
    except OSError:
        pass

    db.session.delete(sf)
    db.session.commit()
    flash('Sound file deleted.', 'success')
    return redirect(url_for('admin'))


# Database initialization and migration
def initialize_database():
    """Create missing tables and apply safe migrations at application startup."""
    with app.app_context():
        db.create_all()
        run_migrations(app)
        app.logger.info("Database initialization and migrations completed")


# Run at module import time so migrations also execute when the app is started
# with `flask run`, Gunicorn, uWSGI, or another WSGI server.
initialize_database()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=52889, debug=True)
