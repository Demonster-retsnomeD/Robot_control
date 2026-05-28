# 代码执行流程完整分析

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│ 主循环：requestAnimationFrame(animate)                       │
│ 每帧调用：updateRobots(dt) → drawMap()                     │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
    [任务处理]           [机器人运动]
        │                     │
        ▼                     ▼
```

---

## 1. 初始化阶段

### 1.1 机器人初始状态

```javascript
const robots = {
  1: { x: 10, y: 35, speed: 5, color: '#ef4444', status: 'idle', ... },
  2: { x: 60, y: 35, speed: 10, color: '#3b82f6', status: 'idle', ... },
  3: { x: 10, y: 35, speed: 3, color: '#06b6d4', status: 'idle', ... }
};
```

- **位置：** 三个机器人初始在 (10,35), (60,35), (10,35)
- **速度：** 5, 10, 3 m/s
- **状态：** 'idle' / 'moving' / 'serving'
- **路径：** robot.path 存储坐标数组，robot.pathProgress 存储进度 0-1

### 1.2 路径网络初始化

```javascript
let pathNetwork = {};
// 从 localStorage 加载：localStorage.getItem('pathNetwork')
```

每条路径格式：
```
pathNetwork['key'] = [{x,y}, {x,y}, ..., {x,y}]
```

**关键：当前自动拆分后，key 格式变成：**
```
"(10,35)-(20,40)_1779773128654_0.5432"
"(20,40)-(30,48)_1779773128655_0.2341"
...
```

---

## 2. 主运动循环：updateRobots(dt)

### 2.1 任务分配阶段

```javascript
for (const task of taskQueue) {
  if (task.status === 'pending') {
    assignTask(task);  // 只分配一次
  }
}
```

**入口：** taskQueue 中有 pending 任务  
**调用：** assignTask(task)  
**结果：** 任务状态变成 'assigned'，某个机器人被赋予路径

### 2.2 机器人位置更新

```javascript
for (const [id, robot] of Object.entries(robots)) {
  if (robot.status === 'moving' && robot.path) {
    // 计算速度缩放因子
    const speed = robot.speed / getPathLength(robot.path);
    // 更新进度 (0 → 1)
    robot.pathProgress += speed * dt;

    if (robot.pathProgress >= 1) {
      // 到达终点
      if (robot.isDefaultShuttle) {
        // 默认A↔B往返：反向路径
        robot.path.reverse();
        robot.pathProgress = 0;
      } else {
        // 任务完成：切换到serving状态
        robot.status = 'serving';
        robot.currentTask.arrivalTime = time;
      }
    } else {
      // 路径中间：更新坐标
      const pos = getPositionOnPath(robot.path, robot.pathProgress);
      robot.x = pos.x;
      robot.y = pos.y;
    }
  }
}
```

**关键数值：**
- `speed` = 机器人速度 / 路径总长度 (m·frame^-1)
- `pathProgress` = 路径上的进度（0=起点, 1=终点）
- 坐标计算：线性插值沿着路径

### 2.3 服务状态处理

```javascript
if (robot.status === 'serving' && robot.currentTask) {
  const serviceElapsed = time - robot.currentTask.arrivalTime;
  if (serviceElapsed >= 3.0) {  // 3秒服务时间
    robot.status = 'idle';
    robot.currentTask.status = 'completed';
    startDefaultShuttle(robot);  // 恢复A↔B往返
  }
}
```

### 2.4 默认往返启动

```javascript
const hasPendingTasks = taskQueue.some(t => t.status !== 'completed');

if (!hasPendingTasks) {
  for (const [id, robot] of Object.entries(robots)) {
    if (robot.status === 'idle' && !robot.path) {
      startDefaultShuttle(robot);
    }
  }
}
```

如果没有待处理任务，空闲机器人启动 A-B 往返。

---

## 3. 呼叫触发机制

### 3.1 UI按钮点击

```html
<button onclick="generateTaskAtPoint('C')">📍 呼叫C</button>
<button onclick="generateTaskAtPoint('D')">📍 呼叫D</button>
<button onclick="generateTaskAtPoint('E')">📍 呼叫E</button>
```

### 3.2 generateTaskAtPoint(label) 函数

```javascript
function generateTaskAtPoint(label) {  // label = 'C' / 'D' / 'E'
  if (!isRunning) {
    alert('请先启动仿真');
    return;
  }

  // 诊断输出
  console.log(`[pathNetwork内容] 共${Object.keys(pathNetwork).length}条路径`);
  console.log(`[机器人当前位置]`);
  for (const [id, robot] of Object.entries(robots)) {
    console.log(`  机器人${id}: (${robot.x}, ${robot.y}) 状态=${robot.status}`);
  }

  // 创建任务
  taskQueue.push({
    id: Math.random(),
    target: label,           // 目标点：C / D / E
    status: 'pending',       // 待分配
    assignedRobot: null,
    arrivalTime: null,
    serviceTime: 3           // 3秒服务时间
  });
}
```

**流程：**
1. 检查 isRunning（仿真是否启动）
2. 输出诊断日志
3. 创建 task 对象，push 到 taskQueue
4. **关键：下一帧的 updateRobots() 会检测到这个 pending 任务**

---

## 4. 任务分配：assignTask(task)

### 4.1 目标验证

```javascript
const targetPt = keyPoints[task.target];  // 例：C = {x:30, y:20}
if (!targetPt) {
  console.error(`目标${task.target}不是有效关键点`);
  return;
}
```

### 4.2 机器人选择

```javascript
// 遍历所有机器人，计算直线距离
for (const [id, robot] of Object.entries(robots)) {
  // 跳过：正在执行其他任务的机器人
  if (robot.status === 'moving' && robot.currentTask) continue;

  // 检测机器人当前位置
  const posInfo = getRobotCurrentPosition(robot);
  const currentPosLabel = posInfo.label;  // 'A' / 'B' / '(x,y)' 等

  // 计算直线距离
  const dx = targetPt.x - robot.x;
  const dy = targetPt.y - robot.y;
  const directDist = Math.sqrt(dx * dx + dy * dy);

  console.log(`  机器人${id} [${posType}:${currentPosLabel}] → ${task.target}: 距离=${directDist}`);

  // 选择最短的
  if (directDist < bestDist) {
    bestDist = directDist;
    bestRobot = parseInt(id);
    bestRobotPos = currentPosLabel;
  }
}
```

**输出示例：**
```
机器人1 (32.1,35.0) [路径上:(10,35)] → C: 直线距离=16.5
机器人2 (45.3,35.0) [关键点:B] → C: 直线距离=22.7
机器人3 (10.2,35.0) [关键点:A] → C: 直线距离=28.3
✓ 机器人1：目前最优（距离16.5）
```

### 4.3 路由计算

```javascript
const pathNodes = findShortestPath(bestRobotPos, task.target);
// 例：["(10,35)", "(20,40)", "C"]  <- 小路径段连接

let fullPath = getFullPath(pathNodes);
// 例：[{x,y}, {x,y}, ..., {x:30,y:20}]  <- 完整坐标列表

console.log(`[任务${task.target}] 机器人${bestRobot} | 
  起点:${bestRobotPos} | 
  路径节点:${pathNodes} | 
  完整路径${fullPath.length}个点`);
```

**Dijkstra 用途：**
- 输入：`bestRobotPos`（当前位置标签）, `task.target`（目标标签）
- 输出：中间节点列表
- 图的节点：小路径段的起点/终点
- 图的边：相邻的小路径段

### 4.4 路径设置

```javascript
if (fullPath && fullPath.length > 1) {
  robots[bestRobot].path = fullPath;         // 坐标数组
  robots[bestRobot].pathProgress = 0;        // 进度重置为0
  robots[bestRobot].status = 'moving';       // 状态变成moving
  robots[bestRobot].isDefaultShuttle = false;
  robots[bestRobot].currentTask = task;
  task.assignedRobot = bestRobot;
  task.status = 'assigned';
  
  console.log(`✅ 分配成功！机器人${bestRobot}，经过${pathNodes.length}个小路径`);
} else {
  console.log(`❌ 路径不完整（节点:${pathNodes}），无法到达`);
}
```

---

## 5. 位置检测：getRobotCurrentPosition(robot)

### 5.1 检测优先级

```
优先级1：是否接近关键点（<3 pixels）
  ✓ 返回关键点标签 'A' / 'B' / 'C'
  
优先级2：是否在某条保存的路径上
  ✓ 返回该路径的起点标签（或伪标签）
  
优先级3：默认返回最近的关键点
```

### 5.2 关键点检测

```javascript
let closestKeyPoint = null;
let minDistToKeyPoint = Infinity;

for (const [key, pt] of Object.entries(keyPoints)) {
  const dist = Math.sqrt((robot.x - pt.x)² + (robot.y - pt.y)²);
  if (dist < minDistToKeyPoint) {
    closestKeyPoint = key;
    minDistToKeyPoint = dist;
  }
}

if (minDistToKeyPoint < 3) {
  return { label: closestKeyPoint, type: 'keypoint', dist: minDistToKeyPoint };
}
```

### 5.3 路径上检测

```javascript
for (const [pathKey, pathPoints] of Object.entries(pathNetwork)) {
  for (let i = 0; i < pathPoints.length; i++) {
    const pt = pathPoints[i];
    const dist = Math.sqrt((robot.x - pt.x)² + (robot.y - pt.y)²);
    
    if (dist < minDistToPath) {
      minDistToPath = dist;
      closestPath = pathPoints;
      
      // 获取路径起点标签
      const startPt = pathPoints[0];
      // ... 匹配关键点或创建伪标签
    }
  }
}

if (closestPath) {
  return {
    label: pathStartLabel,
    type: 'path',
    dist: minDistToPath
  };
}
```

---

## 6. 路径保存自动拆分

### 6.1 用户绘制路径

用户点击 A → 拖曲线 → 点 C → 自动保存

### 6.2 自动拆分逻辑（savePath时触发）

```javascript
const fullPath = [...currentEditPath, keyPoints[hitPoint]];
const segmentSize = 15;  // 每段最多15个点

for (let i = 0; i < fullPath.length - 1; i += segmentSize) {
  const endIdx = Math.min(i + segmentSize + 1, fullPath.length);
  const segment = fullPath.slice(i, endIdx);

  const startPt = segment[0];
  const endPt = segment[segment.length - 1];
  // key 格式：(x1,y1)-(x2,y2)_timestamp_random
  const segKey = `(${startPt.x}-(${endPt.x})_${Date.now()}_${Math.random()}`;

  pathNetwork[segKey] = segment;  // 保存小段
}
```

**结果示例：**
```
原路径：A(10,35) → ... → C(30,20) [100个点]

拆分后：
  "(10,35)-(20,40)_1779773128654_0.5432": [15个点]
  "(20,40)-(32,48)_1779773128655_0.2341": [15个点]
  "(32,48)-(30,20)_1779773128656_0.1234": [10个点]
```

---

## 问题排查清单

### ❓ 机器人不动？
- [ ] isRunning === true？
- [ ] pathNetwork 有路径吗？（控制台检查 Object.keys(pathNetwork)）
- [ ] 路径有至少2个点吗？

### ❓ 呼叫没反应？
- [ ] taskQueue 中有 pending 任务吗？（在 updateRobots 中检查）
- [ ] assignTask 被调用了吗？（看控制台日志）
- [ ] fullPath 为空吗？（说明 Dijkstra 找不到路径）

### ❓ 机器人走错路？
- [ ] getRobotCurrentPosition 返回的标签正确吗？
- [ ] findShortestPath 返回的节点是否连通？
- [ ] getFullPath 是否正确将节点转换为坐标？

---

## 关键变量

| 变量 | 含义 | 范围 |
|------|------|------|
| `robot.x, robot.y` | 机器人屏幕坐标 | 0-700 |
| `robot.pathProgress` | 沿路径的进度 | 0-1 |
| `robot.path` | 路径坐标数组 | [...] |
| `robot.status` | 机器人状态 | idle/moving/serving |
| `pathNetwork[key]` | 单条小路径 | [{x,y}, ...] |
| `taskQueue` | 待处理任务 | [...] |
| `isRunning` | 仿真运行中？ | true/false |

---

## 调试命令

```javascript
// 查看路径网络结构
Object.keys(pathNetwork).slice(0, 5).forEach(k => 
  console.log(`${k}: ${pathNetwork[k].length}点`)
);

// 查看机器人当前状态
Object.entries(robots).forEach(([id, r]) => {
  const pos = getRobotCurrentPosition(r);
  console.log(`机器人${id}: (${r.x.toFixed(1)},${r.y.toFixed(1)}) [${pos.label}]`);
});

// 手动测试 Dijkstra
const nodes = findShortestPath('(10,35)', 'C');
console.log('路径节点:', nodes);

// 查看任务队列
console.log(taskQueue);
```

