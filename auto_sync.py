"""
Auto-sync: watch for file changes, commit + push to GitHub.
Run once alongside your dev session. Ctrl+C to stop.
"""
import os, sys, time, subprocess, threading
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

BASE = os.path.dirname(os.path.abspath(__file__))

IGNORE_DIRS  = {'.git', 'dist', 'build_tmp', '__pycache__', 'android', '.idea'}
IGNORE_FILES = {'users.db', 'config.json', 'auto_sync.py'}
IGNORE_EXT   = {'.pyc', '.pyo', '.spec', '.log'}
WATCH_EXT    = {'.py', '.html', '.js', '.css', '.json', '.md', '.svg', '.txt'}

_timer = None
_lock  = threading.Lock()
DEBOUNCE = 3.0  # seconds after last change before committing


def run(cmd):
    return subprocess.run(cmd, cwd=BASE, capture_output=True, text=True, shell=True)


def should_ignore(path):
    rel = os.path.relpath(path, BASE)
    parts = rel.replace('\\', '/').split('/')
    if any(p in IGNORE_DIRS for p in parts):
        return True
    name = os.path.basename(path)
    if name in IGNORE_FILES:
        return True
    ext = os.path.splitext(name)[1].lower()
    if ext in IGNORE_EXT:
        return True
    if WATCH_EXT and ext not in WATCH_EXT:
        return True
    return False


def do_sync():
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'\n[{ts}] Syncing to GitHub...', flush=True)

    status = run('git status --porcelain')
    if not status.stdout.strip():
        print('  No changes to commit.', flush=True)
        return

    run('git add -A')

    changed = [l[3:].strip() for l in status.stdout.splitlines() if l.strip()]
    if len(changed) == 1:
        msg = f'auto: update {changed[0]}'
    elif len(changed) <= 4:
        msg = f'auto: update {", ".join(changed)}'
    else:
        msg = f'auto: update {len(changed)} files'

    r = run(f'git commit -m "{msg}"')
    if r.returncode != 0:
        print(f'  Commit failed: {r.stderr.strip()}', flush=True)
        return
    print(f'  Committed: {msg}', flush=True)

    r = run('git push origin master')
    if r.returncode == 0:
        print(f'  Pushed OK -> GitHub', flush=True)
    else:
        print(f'  Push failed: {r.stderr.strip()}', flush=True)


def schedule_sync():
    global _timer
    with _lock:
        if _timer:
            _timer.cancel()
        _timer = threading.Timer(DEBOUNCE, do_sync)
        _timer.daemon = True
        _timer.start()


class Handler(FileSystemEventHandler):
    def on_any_event(self, event):
        if event.is_directory:
            return
        src = getattr(event, 'src_path', '') or ''
        if should_ignore(src):
            return
        rel = os.path.relpath(src, BASE)
        print(f'  Changed: {rel}', flush=True)
        schedule_sync()


if __name__ == '__main__':
    print('=' * 52)
    print('  Auto-sync  [watching for file changes]')
    print(f'  Repo: {BASE}')
    print(f'  Debounce: {DEBOUNCE}s  |  Ctrl+C to stop')
    print('=' * 52)

    observer = Observer()
    observer.schedule(Handler(), BASE, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
        print('\nAuto-sync stopped.')
