"""Saved Sunday weeks with immutable planned workout snapshots."""
from datetime import date, timedelta, datetime
from models import db, WeekActual, WeeklyPlan, Workout


def sunday(value=None):
    try:
        day = date.fromisoformat(value) if value else date.today()
    except (ValueError, TypeError):
        raise ValueError('Choose a valid Sunday date.')
    if value and day.weekday() != 6:
        raise ValueError('Choose a Sunday for the week start.')
    return day - timedelta(days=(day.weekday() + 1) % 7)


def select_plan(row, plan):
    row.plan_id = plan.id
    row.plan_name = plan.name
    row.planned = [dict(day=item.day, title=item.workout.title, workout_id=item.workout_id)
                   for item in plan.assignments if item.workout]
    row.actuals = [dict(status='pending', workout_id=None) for item in row.planned]


def load_week(week_start):
    row = WeekActual.query.filter_by(week_start=week_start).first()
    if row:
        return row
    latest = WeekActual.query.order_by(WeekActual.updated_at.desc(), WeekActual.id.desc()).first()
    plan = db.session.get(WeeklyPlan, latest.plan_id) if latest and latest.plan_id else None
    plan = plan or WeeklyPlan.query.order_by(WeeklyPlan.updated_at.desc(), WeeklyPlan.id.desc()).first()
    row = WeekActual(week_start=week_start, planned=[], actuals=[], notes='')
    if plan:
        select_plan(row, plan)
    db.session.add(row)
    db.session.commit()
    return row


def save_progress(row, form):
    actuals = []
    available = {workout.id for workout in Workout.query.all()}
    for index, item in enumerate(row.planned):
        status = form.get(f'status_{index}', 'pending')
        progress = form.get(f'progress_{index}')
        replacement_value = form.get(f'replacement_{index}', '')
        if progress is not None:
            if progress.startswith('workout_'):
                status = 'changed'
                replacement_value = progress[len('workout_'):]
            else:
                status = progress
        if status not in {'pending', 'complete', 'changed', 'skipped'}:
            raise ValueError('Choose a valid workout status.')
        replacement = None
        if status == 'changed':
            try:
                replacement = int(replacement_value)
            except (ValueError, TypeError):
                raise ValueError('Choose a replacement workout for each changed workout.')
            if replacement not in available:
                raise ValueError('Choose an available replacement workout.')
        actuals.append(dict(status=status, workout_id=replacement))
    row.actuals = actuals
    row.notes = form.get('notes', '')
    row.updated_at = datetime.utcnow()
    db.session.commit()
