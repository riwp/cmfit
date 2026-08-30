import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.utils import secure_filename

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
    set_number = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    duration = db.Column(db.Float, nullable=True)
    time_seconds = db.Column(db.Integer, nullable=True)
    distance_meters = db.Column(db.Float, nullable=True)

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
        
        # Ensure distinct filenames if duplicates are uploaded
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(filepath):
            filename = f"{base}_{counter}{ext}"
            filepath = os.path.join(app.config['SOUND_FOLDER'], filename)
            counter += 1

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
    log_set_file = get_file('sound_log_set_file_id')
    notice_file = get_file('sound_notice_file_id')
    rest_end_file = get_file('sound_rest_end_file_id')
    end_file = get_file('sound_end_file_id')

    return {
        'start_enabled': settings.get('sound_start_enabled', 'false') == 'true',
        'start_url': url_for('static', filename=f'sounds/{start_file.filename}') if start_file else None,
        'start_file_id': safe_int(settings.get('sound_start_file_id'), None),
        
        'log_set_enabled': settings.get('sound_log_set_enabled', 'false') == 'true',
        'log_set_url': url_for('static', filename=f'sounds/{log_set_file.filename}') if log_set_file else None,
        'log_set_file_id': safe_int(settings.get('sound_log_set_file_id'), None),

        'notice_enabled': settings.get('sound_notice_enabled', 'false') == 'true',
        'notice_url': url_for('static', filename=f'sounds/{notice_file.filename}') if notice_file else None,
        'notice_file_id': safe_int(settings.get('sound_notice_file_id'), None),
        'notice_seconds': safe_int(settings.get('sound_notice_seconds'), 10),

        'rest_end_enabled': settings.get('sound_rest_end_enabled', 'false') == 'true',
        'rest_end_url': url_for('static', filename=f'sounds/{rest_end_file.filename}') if rest_end_file else None,
        'rest_end_file_id': safe_int(settings.get('sound_rest_end_file_id'), None),

        'end_enabled': settings.get('sound_end_enabled', 'false') == 'true',
        'end_url': url_for('static', filename=f'sounds/{end_file.filename}') if end_file else None,
        'end_file_id': safe_int(settings.get('sound_end_file_id'), None),
    }


def set_app_setting(key, value):
    setting = AppSetting.query.filter_by(key=key).first()
    if not setting:
        setting = AppSetting(key=key, value=str(value) if value is not None else '')
        db.session.add(setting)
    else:
        setting.value = str(value) if value is not None else ''


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
    all_exercises = Exercise.query.order_by(Exercise.name.asc()).all()
    return render_template('exercise_list.html', all_exercises=all_exercises)


@app.route('/exercise/new', methods=['GET', 'POST'])
def add_new_exercise():
    return_workout_id = request.args.get('return_workout_id', '')

    if request.method == 'POST':
        return_workout_id = request.form.get('return_workout_id', '')

        name = request.form.get('name')
        exercise_type = request.form.get('exercise_type', 'Strength')
        if exercise_type not in VALID_EXERCISE_TYPES:
            exercise_type = 'Strength'

        muscles = request.form.getlist('muscles')
        sets = safe_int(request.form.get('sets'), 3)
        reps = safe_int(request.form.get('reps'), 10)
        duration = safe_float(request.form.get('duration'), 0.0)
        rest = safe_int(request.form.get('rest'), 60)
        link = request.form.get('link')
        instructions = request.form.get('instructions')

        uploaded_files = request.files.getlist('images') or request.files.getlist('image')
        image_list = save_multiple_images(uploaded_files)
        primary_image = image_list[0] if image_list else None

        new_exercise = Exercise(
            name=name,
            exercise_type=exercise_type,
            muscles=muscles,
            sets=sets,
            reps=reps,
            duration=duration,
            rest=rest,
            image=primary_image,
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
    return render_template(
        'add_new_exercise.html',
        muscle_groups=muscle_groups,
        valid_exercise_types=VALID_EXERCISE_TYPES,
        return_workout_id=return_workout_id,
    )


@app.route('/exercise/<int:id>', methods=['GET', 'POST'])
def display_exercise(id):
    exercise = db.session.get(Exercise, id) or Flask.abort(404)
    return_workout_id = request.args.get('return_workout_id', '')

    if request.method == 'POST':
        return_workout_id = request.form.get('return_workout_id', '')
        exercise.name = request.form.get('name', exercise.name)
        
        req_type = request.form.get('exercise_type')
        if req_type in VALID_EXERCISE_TYPES:
            exercise.exercise_type = req_type

        exercise.sets = safe_int(request.form.get('sets'), exercise.sets)
        exercise.reps = safe_int(request.form.get('reps'), exercise.reps)
        exercise.duration = safe_float(request.form.get('duration'), exercise.duration or 0.0)
        exercise.rest = safe_int(request.form.get('rest'), exercise.rest)
        exercise.instructions = request.form.get('instructions', '')
        exercise.link = request.form.get('link', '')
        exercise.muscles = request.form.getlist('muscles')

        if isinstance(exercise.image_urls, list):
            existing_images = list(exercise.image_urls)
        elif exercise.image:
            existing_images = [exercise.image]
        else:
            existing_images = []

        delete_list = request.form.getlist('delete_images')
        for img_to_delete in delete_list:
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
    return render_template(
        'add_new_exercise.html',
        exercise=exercise,
        muscle_groups=muscle_groups,
        valid_exercise_types=VALID_EXERCISE_TYPES,
        return_workout_id=return_workout_id
    )


@app.route('/exercise/<int:exercise_id>/delete', methods=['POST'])
def delete_exercise(exercise_id):
    exercise = db.session.get(Exercise, exercise_id) or Flask.abort(404)
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
        WorkoutExercise.query.filter_by(workout_id=workout.id).delete()

        selected_ids = request.form.getlist('exercise_ids')
        for idx, ex_id in enumerate(selected_ids):
            ex_id_int = int(ex_id)
            sets = request.form.get(f'sets_{ex_id_int}')
            reps = request.form.get(f'reps_{ex_id_int}')
            duration = request.form.get(f'duration_{ex_id_int}')
            rest = request.form.get(f'rest_{ex_id_int}')

            we = WorkoutExercise(
                workout_id=workout.id,
                exercise_id=ex_id_int,
                custom_sets=safe_int(sets) if sets else None,
                custom_reps=safe_int(reps) if reps else None,
                custom_duration=safe_float(duration) if duration else None,
                custom_rest=safe_int(rest) if rest else None,
                order=idx,
            )
            db.session.add(we)

        db.session.commit()
        return redirect(url_for('view_workout', workout_id=workout.id))

    all_exercises = Exercise.query.order_by(Exercise.name.asc()).all()
    existing_we = WorkoutExercise.query.filter_by(
        workout_id=workout.id
    ).all()
    existing_map = {
        we.exercise_id: {
            'sets': we.custom_sets,
            'reps': we.custom_reps,
            'duration': we.custom_duration,
            'rest': we.custom_rest,
        }
        for we in existing_we
    }

    return render_template(
        'add_exercise_to_workout.html',
        workout=workout,
        all_exercises=all_exercises,
        existing_map=existing_map,
    )


@app.route('/workout/<int:workout_id>/reorder', methods=['POST'])
def reorder_workout_exercises(workout_id):
    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'status': 'error', 'message': 'Invalid payload'}), 400

    order_map = {item['id']: item['order'] for item in data['order']}
    exercises = WorkoutExercise.query.filter_by(workout_id=workout_id).all()

    for ex in exercises:
        if ex.id in order_map:
            ex.order = order_map[ex.id]

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

    # ---------------------------------------------------------
    # POST METHOD: Save set log
    # ---------------------------------------------------------
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form

        exercise_id = int(data.get('exercise_id'))
        set_number = int(data.get('set_number'))

        reps_val = data.get('reps')
        weight_val = data.get('weight')
        duration_val = data.get('duration')
        time_seconds_val = data.get('time_seconds')
        distance_meters_val = data.get('distance_meters')

        set_log = SetLog(
            workout_log_id=log.id,
            exercise_id=exercise_id,
            set_number=set_number,
            reps=safe_int(reps_val) if reps_val is not None and str(reps_val).strip() != '' else None,
            weight=safe_float(weight_val) if weight_val is not None and str(weight_val).strip() != '' else None,
            duration=safe_float(duration_val) if duration_val is not None and str(duration_val).strip() != '' else None,
            time_seconds=safe_int(time_seconds_val) if time_seconds_val is not None and str(time_seconds_val).strip() != '' else None,
            distance_meters=safe_float(distance_meters_val) if distance_meters_val is not None and str(distance_meters_val).strip() != '' else None,
        )
        db.session.add(set_log)
        db.session.commit()

        is_ajax = (
            request.is_json
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Accept', '')
        )

        if is_ajax:
            return jsonify({'status': 'success', 'set_id': set_log.id}), 200

        return redirect(url_for('log_exercise', log_id=log.id))

    # ---------------------------------------------------------
    # GET METHOD: Query history for exercises & render template
    # ---------------------------------------------------------
    exercise_history = {}

    for item in log.workout.exercises:
        ex_id = item.exercise_id

        # 1. All-time max weight logged for this exercise
        max_set = db.session.query(db.func.max(SetLog.weight)).filter(
            SetLog.exercise_id == ex_id,
            SetLog.weight.isnot(None)
        ).scalar()

        # 2. Find the most recent prior log (excluding current active log)
        last_log = WorkoutLog.query.join(SetLog).filter(
            SetLog.exercise_id == ex_id,
            WorkoutLog.id != log_id
        ).order_by(WorkoutLog.start_time.desc()).first()

        last_weight = None
        if last_log:
            # Last logged set from that most recent log
            last_set = SetLog.query.filter_by(
                workout_log_id=last_log.id,
                exercise_id=ex_id
            ).order_by(SetLog.set_number.desc()).first()

            if last_set and last_set.weight is not None:
                last_weight = last_set.weight

        exercise_history[ex_id] = {
            'max_weight': max_set or '-',
            'last_weight': last_weight if last_weight is not None else '-'
        }

    return render_template(
        'log_workout.html',
        log=log,
        exercise_history=exercise_history
    )


@app.route('/log/<int:log_id>/finish', methods=['POST'])
def finish_workout(log_id):
    log = WorkoutLog.query.get_or_404(log_id)
    log.end_time = datetime.utcnow()
    log.notes = request.form.get('notes', '')
    db.session.commit()

    return render_template('finished_workout.html', log=log)


@app.route('/progress')
def progress():
    sessions = (
        WorkoutLog.query.filter(WorkoutLog.end_time.isnot(None))
        .order_by(WorkoutLog.end_time.desc())
        .all()
    )
    return render_template('progress.html', sessions=sessions)


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        action = request.form.get('action')

        # Upload sound action
        if action == 'upload_sound':
            sound_name = request.form.get('sound_name', '').strip()
            file = request.files.get('sound_file')

            if not sound_name or not file or file.filename == '':
                flash('Please provide both a label and a valid audio file.', 'error')
            else:
                filename = save_sound(file)
                if filename:
                    sf = SoundFile(name=sound_name, filename=filename)
                    db.session.add(sf)
                    db.session.commit()
                    flash(f'Sound "{sound_name}" uploaded successfully.', 'success')
                else:
                    flash('Error saving audio file.', 'error')
            return redirect(url_for('admin'))

        # Save sound settings action
        elif action == 'save_sound_settings':
            set_app_setting('sound_start_enabled', 'true' if '1' in request.form.getlist('start_enabled') else 'false')
            set_app_setting('sound_start_file_id', request.form.get('start_file_id') or '')

            set_app_setting('sound_log_set_enabled', 'true' if '1' in request.form.getlist('log_set_enabled') else 'false')
            set_app_setting('sound_log_set_file_id', request.form.get('log_set_file_id') or '')

            set_app_setting('sound_notice_enabled', 'true' if '1' in request.form.getlist('notice_enabled') else 'false')
            set_app_setting('sound_notice_file_id', request.form.get('notice_file_id') or '')
            set_app_setting('sound_notice_seconds', request.form.get('notice_seconds', '10'))

            set_app_setting('sound_rest_end_enabled', 'true' if '1' in request.form.getlist('rest_end_enabled') else 'false')
            set_app_setting('sound_rest_end_file_id', request.form.get('rest_end_file_id') or '')

            set_app_setting('sound_end_enabled', 'true' if '1' in request.form.getlist('end_enabled') else 'false')
            set_app_setting('sound_end_file_id', request.form.get('end_file_id') or '')

            db.session.commit()
            flash('Sound preferences updated successfully.', 'success')
            return redirect(url_for('admin'))

    settings = get_sound_settings()
    sounds = SoundFile.query.order_by(SoundFile.name.asc()).all()
    return render_template('admin.html', settings=settings, sounds=sounds)


@app.route('/admin/sound/<int:sound_id>/delete', methods=['POST'])
@app.route('/admin/delete-sound/<int:sound_id>', methods=['POST'])
def delete_sound(sound_id):
    sf = SoundFile.query.get_or_404(sound_id)

    # Clean up referenced setting IDs before deleting
    for setting_key in [
        'sound_start_file_id',
        'sound_log_set_file_id',
        'sound_notice_file_id',
        'sound_rest_end_file_id',
        'sound_end_file_id'
    ]:
        s = AppSetting.query.filter_by(key=setting_key).first()
        if s and s.value == str(sf.id):
            s.value = ''

    try:
        os.remove(os.path.join(app.config['SOUND_FOLDER'], sf.filename))
    except OSError:
        pass

    db.session.delete(sf)
    db.session.commit()
    flash(f'Sound "{sf.name}" deleted successfully.', 'success')
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
        db.session.commit()

    if 'workout_exercise' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('workout_exercise')]
        if 'custom_duration' not in columns:
            db.session.execute(text("ALTER TABLE workout_exercise ADD COLUMN custom_duration FLOAT"))
        db.session.commit()

    if 'set_log' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('set_log')]
        if 'duration' not in columns:
            db.session.execute(text("ALTER TABLE set_log ADD COLUMN duration FLOAT"))
        if 'time_seconds' not in columns:
            db.session.execute(text("ALTER TABLE set_log ADD COLUMN time_seconds INTEGER"))
        if 'distance_meters' not in columns:
            db.session.execute(text("ALTER TABLE set_log ADD COLUMN distance_meters FLOAT"))
        db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        run_migrations()
    app.run(host='0.0.0.0', port=52889, debug=True)