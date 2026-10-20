import errno
import json
import math
import os
import random
import re
import secrets
import sqlite3
import socket
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from content import ACHIEVEMENTS, CODE_SETS, LEVELS, MODES, VARIANTS, make_text

ROOT = Path(__file__).parent
app = Flask(__name__)
app.config.update(
    DATABASE=os.environ.get('DATABASE', str(ROOT / 'instance' / 'game.db')),
    MAX_CONTENT_LENGTH=2_000_000,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1',
    PERMANENT_SESSION_LIFETIME=timedelta(days=30)
)
secret_file = ROOT / 'instance' / 'secret.key'
if os.environ.get('SECRET_KEY'):
    app.secret_key = os.environ['SECRET_KEY']
else:
    secret_file.parent.mkdir(exist_ok=True)
    if not secret_file.exists():
        secret_file.write_text(secrets.token_hex(32))
        secret_file.chmod(0o600)
    app.secret_key = secret_file.read_text().strip()
MSK = timezone(timedelta(hours=3))


def now():
    return datetime.now(timezone.utc)


def db():
    if 'db' not in g:
        Path(app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(app.config['DATABASE'], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


@app.teardown_appcontext
def close_db(error):
    connection = g.pop('db', None)
    if connection:
        connection.close()


def init_db():
    db().executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            xp INTEGER NOT NULL DEFAULT 0,
            streak INTEGER NOT NULL DEFAULT 0,
            best_streak INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS exercises (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            mode TEXT NOT NULL,
            language TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            text TEXT NOT NULL,
            started TEXT NOT NULL,
            bonus_at INTEGER NOT NULL,
            finished INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY,
            exercise_id TEXT UNIQUE NOT NULL REFERENCES exercises(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            created TEXT NOT NULL,
            mode TEXT NOT NULL,
            cpm REAL NOT NULL,
            wpm REAL NOT NULL,
            accuracy REAL NOT NULL,
            errors INTEGER NOT NULL,
            correct INTEGER NOT NULL,
            duration REAL NOT NULL,
            xp INTEGER NOT NULL,
            combo INTEGER NOT NULL,
            mistakes TEXT NOT NULL,
            pairs TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS awards (
            user_id INTEGER NOT NULL REFERENCES users(id),
            achievement TEXT NOT NULL,
            created TEXT NOT NULL,
            PRIMARY KEY (user_id, achievement)
        );
    ''')
    columns = [row['name'] for row in db().execute('PRAGMA table_info(users)')]
    if 'guest' not in columns:
        db().execute('ALTER TABLE users ADD COLUMN guest INTEGER NOT NULL DEFAULT 0')
        db().commit()


def user_data(user):
    return {'id': user['id'], 'name': user['name'], 'xp': user['xp'],
            'level': user['xp'] // 200 + 1, 'level_xp': user['xp'] % 200,
            'best_streak': user['best_streak'], 'guest': bool(user['guest'])}


def ensure_player():
    if not g.user:
        guest_id = secrets.token_hex(16)
        cursor = db().execute(
            'INSERT INTO users (name, email, password, guest) VALUES (?, ?, ?, 1)',
            ('Гость', guest_id + '@guest.invalid', generate_password_hash(guest_id)))
        db().commit()
        session['user_id'] = cursor.lastrowid
        session.permanent = True
        g.user = db().execute('SELECT * FROM users WHERE id = ?', (cursor.lastrowid,)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            return jsonify(error='Сначала войдите в аккаунт.'), 401
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def prepare_request():
    g.user = db().execute('SELECT * FROM users WHERE id = ?', (session.get('user_id'),)).fetchone()
    if request.method == 'POST' and (not session.get('csrf') or not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session['csrf'])):
        return jsonify(error='Обновите страницу и попробуйте ещё раз.'), 403


@app.get('/')
def index():
    ensure_player()
    session.setdefault('csrf', secrets.token_hex(24))
    return render_template('index.html', csrf=session['csrf'])


@app.get('/api/me')
def me():
    ensure_player()
    return jsonify(user=user_data(g.user) if g.user else None, modes=MODES, unlocks=LEVELS)


@app.post('/api/register')
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))
    if not 2 <= len(name) <= 24:
        return jsonify(error='Имя должно содержать от 2 до 24 символов.'), 400
    if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        return jsonify(error='Укажите корректный email.'), 400
    if not 8 <= len(password) <= 128:
        return jsonify(error='Пароль должен содержать от 8 до 128 символов.'), 400
    try:
        password_hash = generate_password_hash(password)
        if g.user and g.user['guest']:
            db().execute('UPDATE users SET name = ?, email = ?, password = ?, guest = 0 WHERE id = ?',
                         (name, email, password_hash, g.user['id']))
            user_id = g.user['id']
        else:
            cursor = db().execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)',
                                  (name, email, password_hash))
            user_id = cursor.lastrowid
        db().commit()
    except sqlite3.IntegrityError:
        db().rollback()
        return jsonify(error='Этот email уже зарегистрирован.'), 409
    session['user_id'] = user_id
    session.permanent = True
    return jsonify(ok=True)


@app.post('/api/login')
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))
    user = db().execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if len(password) > 128 or not user or user['guest'] or not check_password_hash(user['password'], password):
        return jsonify(error='Неверный email или пароль.'), 400
    session['user_id'] = user['id']
    session.permanent = True
    return jsonify(ok=True)


@app.post('/api/logout')
def logout():
    session.pop('user_id', None)
    return jsonify(ok=True)


@app.post('/api/start')
def start():
    ensure_player()
    data = request.get_json(silent=True) or {}
    mode = data.get('mode', 'words')
    language = data.get('language', 'ru')
    difficulty = data.get('difficulty', 'easy')
    code_language = data.get('code_language', 'python')
    variant = data.get('variant', 'mixed')
    if mode not in MODES or language not in ('ru', 'en') or difficulty not in ('easy', 'medium', 'hard') or code_language not in ('python', 'javascript', 'html'):
        return jsonify(error='Проверьте настройки упражнения.'), 400
    if variant not in VARIANTS[mode]:
        return jsonify(error='Неизвестный набор упражнений.'), 400
    if mode == 'code' and variant != 'mixed' and variant not in CODE_SETS[code_language]:
        return jsonify(error='Этот набор не подходит к выбранному языку кода.'), 400
    level = g.user['xp'] // 200 + 1
    required = max(LEVELS[mode], {'easy': 1, 'medium': 2, 'hard': 3}[difficulty])
    if level < required:
        return jsonify(error=f'Откроется на уровне {required}.'), 403
    previous = db().execute('SELECT text FROM exercises WHERE user_id = ? ORDER BY started DESC LIMIT 1',
                            (g.user['id'],)).fetchone()
    text = make_text(mode, language, difficulty, code_language, variant, previous['text'] if previous else '')
    exercise_id = secrets.token_hex(16)
    bonus_at = random.randint(15, max(15, min(45, len(text) - 5)))
    db().execute('INSERT INTO exercises VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)',
                 (exercise_id, g.user['id'], mode, language, difficulty, text, now().isoformat(), bonus_at))
    db().commit()
    return jsonify(id=exercise_id, text=text, bonus_at=bonus_at, user=user_data(g.user))


def analyze(text, events, bonus_at, initial_streak):
    position = errors = points = best_combo = combo = 0
    streak = initial_streak
    best_streak = streak
    mistakes = {}
    pairs = {}
    bonus_until = -1
    bonus_used = False
    previous_time = 0
    for event in events:
        if not isinstance(event, dict):
            raise ValueError
        key = event.get('key')
        timestamp = event.get('t')
        if not isinstance(key, str) or not 1 <= len(key) <= 12:
            raise ValueError
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp) or timestamp < previous_time:
            raise ValueError
        if position >= len(text):
            raise ValueError
        previous_time = timestamp
        expected = text[position]
        if key == expected:
            position += 1
            combo += 1
            streak += 1
            best_combo = max(best_combo, combo)
            best_streak = max(best_streak, streak)
            if position == bonus_at:
                bonus_until = timestamp + 10000
                bonus_used = True
            multiplier = 5 if combo >= 50 else 3 if combo >= 25 else 2 if combo >= 10 else 1
            points += multiplier * (2 if bonus_used and timestamp < bonus_until else 1)
        else:
            errors += 1
            combo = streak = 0
            mistakes[expected] = mistakes.get(expected, 0) + 1
            pair = text[max(0, position - 1):position + 1]
            pairs[pair] = pairs.get(pair, 0) + 1
    return {'correct': position, 'errors': errors, 'xp': points, 'combo': best_combo,
            'streak': streak, 'best_streak': best_streak, 'mistakes': mistakes, 'pairs': pairs}


@app.post('/api/finish')
@login_required
def finish():
    data = request.get_json(silent=True) or {}
    exercise = db().execute('SELECT * FROM exercises WHERE id = ? AND user_id = ?',
                            (data.get('id'), g.user['id'])).fetchone()
    if not exercise:
        return jsonify(error='Упражнение не найдено.'), 404
    if exercise['finished']:
        return saved_result(exercise['id'])
    events = data.get('events')
    if not isinstance(events, list) or not 1 <= len(events) <= 20000:
        return jsonify(error='Некорректная история нажатий.'), 400
    try:
        result = analyze(exercise['text'], events, exercise['bonus_at'], g.user['streak'])
    except (ValueError, TypeError):
        return jsonify(error='Некорректная история нажатий.'), 400
    duration = events[-1]['t'] / 1000
    elapsed = (now() - datetime.fromisoformat(exercise['started'])).total_seconds()
    if result['correct'] != len(exercise['text']) or duration < 1 or duration > elapsed + 2 or duration > 86400:
        return jsonify(error='Завершите упражнение полностью. Время должно быть от 1 секунды до 24 часов.'), 400
    cpm = result['correct'] * 60 / duration
    accuracy = result['correct'] * 100 / len(events)
    created = now().isoformat()
    connection = db()
    connection.execute('BEGIN IMMEDIATE')
    current = connection.execute('SELECT * FROM users WHERE id = ?', (g.user['id'],)).fetchone()
    fresh = connection.execute('SELECT finished FROM exercises WHERE id = ?', (exercise['id'],)).fetchone()
    if fresh['finished']:
        connection.rollback()
        return saved_result(exercise['id'])
    result = analyze(exercise['text'], events, exercise['bonus_at'], current['streak'])
    connection.execute('UPDATE exercises SET finished = 1 WHERE id = ?', (exercise['id'],))
    connection.execute('''INSERT INTO results (exercise_id, user_id, created, mode, cpm, wpm,
        accuracy, errors, correct, duration, xp, combo, mistakes, pairs) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (exercise['id'], g.user['id'], created, exercise['mode'], cpm, cpm / 5, accuracy,
         result['errors'], result['correct'], duration, result['xp'], result['combo'], json.dumps(result['mistakes']), json.dumps(result['pairs'])))
    connection.execute('UPDATE users SET xp = xp + ?, streak = ?, best_streak = MAX(best_streak, ?) WHERE id = ?',
                       (result['xp'], result['streak'], result['best_streak'], g.user['id']))
    count = connection.execute('SELECT COUNT(*) FROM results WHERE user_id = ?', (g.user['id'],)).fetchone()[0]
    checks = {'first': True, 'fast': cpm >= 200, 'perfect': result['errors'] == 0,
              'steel': result['best_streak'] >= 1000, 'genius': cpm / 5 >= 300, 'regular': count >= 10}
    earned = []
    for award in ACHIEVEMENTS:
        if checks[award['id']]:
            cursor = connection.execute('INSERT OR IGNORE INTO awards VALUES (?, ?, ?)', (g.user['id'], award['id'], created))
            if cursor.rowcount:
                earned.append(award['name'])
    connection.commit()
    return saved_result(exercise['id'], earned)


def saved_result(exercise_id, earned=None):
    row = db().execute('SELECT * FROM results WHERE exercise_id = ?', (exercise_id,)).fetchone()
    user = db().execute('SELECT * FROM users WHERE id = ?', (g.user['id'],)).fetchone()
    return jsonify(cpm=round(row['cpm'], 1), wpm=round(row['wpm'], 1), accuracy=round(row['accuracy'], 1),
                   errors=row['errors'], xp=row['xp'], combo=row['combo'], earned=earned or [], user=user_data(user))


@app.get('/api/stats')
@login_required
def stats():
    rows = db().execute('SELECT * FROM results WHERE user_id = ? ORDER BY created', (g.user['id'],)).fetchall()
    mistakes = {}
    pairs = {}
    daily = {}
    for row in rows:
        for char, count in json.loads(row['mistakes']).items():
            mistakes[char] = mistakes.get(char, 0) + count
        for pair, count in json.loads(row['pairs']).items():
            pairs[pair] = pairs.get(pair, 0) + count
        day = datetime.fromisoformat(row['created']).astimezone(MSK).date().isoformat()
        item = daily.setdefault(day, {'correct': 0, 'duration': 0, 'errors': 0})
        for key in item:
            item[key] += row[key]
    days = []
    for offset in range(13, -1, -1):
        day = (now().astimezone(MSK).date() - timedelta(days=offset)).isoformat()
        item = daily.get(day)
        days.append({'day': day, 'cpm': round(item['correct'] * 60 / item['duration'], 1) if item else None,
                     'accuracy': round(item['correct'] * 100 / (item['correct'] + item['errors']), 1) if item else None})
    correct = sum(row['correct'] for row in rows)
    errors = sum(row['errors'] for row in rows)
    duration = sum(row['duration'] for row in rows)
    awards = [row[0] for row in db().execute('SELECT achievement FROM awards WHERE user_id = ?', (g.user['id'],))]
    return jsonify(count=len(rows), duration=round(duration), correct=correct, errors=errors,
                   cpm=round(correct * 60 / duration, 1) if duration else 0,
                   accuracy=round(correct * 100 / (correct + errors), 1) if correct + errors else 0,
                   best_cpm=round(max((row['cpm'] for row in rows), default=0), 1), days=days,
                   mistakes=sorted(mistakes.items(), key=lambda item: -item[1])[:10],
                   pairs=sorted(pairs.items(), key=lambda item: -item[1])[:10],
                   achievements=[dict(award, unlocked=award['id'] in awards) for award in ACHIEVEMENTS],
                   history=[{'mode': MODES[row['mode']], 'created': row['created'], 'cpm': round(row['cpm'], 1),
                             'accuracy': round(row['accuracy'], 1), 'errors': row['errors'], 'xp': row['xp']} for row in reversed(rows[-10:])])


@app.get('/api/leaders')
def leaders():
    period = request.args.get('period', 'all')
    metric = request.args.get('metric', 'cpm')
    if period not in ('today', 'week', 'all') or metric not in ('cpm', 'accuracy', 'xp'):
        return jsonify(error='Неизвестный фильтр.'), 400
    local = now().astimezone(MSK)
    if period == 'today':
        since = local.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        since = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        since = datetime(1970, 1, 1, tzinfo=timezone.utc)
    rows = db().execute('''SELECT u.id, u.name, MAX(r.cpm) AS cpm,
        100.0 * SUM(r.correct) / SUM(r.correct + r.errors) AS accuracy, SUM(r.xp) AS xp,
        COUNT(*) AS count FROM results r JOIN users u ON u.id = r.user_id
        WHERE r.created >= ? AND u.guest = 0 GROUP BY u.id''', (since.astimezone(timezone.utc).isoformat(),)).fetchall()
    items = [dict(row) for row in rows]
    items.sort(key=lambda row: (-row[metric], -row['xp'], row['id']))
    return jsonify(leaders=[dict(row, cpm=round(row['cpm'], 1), wpm=round(row['cpm'] / 5, 1),
                                 accuracy=round(row['accuracy'], 1)) for row in items[:50]])


@app.errorhandler(413)
def too_large(error):
    return jsonify(error='Слишком большой запрос.'), 413


with app.app_context():
    init_db()

def find_port(host, port):
    for candidate in range(port, min(port + 100, 65536)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            try:
                connection.bind((host, candidate))
            except OSError as error:
                if error.errno == errno.EADDRINUSE:
                    continue
                raise
            return connection.getsockname()[1]
    raise RuntimeError('Не найден свободный порт. Укажите другой PORT.')


if __name__ == '__main__':
    host = os.environ.get('HOST', '127.0.0.1')
    requested_port = int(os.environ.get('PORT', 5000))
    port = find_port(host, requested_port)
    if port != requested_port:
        print(f'Порт {requested_port} занят. Используется порт {port}.', flush=True)
    app.run(host=host, port=port)

