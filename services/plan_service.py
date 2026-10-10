"""Annual focus and reusable weekly schedules; legacy annual plans stay intact."""
from datetime import datetime
from models import db, AnnualMonthFocus, WeeklyPlan, WeeklyPlanWorkout, Workout

FOCUSES = ('Aerobic', 'Strength', 'Speed', 'HIT')
DAYS = ('Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat')
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def validate_year(value):
    try:
        year = int(value)
    except (ValueError, TypeError):
        raise ValueError('Choose a valid year.')
    if not 1 <= year <= 9999:
        raise ValueError('Choose a year between 1 and 9999.')
    return year


def annual_focus(year):
    return {row.month: row.focus for row in AnnualMonthFocus.query.filter_by(year=year).all()}


def save_annual(year, form):
    year = validate_year(year)
    values = {month: form.get(f'focus_{month}', '') for month in range(1, 13)}
    if any(value and value not in FOCUSES for value in values.values()):
        raise ValueError('Choose Aerobic, Strength, Speed, or HIT for each month.')
    existing = {row.month: row for row in AnnualMonthFocus.query.filter_by(year=year).all()}
    for month, value in values.items():
        row = existing.get(month)
        if not value:
            if row:
                db.session.delete(row)
        elif row:
            row.focus = value
        else:
            db.session.add(AnnualMonthFocus(year=year, month=month, focus=value))
    db.session.commit()


def list_weekly():
    return WeeklyPlan.query.order_by(WeeklyPlan.updated_at.desc(), WeeklyPlan.id.desc()).all()


def save_weekly(form, plan=None):
    name = (form.get('name') or '').strip()
    if not name or len(name) > 120:
        raise ValueError('Enter a plan name of up to 120 characters.')
    selections = []
    available = {row.id for row in Workout.query.all()}
    for day in range(7):
        day_values = form.getlist(f'workouts_{day}')
        if 'rest' in day_values:
            if any(value != 'rest' for value in day_values):
                raise ValueError(f'{DAYS[day]}: choose Rest Day or workouts, not both.')
            continue
        for position, raw_id in enumerate(day_values):
            try:
                workout_id = int(raw_id)
            except (ValueError, TypeError):
                raise ValueError('Choose an available workout.')
            if workout_id not in available:
                raise ValueError('A selected workout is no longer available. Choose another workout.')
            selections.append((day, position, workout_id))
    if not selections:
        raise ValueError('Add at least one workout to your weekly plan.')
    if plan is None:
        plan = WeeklyPlan()
        db.session.add(plan)
    plan.name = name
    plan.description = (form.get('description') or '').strip()
    plan.updated_at = datetime.utcnow()
    plan.assignments[:] = [WeeklyPlanWorkout(day=day, position=position, workout_id=workout_id)
                           for day, position, workout_id in selections]
    db.session.commit()
    return plan
