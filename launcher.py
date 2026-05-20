"""
Reeman Robot Control — Desktop Launcher
Starts Flask server + opens native window (no browser needed).
"""
import sys, os, threading, time, socket

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except:
        return 'localhost'
    finally:
        s.close()

def wait_ready(port=5000, timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        try:
            socket.create_connection(('localhost', port), timeout=0.5).close()
            return True
        except:
            time.sleep(0.3)
    return False

def run_server():
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
    import server
    server.app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    # Start Flask in background thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    local_ip = get_local_ip()

    # Wait for server ready
    if not wait_ready():
        import tkinter.messagebox as mb
        mb.showerror('Error', 'Server failed to start on port 5000.')
        sys.exit(1)

    # Open native window via pywebview
    try:
        import webview
        window = webview.create_window(
            title='Reeman Moon Knight 2.0 - Robot Control',
            url='http://localhost:5000',
            width=1280,
            height=800,
            min_size=(900, 600),
        )
        # Show phone URL in window title after load
        def on_loaded():
            window.set_title(f'Robot Control  |  Phone: http://{local_ip}:5000/mobile')
        window.events.loaded += on_loaded
        webview.start(debug=False)
    except ImportError:
        # Fallback: open browser if pywebview not available
        import webbrowser
        webbrowser.open('http://localhost:5000')
        print(f'Phone access: http://{local_ip}:5000/mobile')
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            pass
