import os
import json
import uuid
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, 
    url_for, jsonify, flash
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "cmfit-secret-key-change-in-production"

# Directory Configuration
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

WORKOUTS_FILE = os.path.join(DATA_DIR, 'workouts.json')
EXERCISES_FILE = os.path.join(DATA_DIR, 'exercises.json')
SESSIONS_FILE = os.path.join(DATA_DIR, 'sessions.json')

# Helper Utilities
def load_json(filepath):
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def normalize_workout_exercises(workout, all_exercises_map):
    """
    Returns a list of dicts: [{'id': ex_id, 'sets': X, 'reps': Y, 'rest': Z, 'name': ...}, ...]
    Merged with base exercise definitions while keeping workout overrides intact.
    Handles both legacy string IDs ("ex_1") and override dict objects ({"id": "ex_1", "sets": 4}).
    """
    result = []
    for item in workout.get('exercise_ids', []):
        if isinstance(item, str):
            eid = item
            override_sets, override_reps, override_rest = None, None, None
        else:
            eid = item.get('id')
            override_sets = item.get('sets')
            override_reps = item.get('reps')
            override_rest = item.get('rest')

        if eid in all_exercises_map:
            ex = dict(all_exercises_map[eid])  # Copy base defaults
            if override_sets is not None:
                ex['sets'] = int(override_sets)
            if override_reps is not None:
                ex['reps'] = int(override_reps)
            if override_rest is not None:
                ex['rest'] = int(override_rest)
            result.append(ex)
    return result

# Seed Data Initialization
def init_db():
    if not os.path.exists(EXERCISES_FILE):
        default_exercises = [
            {
                "id": "ex_1",
                "name": "Barbell Bench Press",
                "muscles": ["Chest", "Triceps", "Shoulders"],
                "image": "",
                "link": "https://en.wikipedia.org/wiki/Bench_press",
                "instructions": "Lie on bench, lower bar to mid-chest, press up explosively.",
                "sets": 4,
                "reps": 10,
                "rest": 60
            },
            {
                "id": "ex_2",
                "name": "Bodyweight Squat",
                "muscles": ["Upper Leg", "Glutes"],
                "image": "",
                "link": "",
                "instructions": "Keep chest up, lower hips below knees, push through heels.",
                "sets": 3,
                "reps": 12,
                "rest": 45
            }
        ]
        save_json(EXERCISES_FILE, default_exercises)
    
    if not os.path.exists(WORKOUTS_FILE):
        default_workouts = [
            {
                "id": "wk_1",
                "name": "Full Body Starter",
                "exercise_ids": ["ex_1", "ex_2"]
            }
        ]
        save_json(WORKOUTS_FILE, default_workouts)

init_db()

# Application Routes
@app.route('/')
def workout_list():
    workouts = load_json(WORKOUTS_FILE)
    exercises = {e['id']: e for e in load_json(EXERCISES_FILE)}
    
    workout_data = []
    for w in workouts:
        total_sec = 0
        norm_exercises = normalize_workout_exercises(w, exercises)
        ex_count = len(norm_exercises)
        for ex in norm_exercises:
            total_sec += (ex['sets'] * 45) + (ex['sets'] * ex['rest'])
        
        mins = round(total_sec / 60)
        workout_data.append({
            "id": w['id'],
            "name": w['name'],
            "count": ex_count,
            "duration": mins
        })

    return render_template('workout_list.html', workouts=workout_data, active_page='workouts')


@app.route('/workout/add', methods=['GET', 'POST'])
def add_workout():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash("Workout name is required.", "danger")
            return redirect(url_for('add_workout'))
        
        workouts = load_json(WORKOUTS_FILE)
        new_id = f"wk_{uuid.uuid4().hex[:8]}"
        workouts.append({"id": new_id, "name": name, "exercise_ids": []})
        save_json(WORKOUTS_FILE, workouts)
        
        flash("Workout created successfully!", "success")
        return redirect(url_for('view_workout', workout_id=new_id))

    return render_template('add_workout.html', active_page='workouts')


@app.route('/workout/<workout_id>')
def view_workout(workout_id):
    workouts = load_json(WORKOUTS_FILE)
    workout = next((w for w in workouts if w['id'] == workout_id), None)
    if not workout:
        flash("Workout not found.", "danger")
        return redirect(url_for('workout_list'))

    all_exercises = {e['id']: e for e in load_json(EXERCISES_FILE)}
    workout_exercises = normalize_workout_exercises(workout, all_exercises)

    return render_template('view_workout.html', workout=workout, workout_exercises=workout_exercises, active_page='workouts')


@app.route('/workout/<workout_id>/add-exercise', methods=['GET', 'POST'])
def add_exercise_to_workout(workout_id):
    workouts = load_json(WORKOUTS_FILE)
    workout = next((w for w in workouts if w['id'] == workout_id), None)
    if not workout:
        return redirect(url_for('workout_list'))

    if request.method == 'POST':
        selected_ids = request.form.getlist('exercise_ids')
        updated_list = []

        for eid in selected_ids:
            sets = request.form.get(f'sets_{eid}')
            reps = request.form.get(f'reps_{eid}')
            rest = request.form.get(f'rest_{eid}')
            
            entry = {"id": eid}
            if sets: entry["sets"] = int(sets)
            if reps: entry["reps"] = int(reps)
            if rest: entry["rest"] = int(rest)
            
            updated_list.append(entry)

        workout['exercise_ids'] = updated_list
        save_json(WORKOUTS_FILE, workouts)
        flash("Exercises saved to workout!", "success")
        return redirect(url_for('view_workout', workout_id=workout_id))

    all_exercises = load_json(EXERCISES_FILE)
    
    # Map existing exercise configurations
    existing_map = {}
    for item in workout.get('exercise_ids', []):
        if isinstance(item, str):
            existing_map[item] = {}
        else:
            existing_map[item['id']] = item

    return render_template(
        'add_exercise_to_workout.html', 
        workout=workout, 
        all_exercises=all_exercises, 
        existing_map=existing_map,
        active_page='workouts'
    )


@app.route('/exercise/new', methods=['GET', 'POST'])
def add_new_exercise():
    return_workout_id = request.args.get('return_workout_id', request.form.get('return_workout_id', ''))
    muscle_groups = ['Abs', 'Back', 'Biceps', 'Chest', 'Forearms', 'Glutes', 'Shoulders', 'Triceps', 'Upper Leg', 'Lower Leg', 'Cardio']

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        muscles = request.form.getlist('muscles')
        link = request.form.get('link', '').strip()
        instructions = request.form.get('instructions', '').strip()
        sets = int(request.form.get('sets', 3))
        reps = int(request.form.get('reps', 10))
        rest = int(request.form.get('rest', 60))

        image_filename = ""
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{uuid.uuid4().hex[:6]}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_filename = filename

        exercises = load_json(EXERCISES_FILE)
        new_ex_id = f"ex_{uuid.uuid4().hex[:8]}"
        new_ex = {
            "id": new_ex_id,
            "name": name,
            "muscles": muscles,
            "image": image_filename,
            "link": link,
            "instructions": instructions,
            "sets": sets,
            "reps": reps,
            "rest": rest
        }
        exercises.append(new_ex)
        save_json(EXERCISES_FILE, exercises)

        if return_workout_id:
            workouts = load_json(WORKOUTS_FILE)
            for w in workouts:
                if w['id'] == return_workout_id:
                    if 'exercise_ids' not in w:
                        w['exercise_ids'] = []
                    
                    # Ensure we don't duplicate entry
                    existing_eids = [item if isinstance(item, str) else item.get('id') for item in w['exercise_ids']]
                    if new_ex_id not in existing_eids:
                        w['exercise_ids'].append({"id": new_ex_id, "sets": sets, "reps": reps, "rest": rest})
                    break
            save_json(WORKOUTS_FILE, workouts)
            flash("New Exercise created and added to workout!", "success")
            return redirect(url_for('view_workout', workout_id=return_workout_id))

        flash("New Exercise created!", "success")
        return redirect(url_for('workout_list'))

    return render_template(
        'add_new_exercise.html', 
        muscle_groups=muscle_groups, 
        return_workout_id=return_workout_id,
        active_page='workouts'
    )


@app.route('/workout/<workout_id>/start')
def start_workout(workout_id):
    workouts = load_json(WORKOUTS_FILE)
    workout = next((w for w in workouts if w['id'] == workout_id), None)
    if not workout or not workout.get('exercise_ids'):
        flash("Cannot start an empty workout.", "danger")
        return redirect(url_for('view_workout', workout_id=workout_id))

    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    sessions = load_json(SESSIONS_FILE)
    
    new_session = {
        "session_id": session_id,
        "workout_id": workout_id,
        "start_time": datetime.utcnow().isoformat() + "Z",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "completed": False,
        "logs": []
    }
    sessions.append(new_session)
    save_json(SESSIONS_FILE, sessions)

    return redirect(url_for('display_exercise', session_id=session_id, exercise_idx=0))


@app.route('/session/<session_id>/exercise/<int:exercise_idx>')
def display_exercise(session_id, exercise_idx):
    sessions = load_json(SESSIONS_FILE)
    session = next((s for s in sessions if s['session_id'] == session_id), None)
    if not session or session.get('completed', False):
        return redirect(url_for('workout_list'))

    workouts = load_json(WORKOUTS_FILE)
    workout = next((w for w in workouts if w['id'] == session['workout_id']), None)
    
    all_exercises_map = {e['id']: e for e in load_json(EXERCISES_FILE)}
    workout_exercises = normalize_workout_exercises(workout, all_exercises_map) if workout else []
    
    if not workout or exercise_idx >= len(workout_exercises):
        return redirect(url_for('finished_workout', session_id=session_id))

    exercise = workout_exercises[exercise_idx]
    
    logged_counts_map = {}
    for ex_item in workout_exercises:
        ex_id = ex_item['id']
        logged_counts_map[ex_id] = len([l for l in session.get('logs', []) if l.get('exercise_id') == ex_id])

    logged_sets = [l for l in session.get('logs', []) if l.get('exercise_id') == exercise['id']]

    return render_template(
        'display_exercise.html', 
        exercise=exercise, 
        session_id=session_id, 
        exercise_idx=exercise_idx, 
        total_exercises=len(workout_exercises),
        all_workout_exercises=workout_exercises,
        logged_counts_map=logged_counts_map,
        logged_sets=logged_sets,
        active_page='workouts',
        is_in_session=True  # <--- Pass flag to template
    )

@app.route('/api/log-set', methods=['POST'])
def log_set():
    data = request.json
    sessions = load_json(SESSIONS_FILE)
    session = next((s for s in sessions if s['session_id'] == data['session_id']), None)
    
    if session:
        session['logs'].append({
            "exercise_id": data['exercise_id'],
            "set_number": data['set_number'],
            "lbs": data['lbs'],
            "reps": data['reps'],
            "rest": data['rest']
        })
        save_json(SESSIONS_FILE, sessions)
        return jsonify({"success": True})
    return jsonify({"success": False}), 400


@app.route('/session/<session_id>/finished')
def finished_workout(session_id):
    sessions = load_json(SESSIONS_FILE)
    session = next((s for s in sessions if s['session_id'] == session_id), None)
    if session:
        session['completed'] = True
        save_json(SESSIONS_FILE, sessions)

    return render_template('finished_workout.html', active_page='workouts')


@app.route('/progress')
def progress():
    sessions = load_json(SESSIONS_FILE)
    workouts = {w['id']: w['name'] for w in load_json(WORKOUTS_FILE)}
    return render_template('progress.html', sessions=sessions, workouts=workouts, active_page='progress')


@app.route('/workout/<workout_id>/reorder', methods=['POST'])
def reorder_workout_exercises(workout_id):
    data = request.json
    new_order = data.get('exercise_ids', [])
    
    workouts = load_json(WORKOUTS_FILE)
    workout = next((w for w in workouts if w['id'] == workout_id), None)
    
    if workout:
        # Preserve configuration objects while reordering
        item_map = {}
        for item in workout.get('exercise_ids', []):
            eid = item if isinstance(item, str) else item.get('id')
            item_map[eid] = item

        reordered = []
        for eid in new_order:
            if eid in item_map:
                reordered.append(item_map[eid])

        workout['exercise_ids'] = reordered
        save_json(WORKOUTS_FILE, workouts)
        return jsonify({"success": True})
    
    return jsonify({"success": False}), 404


@app.route('/workout/<workout_id>/remove-exercise/<exercise_id>', methods=['POST'])
def remove_exercise_from_workout(workout_id, exercise_id):
    workouts = load_json(WORKOUTS_FILE)
    workout = next((w for w in workouts if w['id'] == workout_id), None)
    
    if workout and 'exercise_ids' in workout:
        workout['exercise_ids'] = [
            item for item in workout['exercise_ids'] 
            if (item if isinstance(item, str) else item.get('id')) != exercise_id
        ]
        save_json(WORKOUTS_FILE, workouts)
        return jsonify({"success": True})
        
    return jsonify({"success": False}), 400


@app.route('/workouts/reorder', methods=['POST'])
def reorder_workouts():
    data = request.json
    new_order = data.get('workout_ids', [])
    
    workouts = load_json(WORKOUTS_FILE)
    workout_dict = {w['id']: w for w in workouts}
    
    # Reconstruct list matching the new user-defined order
    reordered_workouts = []
    for wid in new_order:
        if wid in workout_dict:
            reordered_workouts.append(workout_dict.pop(wid))
            
    # Append any workouts that weren't included in the request payload
    reordered_workouts.extend(workout_dict.values())
    
    save_json(WORKOUTS_FILE, reordered_workouts)
    return jsonify({"success": True})


@app.route('/workout/<workout_id>/delete', methods=['POST'])
def delete_workout(workout_id):
    workouts = load_json(WORKOUTS_FILE)
    updated_workouts = [w for w in workouts if w['id'] != workout_id]
    
    if len(workouts) != len(updated_workouts):
        save_json(WORKOUTS_FILE, updated_workouts)
        return jsonify({"success": True})
        
    return jsonify({"success": False, "message": "Workout not found"}), 404


@app.route('/api/active-session')
def get_active_session():
    sessions = load_json(SESSIONS_FILE)
    # Find the most recent active (uncompleted) session
    active_session = next((s for s in reversed(sessions) if not s.get('completed', False)), None)
    
    if active_session:
        workouts = load_json(WORKOUTS_FILE)
        workout = next((w for w in workouts if w['id'] == active_session['workout_id']), None)
        
        if workout:
            all_exercises_map = {e['id']: e for e in load_json(EXERCISES_FILE)}
            workout_exercises = normalize_workout_exercises(workout, all_exercises_map)
            
            # Determine current exercise index based on latest logged set
            last_idx = 0
            if active_session.get('logs'):
                last_logged_eid = active_session['logs'][-1].get('exercise_id')
                for idx, ex in enumerate(workout_exercises):
                    if ex['id'] == last_logged_eid:
                        last_idx = idx
                        break

            return jsonify({
                'active': True,
                'session_id': active_session['session_id'],
                'workout_name': workout['name'],
                'start_time': active_session.get('start_time', datetime.utcnow().isoformat() + "Z"),
                'current_exercise_idx': last_idx
            })

    return jsonify({'active': False})

@app.route('/session/<session_id>/exit', methods=['POST'])
def exit_workout(session_id):
    sessions = load_json(SESSIONS_FILE)
    session = next((s for s in sessions if s['session_id'] == session_id), None)
    if session:
        session['completed'] = True
        save_json(SESSIONS_FILE, sessions)
        flash("Workout ended early.", "info")
    return redirect(url_for('workout_list'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=52889)