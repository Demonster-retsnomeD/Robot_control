"""
Dev launcher: Flask runs as subprocess with auto-reloader.
pywebview stays alive and auto-refreshes when server restarts.
"""
import sys, os, socket, time, threading, subprocess
import webview

BASE = os.path.dirname(os.path.abspath(__file__))

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(('8.8.8.8', 80)); return s.getsockname()[0]
    except: return 'localhost'
    finally: s.close()

def server_up(timeout=0.5):
    try:
        socket.create_connection(('localhost', 5000), timeout=timeout).close()
        return True
    except: return False

def wait_ready(timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        if server_up(): return True
        time.sleep(0.3)
    return False

def start_flask():
    env = os.environ.copy()
    env['FLASK_ENV'] = 'development'
    return subprocess.Popen(
        [sys.executable, '-u', 'server.py', '--dev'],
        cwd=BASE, env=env
    )

def monitor(window):
    """Detect server restart → reload pywebview page."""
    was_down = False
    while True:
        time.sleep(1)
        up = server_up()
        if not up:
            was_down = True
        elif was_down:
            was_down = False
            time.sleep(0.6)   # let Flask finish startup
            try: window.evaluate_js('window.location.reload()')
            except: pass

if __name__ == '__main__':
    print('=' * 48)
    print('  Robot Control  [DEV MODE — hot reload ON]')
    print('=' * 48)

    proc = start_flask()
    local_ip = get_local_ip()

    if not wait_ready():
        print('[ERROR] Server failed to start'); proc.terminate(); sys.exit(1)

    print(f'\n  PC:    http://localhost:5000')
    print(f'  Phone: http://{local_ip}:5000/mobile')
    print('\n  Edit any .py / .html / .js → page auto-reloads\n')

    window = webview.create_window(
        'Robot Control [DEV]', 'http://localhost:5000',
        width=1280, height=800, min_size=(900, 600)
    )
    threading.Thread(target=monitor, args=(window,), daemon=True).start()

    try:
        webview.start(debug=True)
    finally:
        proc.terminate()
