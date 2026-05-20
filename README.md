# Reeman Moon Knight 2.0 — Robot Control System

Web-based control panel for Reeman Moon Knight 2.0 robot. Built with Flask + SLAM Web API.

## Quick Start

### Requirements
- Python 3.8+
- Same WiFi network as the robot (or simulation mode)

### Install & Run

**Windows (double-click):**
```
启动.bat
```

**Manual:**
```bash
pip install -r requirements.txt
python server.py
```

Access at: **http://localhost:5000**

### Network Access (same WiFi)

When the server is running, anyone on the same WiFi can access:
```
http://[your-machine-ip]:5000
```
Your machine IP is shown in the terminal on startup.

## Configuration

Edit `config.json`:

```json
{
  "robot_ip": "172.29.19.11",
  "robot_port": 80,
  "linear_speed": 0.3,
  "angular_speed": 0.5,
  "simulation_mode": true,
  "timeout": 5,
  "cmd_interval_ms": 300
}
```

- `simulation_mode: true` — runs without real robot (for testing)
- `simulation_mode: false` — connects to real robot at `robot_ip`
- `robot_ip` — robot's IP address (connect to robot's WiFi hotspot first)

## Features

- Login / Register system
- Real-time robot status (pose, battery, speed, nav state)
- Map visualization with waypoints
- Navigation by name or coordinates
- Manual speed control (WASD)
- Mapping mode / Navigation mode toggle
- Command history log
- Network scanner for robot discovery

## Robot Connection

1. Connect your machine to the robot's WiFi hotspot
2. Set `simulation_mode: false` in config.json
3. Set `robot_ip` to the robot's IP (default: `172.29.19.11`)
4. Restart server
