import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# 1. Load environment variables from .env file
load_dotenv()

# 2. Get absolute path to project root (~/cmfit)
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# 3. Retrieve SECRET_KEY from environment (fallback for quick testing if .env isn't present)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key-change-in-prod')

# 4. Lock SQLite database location to absolute path (~/cmfit/data/cmfit.db)
db_dir = os.path.join(basedir, 'data')
os.makedirs(db_dir, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(db_dir, 'cmfit.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'uploads')

db = SQLAlchemy(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# Models
class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    muscles = db.Column(db.JSON, nullable=True)
    sets = db.Column(db.Integer, default=3)
    reps = db.Column(db.Integer, default=10)
    rest = db.Column(db.Integer, default=60)
    image = db.Column(db.String(255), nullable=True)
    link = db.Column(db.String(255), nullable=True)
    instructions = db.Column(db.Text, nullable=True)


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
    reps = db.Column(db.Integer, nullable=False)
    weight = db.Column(db.Float, nullable=False)

    exercise = db.relationship('Exercise')


# Helpers
def save_image(file):
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return filename
    return None


# Routes
@app.route('/')
def index():
    return redirect(url_for('workout_list'))


# Exercise Library Routes
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
        muscles = request.form.getlist('muscles')
        sets = int(request.form.get('sets', 3))
        reps = int(request.form.get('reps', 10))
        rest = int(request.form.get('rest', 60))
        link = request.form.get('link')
        instructions = request.form.get('instructions')

        image_filename = None
        if 'image' in request.files:
            file = request.files['image']
            image_filename = save_image(file)

        new_exercise = Exercise(
            name=name,
            muscles=muscles,
            sets=sets,
            reps=reps,
            rest=rest,
            image=image_filename,
            link=link,
            instructions=instructions,
        )
        db.session.add(new_exercise)
        db.session.commit()

        if return_workout_id:
            return redirect(
                url_for('add_exercise', workout_id=return_workout_id)
            )
        return redirect(url_for('exercise_list'))

    muscle_groups = [
        'Chest',
        'Back',
        'Shoulders',
        'Biceps',
        'Triceps',
        'Legs',
        'Abs',
        'Cardio',
    ]
    return render_template(
        'add_new_exercise.html',
        muscle_groups=muscle_groups,
        return_workout_id=return_workout_id,
    )


@app.route('/exercise/<int:id>', methods=['GET', 'POST'])
def display_exercise(id):
    exercise = Exercise.query.get_or_404(id)

    if request.method == 'POST':
        exercise.name = request.form.get('name', exercise.name)
        exercise.sets = int(request.form.get('sets', exercise.sets))
        exercise.reps = int(request.form.get('reps', exercise.reps))
        exercise.rest = int(request.form.get('rest', exercise.rest))
        exercise.instructions = request.form.get('instructions', '')
        exercise.link = request.form.get('link', '')
        exercise.muscles = request.form.getlist('muscles')

        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                image_filename = save_image(file)
                if image_filename:
                    exercise.image = image_filename

        db.session.commit()

        next_url = request.form.get('next_url')
        if next_url and next_url != request.url:
            return redirect(next_url)
        return redirect(url_for('exercise_list'))

    next_url = request.referrer or url_for('exercise_list')

    muscle_groups = [
        'Chest',
        'Back',
        'Shoulders',
        'Biceps',
        'Triceps',
        'Legs',
        'Abs',
        'Cardio',
    ]
    return render_template(
        'display_exercise.html',
        exercise=exercise,
        muscle_groups=muscle_groups,
        next_url=next_url,
    )


# Workout Routes
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
            rest = request.form.get(f'rest_{ex_id_int}')

            we = WorkoutExercise(
                workout_id=workout.id,
                exercise_id=ex_id_int,
                custom_sets=int(sets) if sets else None,
                custom_reps=int(reps) if reps else None,
                custom_rest=int(rest) if rest else None,
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


# Active Workout Logging Routes
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
        exercise_id = int(request.form.get('exercise_id'))
        set_number = int(request.form.get('set_number'))
        reps = int(request.form.get('reps'))
        weight = float(request.form.get('weight'))

        set_log = SetLog(
            workout_log_id=log.id,
            exercise_id=exercise_id,
            set_number=set_number,
            reps=reps,
            weight=weight,
        )
        db.session.add(set_log)
        db.session.commit()
        return redirect(url_for('log_exercise', log_id=log.id))

    return render_template('log_workout.html', log=log)


@app.route('/log/<int:log_id>/finish', methods=['POST'])
def finish_workout(log_id):
    log = WorkoutLog.query.get_or_404(log_id)
    log.end_time = datetime.utcnow()
    log.notes = request.form.get('notes', '')
    db.session.commit()

    return render_template('finished_workout.html', log=log)


# Progress Route
@app.route('/progress')
def progress():
    sessions = (
        WorkoutLog.query.filter(WorkoutLog.end_time.isnot(None))
        .order_by(WorkoutLog.end_time.desc())
        .all()
    )
    return render_template('progress.html', sessions=sessions)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=52889, debug=True)