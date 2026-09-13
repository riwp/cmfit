import calendar as pycalendar
from collections import defaultdict
from datetime import date, datetime, timedelta

from models import db, FitnessTestResult, Workout, WorkoutLog
from .serializers import fitness_test_to_dict


FITNESS_TESTS = [
    {'key': 'horizontal_long_jump', 'name': 'Horizontal Long Jump', 'category': 'Power', 'unit': 'in', 'input_label': 'Distance', 'best_direction': 'higher', 'attempts': 3, 'description': 'Best of 3 attempts.'},
    {'key': 'vertical_jump', 'name': 'Vertical Jump', 'category': 'Power', 'unit': 'in', 'input_label': 'Height', 'best_direction': 'higher', 'attempts': 3, 'description': 'Best of 3 attempts.'},
    {'key': 'medicine_ball_throw', 'name': 'Medicine Ball Throw', 'category': 'Power', 'unit': 'ft', 'input_label': 'Distance', 'best_direction': 'higher', 'attempts': 3, 'description': 'Best of 3 attempts.'},
    {'key': 'fatigue_index', 'name': 'Fatigue Index', 'category': 'Anaerobic Capacity', 'unit': '%', 'input_label': 'Round time', 'best_direction': 'lower', 'attempts': 6, 'description': 'Six rounds of 50 heavy-bag punches with 30 seconds rest.'},
    {'key': 'max_punches_60', 'name': '60 Seconds Max Effort', 'category': 'Anaerobic Capacity', 'unit': 'punches', 'input_label': 'Punches', 'best_direction': 'higher', 'attempts': 1, 'description': 'Maximum punches in 60 seconds.'},
    {'key': 'cooper_run', 'name': 'Cooper 12 min Run', 'category': 'Anaerobic Base', 'unit': 'VO₂ max', 'input_label': 'Distance', 'best_direction': 'higher', 'attempts': 1, 'description': 'Enter total distance in miles; VO₂ max is calculated automatically.'},
    {'key': 'max_kicks_60', 'name': '60 Seconds Full Power Kicks', 'category': 'Muscle Endurance', 'unit': 'kicks', 'input_label': 'Kicks', 'best_direction': 'higher', 'attempts': 1, 'description': 'Maximum full-power kicks in 60 seconds.'},
    {'key': 'pullup_static_hold', 'name': 'Pull Up Static Hold', 'category': 'Muscle Endurance', 'unit': 'sec', 'input_label': 'Duration', 'best_direction': 'higher', 'attempts': 1, 'description': '90-degree elbow hold with chin above the bar.'},
]

TEST_DEFINITIONS = {test['key']: test for test in FITNESS_TESTS}
TRAINING_CATEGORIES = ('Strength', 'Power', 'Aerobic')


def list_results(test_key=None, limit=100):
    q = FitnessTestResult.query
    if test_key:
        q = q.filter_by(test_key=test_key)
    return q.order_by(FitnessTestResult.tested_at.desc()).limit(limit).all()


def create_result(data):
    required = ('test_key', 'category', 'value', 'unit')
    missing = [k for k in required if data.get(k) is None]
    if missing:
        raise ValueError('Missing required fields: ' + ', '.join(missing))
    result = FitnessTestResult(
        test_key=data['test_key'], category=data['category'], value=float(data['value']),
        unit=data['unit'], notes=data.get('notes'), details=data.get('details')
    )
    db.session.add(result)
    db.session.commit()
    return result


def _training_types(session):
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


def _fitness_history_state():
    rows = FitnessTestResult.query.order_by(FitnessTestResult.tested_at.desc()).all()
    stats = {}
    history = {}

    for test in FITNESS_TESTS:
        test_rows = [row for row in rows if row.test_key == test['key']]
        values = [row.value for row in test_rows]
        stats[test['key']] = {
            'best': (min(values) if test['best_direction'] == 'lower' else max(values)) if values else None,
            'average': (sum(values) / len(values)) if values else None,
            'count': len(values),
            'unit': test['unit'],
        }
        history[test['key']] = [
            {
                'id': row.id,
                'value': row.value,
                'unit': row.unit,
                'tested_at': row.tested_at.strftime('%Y-%m-%d %H:%M'),
                'notes': row.notes or '',
            }
            for row in reversed(test_rows)
        ]

    return stats, history


def get_progress_view_state(year=None, month=None, today=None):
    today = today or date.today()
    try:
        year = int(year) if year is not None and str(year).strip() != '' else today.year
    except (TypeError, ValueError):
        year = today.year
    try:
        month = int(month) if month is not None and str(month).strip() != '' else today.month
    except (TypeError, ValueError):
        month = today.month
    if not 1 <= month <= 12:
        month, year = today.month, today.year

    # Ignore completed logs whose parent workout was later deleted. This keeps
    # the dashboard compatible with the existing UI and avoids orphan failures.
    sessions = (WorkoutLog.query
                .join(Workout, Workout.id == WorkoutLog.workout_id)
                .filter(WorkoutLog.end_time.isnot(None))
                .order_by(WorkoutLog.end_time.desc()).all())

    session_types = {session.id: _training_types(session) for session in sessions}
    calendar_data = defaultdict(lambda: {'count': 0, 'types': set()})
    type_counts = {name: 0 for name in TRAINING_CATEGORIES}
    workout_dates = set()
    exercise_ids = set()
    logged_sets = 0

    for session in sessions:
        d = session.end_time.date()
        workout_dates.add(d)
        types = session_types[session.id]
        calendar_data[d]['count'] += 1
        calendar_data[d]['types'].update(types)

        if d.year == year and d.month == month:
            for training_type in types:
                type_counts[training_type] += 1

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
            'types': {k: k in entry['types'] for k in TRAINING_CATEGORIES},
            'is_today': d == today,
        })
    while len(days) % 7:
        days.append({'empty': True})

    prev_month, prev_year = month - 1, year
    if prev_month == 0:
        prev_month, prev_year = 12, year - 1
    next_month, next_year = month + 1, year
    if next_month == 13:
        next_month, next_year = 1, year + 1

    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_type_counts = {name: 0 for name in TRAINING_CATEGORIES}
    week_workout_dates = set()
    for session in sessions:
        d = session.end_time.date()
        if week_start <= d <= week_end:
            week_workout_dates.add(d)
            for training_type in session_types[session.id]:
                week_type_counts[training_type] += 1

    chart_months = []
    chart_lookup = {}
    current_month = date(today.year, today.month, 1)
    for offset in range(11, -1, -1):
        total_months = current_month.year * 12 + current_month.month - 1 - offset
        y = total_months // 12
        m = total_months % 12 + 1
        key = (y, m)
        chart_lookup[key] = {name: 0 for name in TRAINING_CATEGORIES}
        chart_months.append({
            'key': key,
            'label': pycalendar.month_abbr[m],
            'year': y,
            'is_current': key == (today.year, today.month),
        })

    for session in sessions:
        d = session.end_time.date()
        key = (d.year, d.month)
        if key in chart_lookup:
            for training_type in session_types[session.id]:
                chart_lookup[key][training_type] += 1

    max_chart_total = 0
    for item in chart_months:
        item['counts'] = chart_lookup[item['key']]
        item['total'] = sum(item['counts'].values())
        max_chart_total = max(max_chart_total, item['total'])

    last_12_total = sum(item['total'] for item in chart_months)
    avg_monthly = round(last_12_total / 12, 1)
    if last_12_total:
        busiest_category = max(TRAINING_CATEGORIES, key=lambda name: sum(
            item['counts'][name] for item in chart_months
        ))
        busiest_category_count = sum(
            item['counts'][busiest_category] for item in chart_months
        )
    else:
        busiest_category = '—'
        busiest_category_count = 0

    completed_weeks = {
        (d.isocalendar().year, d.isocalendar().week)
        for d in workout_dates
    }
    streak = 0
    week_cursor = week_start
    while (week_cursor.isocalendar().year, week_cursor.isocalendar().week) in completed_weeks:
        streak += 1
        week_cursor -= timedelta(days=7)

    # Preserve the template contract: progress.html reads session.summary.
    for session in sessions:
        grouped = {}
        for set_log in session.sets:
            key = (set_log.exercise_id, set_log.category or '')
            item = grouped.setdefault(key, {
                'name': set_log.exercise.name,
                'category': set_log.category,
                'sets': 0,
                'weight': None,
                'reps': None,
                'duration': None,
                'time_seconds': None,
                'distance_meters': None,
            })
            item['sets'] += 1
            if set_log.weight is not None:
                item['weight'] = set_log.weight if item['weight'] is None else max(item['weight'], set_log.weight)
            if set_log.reps is not None:
                item['reps'] = set_log.reps
            if set_log.duration is not None:
                item['duration'] = set_log.duration
            if set_log.time_seconds is not None:
                item['time_seconds'] = set_log.time_seconds
            if set_log.distance_meters is not None:
                item['distance_meters'] = set_log.distance_meters
        session.summary = list(grouped.values())

    max_type = max(type_counts.values(), default=0)
    type_percent = {
        key: round(value / max_type * 100) if max_type else 0
        for key, value in type_counts.items()
    }

    calendar_obj = {
        'year': year,
        'month': month,
        'month_name': pycalendar.month_name[month],
        'days': days,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
    }
    stats = {
        'total_workouts': len(sessions),
        'this_month': sum(1 for d in workout_dates if d.year == year and d.month == month),
        'current_streak': streak,
        'logged_sets': logged_sets,
        'active_exercises': len(exercise_ids),
    }
    week_stats = {
        'start': week_start,
        'end': week_end,
        'total_workouts': len(week_workout_dates),
        'type_counts': week_type_counts,
    }
    long_term = {
        'total': last_12_total,
        'avg_monthly': avg_monthly,
        'busiest_category': busiest_category,
        'busiest_category_count': busiest_category_count,
        'max_chart_total': max_chart_total,
    }
    fitness_stats, fitness_history = _fitness_history_state()

    return {
        'sessions': sessions,
        'calendar': calendar_obj,
        'stats': stats,
        'type_stats': type_counts,
        'type_percent': type_percent,
        'week_stats': week_stats,
        'chart_months': chart_months,
        'long_term': long_term,
        'fitness_tests': FITNESS_TESTS,
        'fitness_stats': fitness_stats,
        'fitness_history': fitness_history,
    }


def progress_snapshot(year=None, month=None):
    state = get_progress_view_state(year, month)
    return {
        'calendar': state['calendar'],
        'stats': state['stats'],
        'type_stats': state['type_stats'],
        'type_percent': state['type_percent'],
        'week_stats': {
            **state['week_stats'],
            'start': state['week_stats']['start'].isoformat(),
            'end': state['week_stats']['end'].isoformat(),
        },
        'chart_months': [
            {**item, 'key': list(item['key'])}
            for item in state['chart_months']
        ],
        'long_term': state['long_term'],
        'fitness_tests': state['fitness_tests'],
        'fitness_stats': state['fitness_stats'],
        'fitness_history': state['fitness_history'],
    }


def save_ui_fitness_test(form):
    key = (form.get('test_key') or '').strip()
    definition = TEST_DEFINITIONS.get(key)
    if not definition:
        raise LookupError('Please select a valid fitness test.')

    details = {}
    try:
        if key == 'fatigue_index':
            rounds = [float(form.get(f'round_{i}')) for i in range(1, 7)]
            if any(value <= 0 for value in rounds):
                raise ValueError
            value = ((rounds[5] - rounds[0]) / rounds[0]) * 100
            details['round_times'] = rounds
        elif key in ('horizontal_long_jump', 'vertical_jump', 'medicine_ball_throw'):
            attempts = [float(form.get(f'attempt_{i}')) for i in range(1, 4)]
            if any(value < 0 for value in attempts):
                raise ValueError
            value = max(attempts)
            details['attempts'] = attempts
        else:
            value = float(form.get('value'))
            if value < 0:
                raise ValueError
            if key == 'cooper_run':
                if value <= 0:
                    raise ValueError
                details['distance_miles'] = value
                value = (value * 1609.344 - 504.9) / 44.73
    except (TypeError, ValueError):
        raise ValueError('Please enter valid values for the selected fitness test.')

    result = FitnessTestResult(
        test_key=key,
        category=definition['category'],
        value=value,
        unit=definition['unit'],
        notes=(form.get('notes') or '').strip(),
        tested_at=datetime.utcnow(),
        details=details or None,
    )
    db.session.add(result)
    db.session.commit()
    return result, definition


def as_dict(result):
    return fitness_test_to_dict(result)
