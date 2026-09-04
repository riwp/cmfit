import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.utils import secure_filename

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

db = SQLAlchemy(app)

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


# Models
class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    order = db.Column('order', db.Integer, default=0, nullable=False)
    muscles = db.Column(db.JSON, nullable=True)
    sets = db.Column(db.Integer, default=3)
    reps = db.Column(db.Integer, default=10)
    duration = db.Column(db.Float, nullable=True)  # Duration column (minutes)
    rest = db.Column(db.Integer, default=60)
    image = db.Column(db.String(255), nullable=True)  # Single image fallback
    image_urls = db.Column(db.JSON, nullable=True)     # Multi-image array list
    link = db.Column(db.String(255), nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    exercise_type = db.Column(db.String(50), nullable=False, default='Strength')
    # Category-specific default targets. Example: {'Strength': {'sets': 3, 'reps': 10, 'weight': 50, 'rest': 60}}
    categories = db.Column(db.JSON, nullable=True)
    category_targets = db.Column(db.JSON, nullable=True)


class Workout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    exercises = db.relationship(
        'WorkoutExercise', backref='workout', cascade='all, delete-orphan'
    )


class WorkoutExercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(
        db.Integer, db.ForeignKey('workout.id'), nullable=False
    )
    exercise_id = db.Column(
        db.Integer, db.ForeignKey('exercise.id'), nullable=False
    )
    custom_sets = db.Column(db.Integer, nullable=True)
    custom_reps = db.Column(db.Integer, nullable=True)
    custom_duration = db.Column(db.Float, nullable=True)
    custom_rest = db.Column(db.Integer, nullable=True)
    categories = db.Column(db.JSON, nullable=True)
    category_targets = db.Column(db.JSON, nullable=True)
    # One WorkoutExercise row represents one exercise/category pairing.
    category = db.Column(db.String(50), nullable=True)
    order = db.Column(db.Integer, default=0, nullable=False)

    exercise = db.relationship('Exercise')


class WorkoutLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(
        db.Integer, db.ForeignKey('workout.id'), nullable=False
    )
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    workout = db.relationship('Workout')
    sets = db.relationship(
        'SetLog', backref='workout_log', cascade='all, delete-orphan'
    )


class SetLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_log_id = db.Column(
        db.Integer, db.ForeignKey('workout_log.id'), nullable=False
    )
    exercise_id = db.Column(
        db.Integer, db.ForeignKey('exercise.id'), nullable=False
    )
    workout_exercise_id = db.Column(
        db.Integer, db.ForeignKey('workout_exercise.id'), nullable=True
    )
    category = db.Column(db.String(50), nullable=True)
    set_number = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    duration = db.Column(db.Float, nullable=True)
    time_seconds = db.Column(db.Integer, nullable=True)
    distance_meters = db.Column(db.Float, nullable=True)
    rest = db.Column(db.Integer, nullable=True)

    exercise = db.relationship('Exercise')


class ExerciseHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_log_id = db.Column(db.Integer, db.ForeignKey('workout_log.id'), nullable=False)
    workout_exercise_id = db.Column(db.Integer, nullable=True)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)
    category = db.Column(db.String(50), nullable=True)
    set_number = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    duration = db.Column(db.Float, nullable=True)
    time_seconds = db.Column(db.Integer, nullable=True)
    distance_meters = db.Column(db.Float, nullable=True)
    rest = db.Column(db.Integer, nullable=True)
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)

    workout_log = db.relationship('WorkoutLog')
    exercise = db.relationship('Exercise')


class SoundFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AppSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=True)


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
    all_exercises = Exercise.query.order_by(Exercise.order.asc()).all()
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

        new_exercise = Exercise(
            name=name,
            exercise_type=selected_categories[0],
            categories=selected_categories,
            category_targets=category_targets,
            muscles=muscles,
            sets=category_targets[selected_categories[0]]['sets'],
            reps=category_targets[selected_categories[0]]['reps'],
            duration=category_targets[selected_categories[0]]['duration'],
            rest=category_targets[selected_categories[0]]['rest'],
            image=image_list[0] if image_list else None,
            image_urls=image_list if image_list else None,
            link=link,
            instructions=instructions,
        )
        db.session.add(new_exercise)
        db.session.commit()

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
    order_data = data.get('order', [])
    
    # Example logic depending on your ORM (SQLAlchemy, Peewee, etc.)
    for item in order_data:
        exercise_id = item.get('id')
        new_order = item.get('order')
        
        exercise = Exercise.query.get(exercise_id)
        if exercise:
            exercise.order = new_order
            
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Exercises reordered successfully'})

@app.route('/exercise/<int:id>', methods=['GET', 'POST'])
def display_exercise(id):
    exercise = db.session.get(Exercise, id) or abort(404)
    return_workout_id = request.args.get('return_workout_id', '')

    if request.method == 'POST':
        return_workout_id = request.form.get('return_workout_id', '')
        exercise.name = (request.form.get('name') or exercise.name).strip()
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

        exercise.categories = selected_categories
        exercise.category_targets = category_targets
        exercise.exercise_type = selected_categories[0]
        exercise.sets = category_targets[selected_categories[0]]['sets']
        exercise.reps = category_targets[selected_categories[0]]['reps']
        exercise.duration = category_targets[selected_categories[0]]['duration']
        exercise.rest = category_targets[selected_categories[0]]['rest']
        exercise.instructions = request.form.get('instructions', '')
        exercise.link = request.form.get('link', '')
        exercise.muscles = request.form.getlist('muscles')

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
        exercise.image_urls = combined_images if combined_images else None
        exercise.image = combined_images[0] if combined_images else None

        db.session.commit()
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
    exercise = db.session.get(Exercise, exercise_id) or abort(404)
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

    WorkoutExercise.query.filter_by(exercise_id=exercise.id).delete()
    SetLog.query.filter_by(exercise_id=exercise.id).delete()
    ExerciseHistory.query.filter_by(exercise_id=exercise.id).delete()

    db.session.delete(exercise)
    db.session.commit()
    
    flash('Exercise deleted successfully.', 'success')

    if return_workout_id:
        return redirect(url_for('add_exercise', workout_id=return_workout_id))
    return redirect(url_for('exercise_list'))


@app.route('/workouts')
def workout_list():
    workouts = Workout.query.all()
    return render_template('workout_list.html', workouts=workouts)


@app.route('/workout/add', methods=['GET', 'POST'])
def add_workout():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()

        if not title:
            flash('Workout title is required.', 'error')
            return render_template(
                'add_workout.html', title=title, description=description
            )

        workout = Workout(title=title, description=description or None)
        db.session.add(workout)
        db.session.commit()

        return redirect(url_for('add_exercise', workout_id=workout.id))

    return render_template('add_workout.html')


@app.route('/workout/<int:workout_id>')
def view_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    sorted_exercises = sorted(workout.exercises, key=lambda x: x.order)
    return render_template(
        'view_workout.html', workout=workout, sorted_exercises=sorted_exercises
    )


@app.route('/workout/<int:workout_id>/add_exercise', methods=['GET', 'POST'])
def add_exercise(workout_id):
    workout = Workout.query.get_or_404(workout_id)

    if request.method == 'POST':
        # Rebuild the workout's exercise/category rows from the submitted selection.
        # Each selected category gets its own WorkoutExercise row so that the
        # category, targets, rest, history and logging are independent.
        WorkoutExercise.query.filter_by(workout_id=workout.id).delete(synchronize_session=False)

        selected_ids = request.form.getlist('exercise_ids')
        order_index = 0

        for ex_id in selected_ids:
            try:
                ex_id_int = int(ex_id)
            except (TypeError, ValueError):
                continue

            exercise = db.session.get(Exercise, ex_id_int)
            if not exercise:
                continue

            selected_categories = request.form.getlist(f'categories_{ex_id_int}')
            if not selected_categories:
                continue

            for category in selected_categories:
                # Strength/Speed use reps; the other categories use duration.
                # We still retain both fields so the saved workout has complete data.
                target = {
                    'sets': max(1, safe_int(request.form.get(f'sets_{ex_id_int}_{category}'), exercise.sets or 3)),
                    'reps': max(1, safe_int(request.form.get(f'reps_{ex_id_int}_{category}'), exercise.reps or 10)),
                    'duration': max(0.0, safe_float(request.form.get(f'duration_{ex_id_int}_{category}'), exercise.duration or 30)),
                    'weight': max(0.0, safe_float(request.form.get(f'weight_{ex_id_int}_{category}'), 0.0)),
                    'rest': max(0, safe_int(request.form.get(f'rest_{ex_id_int}_{category}'), exercise.rest or 60)),
                }

                we = WorkoutExercise(
                    workout_id=workout.id,
                    exercise_id=ex_id_int,
                    custom_sets=target['sets'],
                    custom_reps=target['reps'],
                    custom_duration=target['duration'],
                    custom_rest=target['rest'],
                    categories=[category],
                    category_targets={category: target},
                    category=category,
                    order=order_index,
                )
                db.session.add(we)
                order_index += 1

        db.session.commit()
        return redirect(url_for('view_workout', workout_id=workout.id))

    all_exercises = Exercise.query.order_by(Exercise.name.asc()).all()
    existing_we = WorkoutExercise.query.filter_by(workout_id=workout.id).order_by(WorkoutExercise.order).all()

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

    category_defaults = {}
    for ex in all_exercises:
        category_defaults[ex.id] = {
            category: {
                'sets': ex.sets or 3,
                'reps': ex.reps or 10,
                'duration': ex.duration or 30,
                'weight': 0,
                'rest': ex.rest or 60,
            }
            for category in VALID_EXERCISE_TYPES
        }
        configured = ex.categories if isinstance(ex.categories, list) else []
        if not configured:
            configured = [ex.exercise_type] if ex.exercise_type in VALID_EXERCISE_TYPES else ['Strength']
        ex.types_list = configured
        stored_targets = ex.category_targets if isinstance(ex.category_targets, dict) else {}
        ex.category_targets = {
            category: stored_targets.get(category, category_defaults[ex.id].get(category, {
                'sets': ex.sets or 3, 'reps': ex.reps or 10, 'duration': ex.duration or 30,
                'weight': 0, 'rest': ex.rest or 60
            })) for category in configured
        }

    return render_template(
        'add_exercise_to_workout.html',
        workout=workout,
        all_exercises=all_exercises,
        existing_map=existing_map,
    )


@app.route('/workout/<int:workout_id>/reorder', methods=['POST'])
def reorder_workout_exercises(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('order'), list):
        return jsonify({'status': 'error', 'message': 'Invalid payload'}), 400

    exercises = WorkoutExercise.query.filter_by(workout_id=workout.id).all()
    exercise_map = {ex.id: ex for ex in exercises}
    submitted_ids = []
    seen_ids = set()

    for item in data['order']:
        if not isinstance(item, dict):
            return jsonify({'status': 'error', 'message': 'Invalid order item'}), 400
        try:
            exercise_id = int(item.get('id'))
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': 'Invalid exercise ID'}), 400
        if exercise_id not in exercise_map or exercise_id in seen_ids:
            return jsonify({'status': 'error', 'message': 'Invalid or duplicate exercise ID'}), 400
        seen_ids.add(exercise_id)
        submitted_ids.append(exercise_id)

    if len(submitted_ids) != len(exercises):
        return jsonify({'status': 'error', 'message': 'Incomplete exercise order'}), 400

    for position, exercise_id in enumerate(submitted_ids):
        exercise_map[exercise_id].order = position

    db.session.commit()
    return jsonify({'status': 'success'})


@app.route('/workout/<int:workout_id>/remove_exercise/<int:we_id>', methods=['POST'])
def remove_exercise_from_workout(workout_id, we_id):
    we = WorkoutExercise.query.filter_by(
        id=we_id, workout_id=workout_id
    ).first_or_404()
    db.session.delete(we)
    db.session.commit()
    flash('Exercise removed from workout.', 'success')
    return redirect(url_for('view_workout', workout_id=workout_id))


@app.route('/workout/<int:workout_id>/delete', methods=['POST'])
def delete_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    db.session.delete(workout)
    db.session.commit()
    flash('Workout deleted successfully.', 'success')
    return redirect(url_for('workout_list'))


@app.route('/workout/<int:workout_id>/start')
def start_workout(workout_id):
    workout = Workout.query.get_or_404(workout_id)
    log = WorkoutLog(workout_id=workout.id, start_time=datetime.utcnow())
    db.session.add(log)
    db.session.commit()
    return redirect(url_for('log_exercise', log_id=log.id))


@app.route('/log/<int:log_id>', methods=['GET', 'POST'])
def log_exercise(log_id):
    log = WorkoutLog.query.get_or_404(log_id)

    if request.method == 'POST':
        data = request.get_json(silent=True) if request.is_json else request.form

        try:
            workout_exercise_id = int(data.get('workout_exercise_id'))
            set_number = int(data.get('set_number'))
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': 'Invalid workout exercise or set number.'}), 400

        we = WorkoutExercise.query.filter_by(
            id=workout_exercise_id, workout_id=log.workout_id
        ).first()
        if not we:
            return jsonify({'status': 'error', 'message': 'Workout exercise/category was not found.'}), 404

        exercise_id = we.exercise_id
        category = we.category or (we.categories[0] if isinstance(we.categories, list) and we.categories else we.exercise.exercise_type)

        reps_val = data.get('reps')
        weight_val = data.get('weight')
        duration_val = data.get('duration')
        time_seconds_val = data.get('time_seconds')
        distance_meters_val = data.get('distance_meters')
        rest_val = data.get('rest')

        set_log = SetLog(
            workout_log_id=log.id,
            exercise_id=exercise_id,
            workout_exercise_id=we.id,
            category=category,
            set_number=set_number,
            reps=safe_int(reps_val) if reps_val is not None and str(reps_val).strip() != '' else None,
            weight=safe_float(weight_val) if weight_val is not None and str(weight_val).strip() != '' else None,
            duration=safe_float(duration_val) if duration_val is not None and str(duration_val).strip() != '' else None,
            time_seconds=safe_int(time_seconds_val) if time_seconds_val is not None and str(time_seconds_val).strip() != '' else None,
            distance_meters=safe_float(distance_meters_val) if distance_meters_val is not None and str(distance_meters_val).strip() != '' else None,
            rest=safe_int(rest_val, we.custom_rest if we.custom_rest is not None else (we.exercise.rest or 60)),
        )
        db.session.add(set_log)
        db.session.commit()

        is_ajax = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')
        if is_ajax:
            return jsonify({'status': 'success', 'set_id': set_log.id}), 200
        return redirect(url_for('log_exercise', log_id=log.id))

    # Build per-workout-exercise display data including history defaults/max values.
    exercise_cards = []
    for item in sorted(log.workout.exercises, key=lambda x: x.order):
        ex = item.exercise
        category = item.category or (item.categories[0] if isinstance(item.categories, list) and item.categories else ex.exercise_type)
        target = {}
        if isinstance(item.category_targets, dict):
            target = item.category_targets.get(category, {})
        if not target:
            target = {
                'sets': item.custom_sets if item.custom_sets is not None else (ex.sets or 3),
                'reps': item.custom_reps if item.custom_reps is not None else (ex.reps or 10),
                'duration': item.custom_duration if item.custom_duration is not None else (ex.duration or 30),
                'weight': 0,
                'rest': item.custom_rest if item.custom_rest is not None else (ex.rest or 60),
            }

        # Only completed prior sessions count as history.
        history_rows = (ExerciseHistory.query
            .join(WorkoutLog, ExerciseHistory.workout_log_id == WorkoutLog.id)
            .filter(
                ExerciseHistory.exercise_id == ex.id,
                ExerciseHistory.category == category,
                WorkoutLog.end_time.isnot(None),
                WorkoutLog.id != log.id,
            )
            .order_by(WorkoutLog.end_time.desc(), ExerciseHistory.set_number.asc())
            .all())

        max_weight = max((h.weight for h in history_rows if h.weight is not None), default=None)
        max_duration = max((h.duration for h in history_rows if h.duration is not None), default=None)

        last_session_id = history_rows[0].workout_log_id if history_rows else None
        last_session_rows = [h for h in history_rows if h.workout_log_id == last_session_id]
        last_session_rows.sort(key=lambda h: h.set_number)

        # Defaults come from the most recent completed session. For each field,
        # use the latest non-empty value recorded in that session. Fall back to
        # the saved workout/category target when the history has no value.
        def last_value(rows, attr, fallback=None):
            for row in reversed(rows):
                value = getattr(row, attr, None)
                if value is not None:
                    return value
            return fallback

        default_reps = last_value(last_session_rows, 'reps', target.get('reps'))
        default_weight = last_value(last_session_rows, 'weight', target.get('weight', 0))
        default_duration = last_value(last_session_rows, 'duration', target.get('duration'))
        default_rest = last_value(last_session_rows, 'rest', target.get('rest', ex.rest or 60))

        current_sets = [s for s in log.sets if s.workout_exercise_id == item.id]
        exercise_cards.append({
            'item': item,
            'exercise': ex,
            'category': category,
            'target': target,
            'history_max_weight': max_weight,
            'history_max_duration': max_duration,
            'last_reps': default_reps,
            'last_weight': default_weight,
            'last_duration': default_duration,
            'last_rest': default_rest,
            'logged_sets': sorted(current_sets, key=lambda s: s.set_number),
        })

    return render_template('log_workout.html', log=log, exercise_cards=exercise_cards)


@app.route('/log/<int:log_id>/finish', methods=['POST'])
def finish_workout(log_id):
    log = WorkoutLog.query.get_or_404(log_id)
    log.end_time = datetime.utcnow()
    log.notes = request.form.get('notes', '')

    # Snapshot completed sets into the exercise history table. This prevents an
    # abandoned/in-progress workout from becoming the user's "last session".
    ExerciseHistory.query.filter_by(workout_log_id=log.id).delete(synchronize_session=False)
    for set_log in log.sets:
        we = db.session.get(WorkoutExercise, set_log.workout_exercise_id) if set_log.workout_exercise_id else None
        category = set_log.category or (we.category if we else None)
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
            logged_at=datetime.utcnow(),
        ))

    db.session.commit()
    return render_template('finished_workout.html', log=log)


@app.route('/progress')
def progress():
    today = date.today()
    year = safe_int(request.args.get('year'), today.year)
    month = safe_int(request.args.get('month'), today.month)
    if not 1 <= month <= 12:
        month, year = today.month, today.year

    sessions = (WorkoutLog.query
                .filter(WorkoutLog.end_time.isnot(None))
                .order_by(WorkoutLog.end_time.desc()).all())

    calendar_data = defaultdict(lambda: {'count': 0, 'types': set()})
    type_counts = {'Strength': 0, 'Power': 0, 'Aerobic': 0}
    workout_dates = set()
    exercise_ids = set()
    logged_sets = 0

    def training_types(session):
        result = set()
        for we in session.workout.exercises:
            category = (we.category or '').strip().lower()
            if category == 'strength':
                result.add('Strength')
            elif category in ('speed', 'alactic atp', 'anaerobic (hit)'):
                result.add('Power')
            elif category == 'aerobic capacity':
                result.add('Aerobic')
        return result

    for session in sessions:
        d = session.end_time.date()
        workout_dates.add(d)
        types = training_types(session)
        calendar_data[d]['count'] += 1
        calendar_data[d]['types'].update(types)
        if d.year == year and d.month == month:
            for t in types:
                type_counts[t] += 1
        logged_sets += len(session.sets)
        exercise_ids.update(s.exercise_id for s in session.sets)

    first_weekday, days_in_month = pycalendar.monthrange(year, month)
    days = [{'empty': True} for _ in range(first_weekday)]
    for n in range(1, days_in_month + 1):
        d = date(year, month, n)
        entry = calendar_data.get(d, {'count': 0, 'types': set()})
        days.append({
            'empty': False,
            'day': n,
            'has_workout': entry['count'] > 0,
            'workout_count': entry['count'],
            'types': {k: k in entry['types'] for k in ('Strength','Power','Aerobic')},
            'is_today': d == today
        })
    while len(days) % 7:
        days.append({'empty': True})

    prev_month, prev_year = month - 1, year
    if prev_month == 0:
        prev_month, prev_year = 12, year - 1
    next_month, next_year = month + 1, year
    if next_month == 13:
        next_month, next_year = 1, year + 1

    completed_weeks = {(d.isocalendar().year, d.isocalendar().week) for d in workout_dates}
    streak = 0
    cursor = today - timedelta(days=today.weekday())
    while (cursor.isocalendar().year, cursor.isocalendar().week) in completed_weeks:
        streak += 1
        cursor -= timedelta(days=7)

    for session in sessions:
        grouped = {}
        for s in session.sets:
            key = (s.exercise_id, s.category or '')
            item = grouped.setdefault(key, {
                'name': s.exercise.name, 'category': s.category, 'sets': 0,
                'weight': None, 'reps': None, 'duration': None,
                'time_seconds': None, 'distance_meters': None
            })
            item['sets'] += 1
            if s.weight is not None:
                item['weight'] = s.weight if item['weight'] is None else max(item['weight'], s.weight)
            if s.reps is not None:
                item['reps'] = s.reps
            if s.duration is not None:
                item['duration'] = s.duration
            if s.time_seconds is not None:
                item['time_seconds'] = s.time_seconds
            if s.distance_meters is not None:
                item['distance_meters'] = s.distance_meters
        session.summary = list(grouped.values())

    max_type = max(type_counts.values(), default=0)
    type_percent = {k: round(v / max_type * 100) if max_type else 0 for k, v in type_counts.items()}

    calendar_obj = {
        'year': year, 'month': month, 'month_name': pycalendar.month_name[month],
        'days': days, 'prev_month': prev_month, 'prev_year': prev_year,
        'next_month': next_month, 'next_year': next_year
    }
    stats = {
        'total_workouts': len(sessions),
        'this_month': sum(1 for d in workout_dates if d.year == year and d.month == month),
        'current_streak': streak,
        'logged_sets': logged_sets,
        'active_exercises': len(exercise_ids)
    }

    return render_template(
        'progress.html',
        sessions=sessions,
        calendar=calendar_obj,
        stats=stats,
        type_stats=type_counts,
        type_percent=type_percent
    )



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


# Migration Helper
def run_migrations():
    inspector = inspect(db.engine)
    
    if 'exercise' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('exercise')]
        if 'exercise_type' not in columns:
            db.session.execute(text("ALTER TABLE exercise ADD COLUMN exercise_type VARCHAR(50) DEFAULT 'Strength' NOT NULL"))
        if 'duration' not in columns:
            db.session.execute(text("ALTER TABLE exercise ADD COLUMN duration FLOAT"))
        if 'image_urls' not in columns:
            db.session.execute(text("ALTER TABLE exercise ADD COLUMN image_urls JSON"))
        if 'categories' not in columns:
            db.session.execute(text("ALTER TABLE exercise ADD COLUMN categories JSON"))
        if 'category_targets' not in columns:
            db.session.execute(text("ALTER TABLE exercise ADD COLUMN category_targets JSON"))
        db.session.commit()

    if 'workout_exercise' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('workout_exercise')]
        if 'custom_duration' not in columns:
            db.session.execute(text("ALTER TABLE workout_exercise ADD COLUMN custom_duration FLOAT"))
        if 'categories' not in columns:
            db.session.execute(text("ALTER TABLE workout_exercise ADD COLUMN categories JSON"))
        if 'category_targets' not in columns:
            db.session.execute(text("ALTER TABLE workout_exercise ADD COLUMN category_targets JSON"))
        if 'category' not in columns:
            db.session.execute(text("ALTER TABLE workout_exercise ADD COLUMN category VARCHAR(50)"))
        db.session.commit()

    if 'set_log' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('set_log')]
        if 'duration' not in columns:
            db.session.execute(text("ALTER TABLE set_log ADD COLUMN duration FLOAT"))
        if 'time_seconds' not in columns:
            db.session.execute(text("ALTER TABLE set_log ADD COLUMN time_seconds INTEGER"))
        if 'distance_meters' not in columns:
            db.session.execute(text("ALTER TABLE set_log ADD COLUMN distance_meters FLOAT"))
        if 'workout_exercise_id' not in columns:
            db.session.execute(text("ALTER TABLE set_log ADD COLUMN workout_exercise_id INTEGER"))
        if 'category' not in columns:
            db.session.execute(text("ALTER TABLE set_log ADD COLUMN category VARCHAR(50)"))
        if 'rest' not in columns:
            db.session.execute(text("ALTER TABLE set_log ADD COLUMN rest INTEGER"))
        db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        run_migrations()
    app.run(host='0.0.0.0', port=52889, debug=True)