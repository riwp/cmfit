from datetime import datetime, date

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

db = SQLAlchemy()


class Exercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    order = db.Column('order', db.Integer, default=0, nullable=False)
    muscles = db.Column(db.JSON, nullable=True)
    sets = db.Column(db.Integer, default=3)
    reps = db.Column(db.Integer, default=10)
    duration = db.Column(db.Float, nullable=True)
    rest = db.Column(db.Integer, default=60)
    image = db.Column(db.String(255), nullable=True)
    image_urls = db.Column(db.JSON, nullable=True)
    link = db.Column(db.String(255), nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    exercise_type = db.Column(db.String(50), nullable=False, default='Strength')
    categories = db.Column(db.JSON, nullable=True)
    category_targets = db.Column(db.JSON, nullable=True)


class Workout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    order = db.Column('order', db.Integer, default=0, nullable=False)
    exercises = db.relationship('WorkoutExercise', backref='workout', cascade='all, delete-orphan')


class WorkoutExercise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)
    custom_sets = db.Column(db.Integer, nullable=True)
    custom_reps = db.Column(db.Integer, nullable=True)
    custom_duration = db.Column(db.Float, nullable=True)
    custom_rest = db.Column(db.Integer, nullable=True)
    categories = db.Column(db.JSON, nullable=True)
    category_targets = db.Column(db.JSON, nullable=True)
    category = db.Column(db.String(50), nullable=True)
    order = db.Column(db.Integer, default=0, nullable=False)
    exercise = db.relationship('Exercise')


class WorkoutLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey('workout.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    workout = db.relationship('Workout')
    sets = db.relationship('SetLog', backref='workout_log', cascade='all, delete-orphan')


class SetLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workout_log_id = db.Column(db.Integer, db.ForeignKey('workout_log.id'), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey('exercise.id'), nullable=False)
    workout_exercise_id = db.Column(db.Integer, db.ForeignKey('workout_exercise.id'), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    set_number = db.Column(db.Integer, nullable=False)
    reps = db.Column(db.Integer, nullable=True)
    weight = db.Column(db.Float, nullable=True)
    duration = db.Column(db.Float, nullable=True)
    time_seconds = db.Column(db.Integer, nullable=True)
    distance_meters = db.Column(db.Float, nullable=True)
    rest = db.Column(db.Integer, nullable=True)
    rest_start_heart_rate = db.Column(db.Integer, nullable=True)
    rest_end_heart_rate = db.Column(db.Integer, nullable=True)
    rest_seconds = db.Column(db.Integer, nullable=True)
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
    rest_start_heart_rate = db.Column(db.Integer, nullable=True)
    rest_end_heart_rate = db.Column(db.Integer, nullable=True)
    rest_seconds = db.Column(db.Integer, nullable=True)
    logged_at = db.Column(db.DateTime, default=datetime.utcnow)
    workout_log = db.relationship('WorkoutLog')
    exercise = db.relationship('Exercise')


class FitnessTestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_key = db.Column(db.String(80), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(30), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    tested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    details = db.Column(db.JSON, nullable=True)


class SoundFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AppSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=True)


class TrainingPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False, default='12-Month Training Plan')
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    months = db.relationship(
        'TrainingPlanMonth', backref='plan', cascade='all, delete-orphan',
        order_by='TrainingPlanMonth.month_number'
    )


class TrainingPlanMonth(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('training_plan.id'), nullable=False)
    month_number = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    phase = db.Column(db.String(80), nullable=True)
    focus = db.Column(db.String(160), nullable=True)
    sessions_per_week = db.Column(db.Float, default=3)
    category_mix = db.Column(db.JSON, nullable=False, default=dict)
    notes = db.Column(db.Text, nullable=True)


def run_migrations(app):
    """Bring an existing SQLite database up to the schema expected by CMFit."""
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()

    migrations = {
        'exercise': {
            'exercise_type': "ALTER TABLE exercise ADD COLUMN exercise_type VARCHAR(50) DEFAULT 'Strength' NOT NULL",
            'duration': "ALTER TABLE exercise ADD COLUMN duration FLOAT",
            'image_urls': "ALTER TABLE exercise ADD COLUMN image_urls JSON",
            'categories': "ALTER TABLE exercise ADD COLUMN categories JSON",
            'category_targets': "ALTER TABLE exercise ADD COLUMN category_targets JSON",
        },
        'workout': {
            'order': 'ALTER TABLE workout ADD COLUMN "order" INTEGER DEFAULT 0 NOT NULL',
        },
        'workout_exercise': {
            'custom_duration': "ALTER TABLE workout_exercise ADD COLUMN custom_duration FLOAT",
            'categories': "ALTER TABLE workout_exercise ADD COLUMN categories JSON",
            'category_targets': "ALTER TABLE workout_exercise ADD COLUMN category_targets JSON",
            'category': "ALTER TABLE workout_exercise ADD COLUMN category VARCHAR(50)",
        },
        'set_log': {
            'duration': "ALTER TABLE set_log ADD COLUMN duration FLOAT",
            'time_seconds': "ALTER TABLE set_log ADD COLUMN time_seconds INTEGER",
            'distance_meters': "ALTER TABLE set_log ADD COLUMN distance_meters FLOAT",
            'workout_exercise_id': "ALTER TABLE set_log ADD COLUMN workout_exercise_id INTEGER",
            'category': "ALTER TABLE set_log ADD COLUMN category VARCHAR(50)",
            'rest': "ALTER TABLE set_log ADD COLUMN rest INTEGER",
            'rest_start_heart_rate': "ALTER TABLE set_log ADD COLUMN rest_start_heart_rate INTEGER",
            'rest_end_heart_rate': "ALTER TABLE set_log ADD COLUMN rest_end_heart_rate INTEGER",
            'rest_seconds': "ALTER TABLE set_log ADD COLUMN rest_seconds INTEGER",
        },
        'exercise_history': {
            'rest_start_heart_rate': "ALTER TABLE exercise_history ADD COLUMN rest_start_heart_rate INTEGER",
            'rest_end_heart_rate': "ALTER TABLE exercise_history ADD COLUMN rest_end_heart_rate INTEGER",
            'rest_seconds': "ALTER TABLE exercise_history ADD COLUMN rest_seconds INTEGER",
        },
    }

    try:
        workout_order_added = False

        for table_name, column_migrations in migrations.items():
            if table_name not in table_names:
                continue

            columns = {column['name'] for column in inspect(db.engine).get_columns(table_name)}

            for column_name, statement in column_migrations.items():
                if column_name not in columns:
                    app.logger.info('Adding missing database column %s.%s', table_name, column_name)
                    db.session.execute(text(statement))
                    db.session.commit()
                    columns.add(column_name)

                    if table_name == 'workout' and column_name == 'order':
                        workout_order_added = True

        # Existing databases had no explicit workout order. On the one migration
        # that adds the column, preserve the prior legacy order (SQLite row/id
        # order) by assigning sequential positions 0..N-1.
        if workout_order_added:
            existing_workouts = Workout.query.order_by(Workout.id.asc()).all()
            for position, workout in enumerate(existing_workouts):
                workout.order = position
            db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception('Database migration failed')
        raise
