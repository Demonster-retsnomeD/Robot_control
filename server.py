"""
Reeman Moon Knight 2.0 — SLAM WEB API Implementation
Source: REEMAN SLAM WEB API 3.0-2025_EN.pdf (local)

ALL endpoints on port 80 (same as robot web UI):
  GET  /reeman/pose          → robot position {x,y,theta}
  GET  /reeman/base_encode   → battery/charge/estop
  GET  /reeman/nav_status    → navigation state
  GET  /reeman/position      → saved waypoints with coords
  GET  /reeman/map           → SLAM map data
  GET  /reeman/speed         → current speed {vx,vth}
  GET  /reeman/get_mode      → mode (1=mapping,2=nav)
  POST /cmd/speed            → {"vx":0.3,"vth":0.5}  (send every 300ms)
  POST /cmd/nav              → {"x":285,"y":252,"theta":1.6}
  POST /cmd/nav_name         → {"point":"A"}
  POST /cmd/cancel_goal      → {}
  POST /cmd/charge           → {"type":2,"point":"充电桩"}
  POST /cmd/max_speed        → {"speed":0.5}
  POST /cmd/move             → {"distance":100,"direction":1,"speed":0.8}
  POST /cmd/turn             → {"direction":1,"angle":90,"speed":0.6}
"""
import sys, json, os, time, math, threading, requests, sqlite3, secrets, concurrent.futures
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_from_directory
from flask_cors import CORS
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

# PyInstaller frozen: data files (config/db) live next to .exe; templates/static in bundle
_FROZEN = getattr(sys, 'frozen', False)
if _FROZEN:
    BASE_DIR    = os.path.dirname(sys.executable)
    _BUNDLE_DIR = sys._MEIPASS
else:
    BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE_DIR = BASE_DIR

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
DB_FILE     = os.path.join(BASE_DIR, "users.db")

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__,
            template_folder=os.path.join(_BUNDLE_DIR, 'templates'),
            static_folder=os.path.join(_BUNDLE_DIR, 'static'))
_key_file = os.path.join(BASE_DIR, ".secret_key")
if os.path.exists(_key_file):
    with open(_key_file) as f: app.secret_key = f.read().strip()
else:
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    with open(_key_file, "w") as f: f.write(app.secret_key)
app.config['TEMPLATES_AUTO_RELOAD'] = True   # always reload templates from disk
# Restrict CORS to localhost and LAN origins only
CORS(app, supports_credentials=True,
     origins=["http://localhost:5000", "http://127.0.0.1:5000",
               r"http://192\.168\.\d+\.\d+:5000",
               r"http://172\.\d+\.\d+\.\d+:5000",
               r"http://10\.\d+\.\d+\.\d+:5000"])

login_manager = LoginManager(app)
login_manager.login_view = "login_page"
login_manager.login_message = "请先登录"

# ── Database ──────────────────────────────────────────────────────────────────
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'operator',
                created_at    TEXT NOT NULL
            )
        """)
        # Future C: robots table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS robots (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                ip         TEXT NOT NULL,
                port       INTEGER NOT NULL DEFAULT 80,
                last_seen  TEXT
            )
        """)
        # Saved SLAM maps (any terrain/site)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS maps (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                width      INTEGER NOT NULL,
                height     INTEGER NOT NULL,
                resolution REAL NOT NULL,
                origin_x   REAL NOT NULL,
                origin_y   REAL NOT NULL,
                data       TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        # Custom waypoints saved from map click
        conn.execute("""
            CREATE TABLE IF NOT EXISTS waypoints (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                x          REAL NOT NULL,
                y          REAL NOT NULL,
                theta      REAL NOT NULL DEFAULT 0.0,
                type       TEXT NOT NULL DEFAULT 'custom',
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()

init_db()

class User(UserMixin):
    def __init__(self, row):
        self.id       = row[0]
        self.username = row[1]
        self.email    = row[2]
        self.role     = row[4]

def get_user_by_id(uid):
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT id,username,email,password_hash,role FROM users WHERE id=?", (uid,)).fetchone()
    return User(row) if row else None

def get_user_by_username(username):
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT id,username,email,password_hash,role FROM users WHERE username=?", (username,)).fetchone()
    return row

def get_user_by_email(email):
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT id,username,email,password_hash,role FROM users WHERE email=?", (email,)).fetchone()
    return row

@login_manager.user_loader
def load_user(uid):
    return get_user_by_id(int(uid))

# ── Auth pages ────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("register.html")

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    d = request.get_json(force=True) or {}
    username = d.get("username", "").strip()
    password = d.get("password", "")
    row = get_user_by_username(username)
    if not row or not check_password_hash(row[3], password):
        return jsonify({"ok": False, "error": "用户名或密码错误"}), 401
    user = User(row)
    login_user(user, remember=d.get("remember", False))
    return jsonify({"ok": True, "username": user.username, "role": user.role})

@app.route("/api/auth/register", methods=["POST"])
def api_register():
    d = request.get_json(force=True) or {}
    username = d.get("username", "").strip()
    email    = d.get("email", "").strip().lower()
    password = d.get("password", "")
    if len(username) < 2:
        return jsonify({"ok": False, "error": "用户名至少2位"}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "error": "密码至少6位"}), 400
    if "@" not in email:
        return jsonify({"ok": False, "error": "邮箱格式错误"}), 400
    if get_user_by_username(username):
        return jsonify({"ok": False, "error": "用户名已存在"}), 409
    if get_user_by_email(email):
        return jsonify({"ok": False, "error": "邮箱已注册"}), 409
    pw_hash = generate_password_hash(password)
    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO users (username,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                     (username, email, pw_hash, "operator", created))
        conn.commit()
    row = get_user_by_username(username)
    login_user(User(row))
    return jsonify({"ok": True, "username": username})

@app.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"ok": True})

@app.route("/api/auth/me", methods=["GET"])
def api_me():
    if current_user.is_authenticated:
        return jsonify({"ok": True, "username": current_user.username, "role": current_user.role})
    return jsonify({"ok": False}), 401

# ── Network scanner ───────────────────────────────────────────────────────────
def _probe_robot(ip, port=80, timeout=0.8):
    """Try GET /reeman/hostname on ip:port. Returns dict or None."""
    try:
        url = f"http://{ip}" if port == 80 else f"http://{ip}:{port}"
        r = requests.get(url + "/reeman/hostname", timeout=timeout)
        if r.status_code == 200:
            data = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
            return {"ip": ip, "port": port, "hostname": data.get("hostname", ip), "online": True}
    except:
        pass
    return None

@app.route("/api/scan", methods=["POST"])
@login_required
def api_scan():
    """Scan current subnet for Reeman robots (port 80, /reeman/hostname)."""
    cfg = load_config()
    if cfg.get("simulation_mode", True):
        return jsonify({"robots": [{"ip": "172.29.19.11", "port": 80,
                                     "hostname": "MoonKnight-SIM", "online": True}]})
    base_ip = cfg.get("robot_ip", "172.29.19.11")
    prefix  = ".".join(base_ip.split(".")[:3])   # e.g. "172.29.19"
    ips     = [f"{prefix}.{i}" for i in range(1, 255)]
    found   = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
        results = ex.map(_probe_robot, ips)
    for r in results:
        if r:
            found.append(r)
    return jsonify({"robots": found, "scanned": len(ips)})


# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "robot_ip": "172.29.19.11",
    "robot_port": 80,
    "linear_speed": 0.3,
    "angular_speed": 0.5,
    "simulation_mode": True,
    "timeout": 5,
    "cmd_interval_ms": 300
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                for k,v in DEFAULT_CONFIG.items(): cfg.setdefault(k,v)
                return cfg
        except: pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def base_url(cfg):
    with _active_lock:
        if _active_robot["ip"]:
            ip, port = _active_robot["ip"], _active_robot["port"]
            return f"http://{ip}" if port == 80 else f"http://{ip}:{port}"
    ip, port = cfg["robot_ip"], cfg.get("robot_port", 80)
    return f"http://{ip}" if port == 80 else f"http://{ip}:{port}"

def rget(cfg, path):
    try:
        r = requests.get(base_url(cfg)+path, timeout=cfg.get("timeout",5))
        r.raise_for_status(); return r.json(), None
    except Exception as e: return None, str(e)

def rpost(cfg, path, body=None):
    try:
        r = requests.post(base_url(cfg)+path, json=body or {}, timeout=cfg.get("timeout",5))
        r.raise_for_status(); return r.json(), None
    except Exception as e: return None, str(e)

def _log(action, ok, msg=""):
    command_log.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "action": action, "ok": ok, "msg": str(msg)[:80],
        "user": current_user.username if current_user.is_authenticated else "?"
    })
    if len(command_log) > 200: command_log.pop(0)

# ── Sim map constants (module-level so nav loop and map func share them) ────
SIM_W, SIM_H   = 100, 80
SIM_RESOLUTION = 0.05
SIM_ORIGIN_X, SIM_ORIGIN_Y = -1.0, -1.0
SIM_LIDAR_R    = 40   # reveal radius in cells (~2m)

def _build_sim_grid():
    W, H = SIM_W, SIM_H
    g = [0] * (W * H)
    def wall(x1,y1,x2,y2):
        for px in range(min(x1,x2), max(x1,x2)+1):
            for py in range(min(y1,y2), max(y1,y2)+1):
                if 0<=px<W and 0<=py<H: g[py*W+px] = 100
    wall(0,0,W-1,0); wall(0,H-1,W-1,H-1)
    wall(0,0,0,H-1); wall(W-1,0,W-1,H-1)
    wall(30,0,30,45); wall(30,55,30,H-1)
    wall(60,20,60,H-1); wall(30,45,50,45)
    wall(10,10,16,16); wall(70,25,76,32); wall(40,55,50,65)
    return g

SIM_GRID = _build_sim_grid()

# ── Simulation state ──────────────────────────────────────────────────────────
sim = {
    "x": 0.0, "y": 0.0, "theta": 0.0,
    "battery": 85, "chargeFlag": 1, "emergencyButton": 1,
    "vx": 0.0, "vth": 0.0,
    "res": 0, "reason": 0, "goal": "", "dist": 0.0, "mileage": 0.0,
    "_nav_goal_x": None, "_nav_goal_y": None, "_nav_goal_theta": 0.0,
    "_mode": 2,                               # 1=mapping, 2=navigation
    "_revealed": bytearray(SIM_W * SIM_H),   # 0=unexplored, 1=seen
}
SIM_WAYPOINTS = [
    {"name": "充电桩",   "type": "charge",   "pose": {"x": 0.0,  "y": 0.0,  "theta": 0.0}},
    {"name": "大厅入口", "type": "delivery", "pose": {"x": 2.5,  "y": 1.0,  "theta": 0.0}},
    {"name": "展厅A",   "type": "delivery", "pose": {"x": 5.0,  "y": 2.0,  "theta": 1.57}},
    {"name": "展厅B",   "type": "delivery", "pose": {"x": 5.0,  "y": -2.0, "theta": -1.57}},
    {"name": "电梯口",  "type": "normal",   "pose": {"x": 8.0,  "y": 0.5,  "theta": 0.0}},
    {"name": "休息区",  "type": "normal",   "pose": {"x": 3.0,  "y": 4.0,  "theta": 3.14}},
]
sim_lock    = threading.Lock()
command_log = []

# ── Active robot (multi-robot switching) ─────────────────────────────────────
_active_robot = {"id": None, "ip": None, "port": 80, "name": "未选择"}
_active_lock  = threading.Lock()

def _reveal_sim(rv, cx, cy):
    """Mark cells within LiDAR radius as revealed (call inside sim_lock)."""
    for dy in range(-SIM_LIDAR_R, SIM_LIDAR_R + 1):
        for dx in range(-SIM_LIDAR_R, SIM_LIDAR_R + 1):
            if dx*dx + dy*dy <= SIM_LIDAR_R*SIM_LIDAR_R:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < SIM_W and 0 <= ny < SIM_H:
                    rv[ny * SIM_W + nx] = 1

def _sim_nav_loop():
    while True:
        time.sleep(0.2)
        with sim_lock:
            mode = sim.get("_mode", 2)

            # ── Mapping mode: apply manual velocity to position ────────────
            if mode == 1 and (abs(sim["vx"]) > 0.01 or abs(sim["vth"]) > 0.01):
                sim["theta"] += sim["vth"] * 0.2
                sim["x"] += sim["vx"] * math.cos(sim["theta"]) * 0.2
                sim["y"] += sim["vx"] * math.sin(sim["theta"]) * 0.2
                sim["mileage"] = round(sim["mileage"] + abs(sim["vx"]) * 0.2, 2)

            # ── Reveal LiDAR scan area in mapping mode ─────────────────────
            if mode == 1:
                px_r = int((sim["x"] - SIM_ORIGIN_X) / SIM_RESOLUTION)
                py_r = int((sim["y"] - SIM_ORIGIN_Y) / SIM_RESOLUTION)
                _reveal_sim(sim["_revealed"], px_r, py_r)

            # ── Auto-navigation (nav mode, res==1 only) ────────────────────
            if sim["res"] != 1: continue
            gx, gy = sim["_nav_goal_x"], sim["_nav_goal_y"]
            if gx is None: continue
            dx, dy = gx - sim["x"], gy - sim["y"]
            dist = math.sqrt(dx*dx + dy*dy)
            sim["dist"] = round(dist, 2)
            if dist < 0.1:
                sim["res"] = 3; sim["reason"] = 0
                sim["vx"] = 0.0; sim["vth"] = 0.0
                sim["_nav_goal_x"] = None; continue
            ta = math.atan2(dy, dx)
            da = ta - sim["theta"]
            while da > math.pi:  da -= 2*math.pi
            while da < -math.pi: da += 2*math.pi
            spd = min(0.4, dist*0.5)
            sim["vth"]  = max(-0.8, min(0.8, da*2.0))
            sim["vx"]   = spd*(1.0 - abs(da)/math.pi)
            sim["theta"] += sim["vth"]*0.2
            sim["x"]    += sim["vx"]*math.cos(sim["theta"])*0.2
            sim["y"]    += sim["vx"]*math.sin(sim["theta"])*0.2
            sim["mileage"] = round(sim["mileage"] + sim["vx"]*0.2, 2)

threading.Thread(target=_sim_nav_loop, daemon=True).start()


# ── Main page ─────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template("index.html", username=current_user.username, role=current_user.role)

@app.route("/mobile")
@login_required
def mobile():
    return render_template("mobile.html", username=current_user.username, role=current_user.role)

@app.route("/api/version")
def api_version():
    """Returns a hash of template+static mtime. Client polls this to detect code changes."""
    import hashlib
    h = hashlib.md5()
    for root in [os.path.join(_BUNDLE_DIR, 'templates'), os.path.join(_BUNDLE_DIR, 'static')]:
        if not os.path.isdir(root):
            continue
        for fname in sorted(os.listdir(root)):
            fp = os.path.join(root, fname)
            if os.path.isfile(fp):
                h.update(str(os.path.getmtime(fp)).encode())
    src = os.path.join(_BUNDLE_DIR, 'server.py')
    if os.path.isfile(src):
        h.update(str(os.path.getmtime(src)).encode())
    return jsonify({"v": h.hexdigest()[:12]})

@app.route("/manifest.json")
def pwa_manifest():
    return send_from_directory(os.path.join(_BUNDLE_DIR, 'static'), 'manifest.json')

@app.route("/sw.js")
def pwa_sw():
    resp = send_from_directory(os.path.join(_BUNDLE_DIR, 'static'), 'sw.js')
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

# ── Config API ────────────────────────────────────────────────────────────────
@app.route("/api/config", methods=["GET"])
@login_required
def api_get_config(): return jsonify(load_config())

@app.route("/api/config", methods=["POST"])
@login_required
def api_set_config():
    if current_user.role not in ("admin", "operator"):
        return jsonify({"ok": False, "error": "权限不足"}), 403
    new_cfg = request.get_json(force=True) or {}
    # Whitelist allowed keys to prevent arbitrary config injection
    allowed = {"robot_ip","robot_port","linear_speed","angular_speed",
               "simulation_mode","timeout","cmd_interval_ms"}
    cfg = load_config()
    for k in allowed:
        if k in new_cfg:
            cfg[k] = new_cfg[k]
    save_config(cfg)
    return jsonify({"ok": True})

# ── Velocity ──────────────────────────────────────────────────────────────────
@app.route("/api/speed", methods=["POST"])
@login_required
def api_speed():
    cfg = load_config()
    d = request.get_json(force=True)
    vx  = float(d.get("vx",  0))
    vth = float(d.get("vth", 0))
    if cfg.get("simulation_mode", True):
        with sim_lock:
            sim["vx"] = vx; sim["vth"] = vth
            if sim["res"] == 1 and (abs(vx)>0.01 or abs(vth)>0.01):
                sim["res"] = 0
        return jsonify({"ok": True, "msg": "SIM"})
    data, err = rpost(cfg, "/cmd/speed", {"vx": vx, "vth": vth})
    ok = err is None
    _log(f"SPEED vx={vx:.2f} vth={vth:.2f}", ok, err or "")
    return jsonify({"ok": ok, "msg": err or "OK"})

# ── Navigation ────────────────────────────────────────────────────────────────
@app.route("/api/nav", methods=["POST"])
@login_required
def api_nav():
    cfg = load_config()
    d = request.get_json(force=True) or {}
    if "x" not in d or "y" not in d:
        return jsonify({"error": "missing required fields: x, y"}), 400
    try:
        x, y, theta = float(d["x"]), float(d["y"]), float(d.get("theta", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "x, y, theta must be numbers"}), 400
    if cfg.get("simulation_mode", True):
        with sim_lock:
            sim["_nav_goal_x"] = x; sim["_nav_goal_y"] = y
            sim["res"] = 1; sim["goal"] = f"({x:.1f},{y:.1f})"; sim["dist"] = 999
        _log(f"NAV→({x:.1f},{y:.1f})", True, "SIM")
        return jsonify({"status": "success"})
    data, err = rpost(cfg, "/cmd/nav", {"x": x, "y": y, "theta": theta})
    ok = err is None
    _log(f"NAV→({x:.1f},{y:.1f})", ok, err or "")
    return jsonify(data or {"error": err})

@app.route("/api/nav_name", methods=["POST"])
@login_required
def api_nav_name():
    cfg = load_config()
    d = request.get_json(force=True)
    point = d.get("point", "")
    if cfg.get("simulation_mode", True):
        wp = next((w for w in SIM_WAYPOINTS if w["name"] == point), None)
        if not wp: return jsonify({"error": f"Point '{point}' not found"})
        with sim_lock:
            sim["_nav_goal_x"] = wp["pose"]["x"]
            sim["_nav_goal_y"] = wp["pose"]["y"]
            sim["res"] = 1; sim["goal"] = point; sim["dist"] = 999
        _log(f"NAV_NAME→{point}", True, "SIM")
        return jsonify({"status": "success"})
    data, err = rpost(cfg, "/cmd/nav_name", {"point": point})
    ok = err is None
    _log(f"NAV_NAME→{point}", ok, err or "")
    return jsonify(data or {"error": err})

@app.route("/api/cancel", methods=["POST"])
@login_required
def api_cancel():
    cfg = load_config()
    if cfg.get("simulation_mode", True):
        with sim_lock:
            sim["res"] = 4; sim["vx"] = 0; sim["vth"] = 0
            sim["_nav_goal_x"] = None
        return jsonify({"status": "success"})
    data, err = rpost(cfg, "/cmd/cancel_goal", {})
    _log("CANCEL", err is None, err or "")
    return jsonify(data or {"error": err})

@app.route("/api/charge", methods=["POST"])
@login_required
def api_charge():
    cfg = load_config()
    d = request.get_json(force=True) or {}
    if cfg.get("simulation_mode", True):
        wp = next((w for w in SIM_WAYPOINTS if w["type"] == "charge"), None)
        if wp:
            with sim_lock:
                sim["_nav_goal_x"] = wp["pose"]["x"]
                sim["_nav_goal_y"] = wp["pose"]["y"]
                sim["res"] = 1; sim["goal"] = wp["name"]
        return jsonify({"status": "success"})
    data, err = rpost(cfg, "/cmd/charge", d)
    return jsonify(data or {"error": err})

@app.route("/api/max_speed", methods=["POST"])
@login_required
def api_max_speed():
    cfg = load_config()
    d = request.get_json(force=True) or {}
    speed = float(d.get("speed", 0.5))
    if cfg.get("simulation_mode", True):
        return jsonify({"status": "success"})
    data, err = rpost(cfg, "/cmd/max_speed", {"speed": speed})
    return jsonify(data or {"error": err})

# ── GET / status ──────────────────────────────────────────────────────────────
@app.route("/api/pose", methods=["GET"])
@login_required
def api_pose():
    cfg = load_config()
    if cfg.get("simulation_mode", True):
        with sim_lock:
            return jsonify({"x": round(sim["x"],3), "y": round(sim["y"],3), "theta": round(sim["theta"],3)})
    data, err = rget(cfg, "/reeman/pose")
    return jsonify(data or {"error": err})

@app.route("/api/battery", methods=["GET"])
@login_required
def api_battery():
    cfg = load_config()
    if cfg.get("simulation_mode", True):
        with sim_lock:
            return jsonify({"battery": sim["battery"], "chargeFlag": sim["chargeFlag"], "emergencyButton": sim["emergencyButton"]})
    data, err = rget(cfg, "/reeman/base_encode")
    return jsonify(data or {"error": err})

@app.route("/api/nav_status", methods=["GET"])
@login_required
def api_nav_status():
    cfg = load_config()
    if cfg.get("simulation_mode", True):
        with sim_lock:
            return jsonify({"res": sim["res"], "reason": sim["reason"],
                            "goal": sim["goal"], "dist": sim["dist"], "mileage": sim["mileage"]})
    data, err = rget(cfg, "/reeman/nav_status")
    return jsonify(data or {"error": err})

@app.route("/api/waypoints", methods=["GET"])
@login_required
def api_waypoints():
    cfg = load_config()
    # Always load local custom waypoints from DB
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT name,x,y,theta,type FROM waypoints ORDER BY id"
        ).fetchall()
    local_wps = [{"name": r[0], "type": r[4], "pose": {"x": r[1], "y": r[2], "theta": r[3]}, "source": "local"}
                 for r in rows]

    if cfg.get("simulation_mode", True):
        merged = SIM_WAYPOINTS + local_wps
        return jsonify({"waypoints": merged})
    data, err = rget(cfg, "/reeman/position")
    if err:
        return jsonify({"error": err, "waypoints": local_wps})
    robot_wps = (data or {}).get("waypoints", [])
    for w in robot_wps:
        w.setdefault("source", "robot")
    return jsonify({"waypoints": robot_wps + local_wps})

@app.route("/api/waypoints/save", methods=["POST"])
@login_required
def api_waypoints_save():
    """Save a custom waypoint from map click to local DB (and optionally push to robot)."""
    d = request.get_json(force=True) or {}
    name  = d.get("name", "").strip()
    x     = float(d.get("x", 0))
    y     = float(d.get("y", 0))
    theta = float(d.get("theta", 0))
    wtype = d.get("type", "custom")
    if not name:
        return jsonify({"ok": False, "error": "名称不能为空"}), 400

    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with sqlite3.connect(DB_FILE) as conn:
            # Upsert: if same name exists, update coords
            existing = conn.execute("SELECT id FROM waypoints WHERE name=?", (name,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE waypoints SET x=?,y=?,theta=?,type=?,created_by=?,created_at=? WHERE name=?",
                    (x, y, theta, wtype, current_user.username, created, name)
                )
            else:
                conn.execute(
                    "INSERT INTO waypoints (name,x,y,theta,type,created_by,created_at) VALUES (?,?,?,?,?,?,?)",
                    (name, x, y, theta, wtype, current_user.username, created)
                )
            conn.commit()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    _log(f"SAVE_WP {name}({x:.2f},{y:.2f})", True, "local DB")

    # If live mode, also push to robot (best-effort)
    cfg = load_config()
    if not cfg.get("simulation_mode", True):
        rpost(cfg, "/cmd/set_point", {"name": name, "x": x, "y": y, "theta": theta})

    return jsonify({"ok": True, "name": name, "x": x, "y": y, "theta": theta})

@app.route("/api/map", methods=["GET"])
@login_required
def api_map():
    cfg = load_config()
    if cfg.get("simulation_mode", True):
        return jsonify(_sim_map())
    data, err = rget(cfg, "/reeman/map")
    return jsonify(data or {"error": err})

@app.route("/api/mode", methods=["GET"])
@login_required
def api_mode():
    cfg = load_config()
    if cfg.get("simulation_mode", True):
        with sim_lock:
            return jsonify({"mode": sim.get("_mode", 2)})
    data, err = rget(cfg, "/reeman/get_mode")
    return jsonify(data or {"error": err})

@app.route("/api/set_mode", methods=["POST"])
@login_required
def api_set_mode():
    """Switch robot between mapping mode (1) and navigation mode (2)."""
    d = request.get_json(force=True) or {}
    mode = int(d.get("mode", 2))
    if mode not in (1, 2):
        return jsonify({"ok": False, "error": "mode must be 1 or 2"}), 400

    cfg = load_config()
    if cfg.get("simulation_mode", True):
        with sim_lock:
            sim["_mode"] = mode
            if mode == 1:
                # Enter mapping: stop navigation, clear fog-of-war (fresh map)
                sim["res"] = 0
                sim["_nav_goal_x"] = None
                sim["_revealed"] = bytearray(SIM_W * SIM_H)
                # Immediately reveal start position
                px_r = int((sim["x"] - SIM_ORIGIN_X) / SIM_RESOLUTION)
                py_r = int((sim["y"] - SIM_ORIGIN_Y) / SIM_RESOLUTION)
                _reveal_sim(sim["_revealed"], px_r, py_r)
        _log(f"SET_MODE {mode}", True, "SIM")
        return jsonify({"ok": True, "mode": mode, "source": "simulation"})

    # Live: Reeman API uses /cmd/set_mode {"mode": 1|2}
    data, err = rpost(cfg, "/cmd/set_mode", {"mode": mode})
    ok = err is None
    _log(f"SET_MODE {mode}", ok, err or "")
    return jsonify({"ok": ok, "mode": mode, "error": err} if not ok else {"ok": True, "mode": mode})

@app.route("/api/current_speed", methods=["GET"])
@login_required
def api_current_speed():
    cfg = load_config()
    if cfg.get("simulation_mode", True):
        with sim_lock:
            return jsonify({"vx": round(sim["vx"],3), "vth": round(sim["vth"],3)})
    data, err = rget(cfg, "/reeman/speed")
    return jsonify(data or {"error": err})

@app.route("/api/status", methods=["GET"])
@login_required
def api_status():
    cfg = load_config()
    if cfg.get("simulation_mode", True):
        with sim_lock:
            return jsonify({
                "ok": True, "source": "simulation",
                "pose":    {"x": round(sim["x"],2), "y": round(sim["y"],2), "theta": round(sim["theta"],2)},
                "battery": sim["battery"], "chargeFlag": sim["chargeFlag"], "emergencyButton": sim["emergencyButton"],
                "speed":   {"vx": round(sim["vx"],2), "vth": round(sim["vth"],2)},
                "nav":     {"res": sim["res"], "reason": sim["reason"],
                            "goal": sim["goal"], "dist": sim["dist"], "mileage": round(sim["mileage"],1)},
                "mode":    2
            })
    def _g(path): return rget(cfg, path)[0] or {}
    with concurrent.futures.ThreadPoolExecutor() as ex:
        fpose = ex.submit(_g, "/reeman/pose")
        fbat  = ex.submit(_g, "/reeman/base_encode")
        fnav  = ex.submit(_g, "/reeman/nav_status")
        fspd  = ex.submit(_g, "/reeman/speed")
        fmode = ex.submit(_g, "/reeman/get_mode")
    bat = fbat.result()
    return jsonify({
        "ok": True, "source": "live",
        "pose":          fpose.result(),
        "battery":       bat.get("battery", "--"),
        "chargeFlag":    bat.get("chargeFlag", 1),
        "emergencyButton": bat.get("emergencyButton", 1),
        "speed":         fspd.result(),
        "nav":           fnav.result(),
        "mode":          fmode.result().get("mode", 2)
    })

@app.route("/api/ping", methods=["GET"])
@login_required
def api_ping():
    cfg = load_config()
    if cfg.get("simulation_mode", True):
        return jsonify({"ok": True, "latency_ms": 0, "mode": "simulation"})
    start = time.time()
    try:
        requests.get(base_url(cfg)+"/reeman/hostname", timeout=2)
        return jsonify({"ok": True, "latency_ms": int((time.time()-start)*1000), "mode": "live"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "mode": "live"})

@app.route("/api/log", methods=["GET"])
@login_required
def api_log():
    return jsonify({"log": list(reversed(command_log[-30:]))})


@app.route("/api/set_pose", methods=["POST"])
@login_required
def api_set_pose():
    """Set robot initial pose for localization (relocalization on known map)."""
    d = request.get_json(force=True) or {}
    x     = float(d.get("x", 0))
    y     = float(d.get("y", 0))
    theta = float(d.get("theta", 0))
    cfg = load_config()
    if cfg.get("simulation_mode", True):
        with sim_lock:
            sim["x"], sim["y"], sim["theta"] = x, y, theta
            sim["vx"], sim["vth"] = 0.0, 0.0
            sim["res"] = 0
            px_r = int((x - SIM_ORIGIN_X) / SIM_RESOLUTION)
            py_r = int((y - SIM_ORIGIN_Y) / SIM_RESOLUTION)
            _reveal_sim(sim["_revealed"], px_r, py_r)
        _log(f"SET_POSE ({x:.2f},{y:.2f})", True, "SIM")
        return jsonify({"ok": True, "source": "simulation"})
    # Real robot: try Reeman relocalization endpoints
    data, err = rpost(cfg, "/cmd/set_initial_pose", {"x": x, "y": y, "theta": theta})
    if err:
        data, err = rpost(cfg, "/cmd/relocalize", {"x": x, "y": y, "theta": theta})
    ok = err is None
    _log(f"SET_POSE ({x:.2f},{y:.2f})", ok, err or "")
    return jsonify({"ok": ok, "error": err} if not ok else {"ok": True})

@app.route("/api/map/new", methods=["POST"])
@login_required
def api_map_new():
    """Reset to a blank editable map (all free space, fully visible, no fog)."""
    global SIM_GRID
    cfg = load_config()
    if not cfg.get("simulation_mode", True):
        return jsonify({"ok": False, "error": "仅支持仿真模式新建地图"}), 400
    with sim_lock:
        SIM_GRID = [0] * (SIM_W * SIM_H)          # all free space
        sim["_mode"] = 1
        sim["_revealed"] = bytearray(b'\x01' * (SIM_W * SIM_H))  # all revealed
        sim["x"] = 0.0; sim["y"] = 0.0; sim["theta"] = 0.0
    _log("NEW_MAP: blank canvas", True, "SIM")
    return jsonify({"ok": True})

@app.route("/api/map/apply_draw", methods=["POST"])
@login_required
def api_apply_draw():
    """Merge user-drawn layer into the simulation grid."""
    d = request.get_json(force=True) or {}
    layer = d.get("layer", [])
    if len(layer) != SIM_W * SIM_H:
        return jsonify({"ok": False, "error": f"layer must be {SIM_W*SIM_H} cells, got {len(layer)}"}), 400
    applied = 0
    with sim_lock:
        for i, v in enumerate(layer):
            if v >= 0:          # -1 = no user data → skip
                SIM_GRID[i] = int(v)
                applied += 1
    _log("DRAW_APPLY", True, f"{applied} cells")
    return jsonify({"ok": True, "applied": applied})

# ── Simulated map ─────────────────────────────────────────────────────────────
def _sim_map():
    origin = {"x": SIM_ORIGIN_X, "y": SIM_ORIGIN_Y}
    with sim_lock:
        mode = sim.get("_mode", 2)
        if mode == 1:
            rv = bytes(sim["_revealed"])   # snapshot under lock
        else:
            rv = None
    if mode == 1:
        # Fog of war: unexplored cells return -1
        data = [SIM_GRID[i] if rv[i] else -1 for i in range(SIM_W * SIM_H)]
        fog = True
    else:
        data = list(SIM_GRID)
        fog = False
    return {"width": SIM_W, "height": SIM_H, "resolution": SIM_RESOLUTION,
            "origin": origin, "data": data, "fog": fog}


# ── Map save / library ────────────────────────────────────────────────────────
@app.route("/api/map/save", methods=["POST"])
@login_required
def api_map_save():
    """Save current map snapshot to DB with a name."""
    d = request.get_json(force=True) or {}
    name = d.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "error": "地图名称不能为空"}), 400

    cfg = load_config()
    if cfg.get("simulation_mode", True):
        m = _sim_map()
    else:
        m, err = rget(cfg, "/reeman/map")
        if err or not m:
            return jsonify({"ok": False, "error": err or "无法获取地图"}), 500

    created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data_json = json.dumps(m["data"])
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.execute(
                "INSERT INTO maps (name,width,height,resolution,origin_x,origin_y,data,created_by,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (name, m["width"], m["height"], m["resolution"],
                 m["origin"]["x"], m["origin"]["y"],
                 data_json, current_user.username, created)
            )
            map_id = cur.lastrowid
            conn.commit()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    _log(f"MAP_SAVE '{name}'", True, f"id={map_id}")
    return jsonify({"ok": True, "id": map_id, "name": name,
                    "width": m["width"], "height": m["height"]})


@app.route("/api/maps", methods=["GET"])
@login_required
def api_maps_list():
    """List all saved maps (without data payload)."""
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT id,name,width,height,resolution,created_by,created_at FROM maps ORDER BY id DESC"
        ).fetchall()
    maps = [{"id":r[0],"name":r[1],"width":r[2],"height":r[3],
              "resolution":r[4],"created_by":r[5],"created_at":r[6]} for r in rows]
    return jsonify({"maps": maps})


@app.route("/api/maps/<int:map_id>", methods=["GET"])
@login_required
def api_map_load(map_id):
    """Load a saved map (full data)."""
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            "SELECT id,name,width,height,resolution,origin_x,origin_y,data,created_by,created_at "
            "FROM maps WHERE id=?", (map_id,)
        ).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "id": row[0], "name": row[1],
        "width": row[2], "height": row[3], "resolution": row[4],
        "origin": {"x": row[5], "y": row[6]},
        "data": json.loads(row[7]),
        "created_by": row[8], "created_at": row[9]
    })


@app.route("/api/maps/<int:map_id>", methods=["DELETE"])
@login_required
def api_map_delete(map_id):
    """Delete a saved map."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM maps WHERE id=?", (map_id,))
        conn.commit()
    _log(f"MAP_DELETE id={map_id}", True, "")
    return jsonify({"ok": True})


# ── Robot management ──────────────────────────────────────────────────────────
@app.route("/api/robots", methods=["GET"])
@login_required
def api_robots_list():
    with sqlite3.connect(DB_FILE) as conn:
        rows = conn.execute(
            "SELECT id,name,ip,port,last_seen FROM robots ORDER BY id"
        ).fetchall()
    robots = [{"id":r[0],"name":r[1],"ip":r[2],"port":r[3],"last_seen":r[4]} for r in rows]
    with _active_lock:
        active_id = _active_robot["id"]
    return jsonify({"robots": robots, "active_id": active_id})

@app.route("/api/robots", methods=["POST"])
@login_required
def api_robots_add():
    d = request.get_json(force=True) or {}
    name = d.get("name", "").strip()
    ip   = d.get("ip", "").strip()
    port = int(d.get("port", 80))
    if not name or not ip:
        return jsonify({"ok": False, "error": "name and ip required"}), 400
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.execute(
            "INSERT INTO robots (name,ip,port,last_seen) VALUES (?,?,?,?)",
            (name, ip, port, ts)
        )
        robot_id = cur.lastrowid
        conn.commit()
    return jsonify({"ok": True, "id": robot_id, "name": name, "ip": ip, "port": port})

@app.route("/api/robots/<int:robot_id>", methods=["DELETE"])
@login_required
def api_robots_delete(robot_id):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM robots WHERE id=?", (robot_id,))
        conn.commit()
    with _active_lock:
        if _active_robot["id"] == robot_id:
            _active_robot.update({"id": None, "ip": None, "port": 80, "name": "未选择"})
    return jsonify({"ok": True})

@app.route("/api/robots/active", methods=["GET"])
@login_required
def api_robots_get_active():
    with _active_lock:
        return jsonify({"ok": True, **_active_robot})

@app.route("/api/robots/active", methods=["POST"])
@login_required
def api_robots_set_active():
    d = request.get_json(force=True) or {}
    robot_id = d.get("id")
    if robot_id is None:
        with _active_lock:
            _active_robot.update({"id": None, "ip": None, "port": 80, "name": "未选择"})
        return jsonify({"ok": True, "name": "未选择"})
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute(
            "SELECT id,name,ip,port FROM robots WHERE id=?", (robot_id,)
        ).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Robot not found"}), 404
    with _active_lock:
        _active_robot.update({"id": row[0], "name": row[1], "ip": row[2], "port": row[3]})
    _log(f"SWITCH_ROBOT→{row[1]}({row[2]})", True, "")
    return jsonify({"ok": True, "id": row[0], "name": row[1], "ip": row[2], "port": row[3]})


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dev', action='store_true', help='Enable hot-reload dev mode')
    args = parser.parse_args()
    dev = args.dev or os.environ.get('ROBOT_DEV', '').lower() in ('1', 'true')
    print("="*55)
    print(f"  Reeman Moon Knight 2.0 — {'DEV' if dev else 'PROD'}")
    print("  访问: http://localhost:5000")
    print("="*55)
    app.run(host="0.0.0.0", port=5000, debug=dev, use_reloader=dev)
