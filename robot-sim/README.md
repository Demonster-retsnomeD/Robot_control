# Robot Simulation — Path Network & Task Dispatch System

完全自包含的单文件HTML5应用。多机器人路径网络仿真系统，支持用户绘制路径、任务分配、自动调度。

**在线演示：** https://robot-sim-iota.vercel.app

---

## 功能

### 核心
- **路径绘制编辑模式**：用鼠标绘制弯曲路线，自动保存到localStorage
- **3机器人仿真**：红/蓝/青色机器人，各自独立速度（1-20 m/s）
- **默认轮巡**：机器人在启动时自动A↔B往返
- **任务分配**：点击C、D、E等呼叫点，最近的空闲机器人出发服务
- **粘性分配**：已分配的呼叫点再次点击，继续用同一机器人
- **3秒服务**：机器人到达目标点停留3秒后返回轮巡

### 状态机
**机器人：** `patrolMode` (轮巡) ↔ 服务 + 返回
**呼叫点：** idle → pending → assigned → idle

---

## 使用

### 第一步：绘制路径

1. 点"✏️ 编辑路径"进入编辑模式
2. 点击关键点A（绿圆，左边）开始
3. 拖鼠标绘制弯曲路线到B（橙圆，右边）
4. 点B完成，或点"💾 保存"
5. 重复绘制B→C、C→D、D→E等路径，形成链
6. 最后点"✅ 完成编辑"

**重要：** 路径必须连接（B是第一条的终点，也是第二条的起点），否则Dijkstra找不到跨路径的路由。

### 第二步：启动仿真

1. 点"▶️ 开始"
2. 观察机器人沿A→B→A→...往返
3. 等待5-10秒让机器人运动稳定

### 第三步：呼叫任务

机器人运动中，点"📍 呼叫C"、"📍 呼叫D"等：
- 最近的机器人停止轮巡，沿路径网络前往目标
- 到达后停留3秒（服务时间）
- 然后返回轮巡路径，继续A↔B

**再次呼叫同一点：** 若机器人还在服务/返回，重复呼叫继续用同一机器人；若已完成，选择距离最近的新机器人。

### 第四步：手动调速

右侧"⚙️ 控制"中有三个输入框，可设置每个机器人速度（1-20 m/s）。

---

## 路径网络结构

**localStorage中的pathNetwork：**
```javascript
pathNetwork = {
  "A-B": [{x,y}, {x,y}, ...],   // 点坐标数组
  "B-C": [{x,y}, {x,y}, ...],
  ...
}
```

路径自动拆分为15点/段，便于处理。

**Dijkstra图节点：**
- 关键点：A, B, C, D, E（坐标±2px内）
- 伪标签：`"(x,y)"`（路径中间的坐标）

任务分配时用Dijkstra找最短路径，然后getFullPath()拼接完整坐标。

---

## 机器人状态机

### 轮巡模式
```
robot.patrolMode = true
→ 调用startDefaultShuttle()
→ 设置robot.path = A-B全路径副本
→ 计算robot.pathProgress（当前位置对应的0-1进度）
→ 每帧pathProgress += speed/pathLen * dt
→ pathProgress >= 1时反序路径，pathProgress = 0
```

### 服务模式
```
robot.patrolMode = false
robot.serviceTarget = 'C'   // 目标点
robot.path = [从robot当前位置 → C的完整坐标]
robot.pathProgress = 0

→ 沿robot.path运动
→ 到达(pathProgress >= 1)
→ 切换为returning状态
  → robot.returning = true
  → 计算C→A的返回路径
  → 沿返回路径运动
  → 到达A后
    → robot.patrolMode = true
    → robot.returning = false
    → 重新启动A↔B轮巡
```

---

## 关键算法

### getPositionOnPath(path, progress)
根据pathProgress和实际路径长度计算机器人精确坐标（线性插值）。

### findShortestPath(start, end)
Dijkstra算法。节点为所有路径的起终点，边为相邻路径段。返回标签数组。

### getFullPath(nodeRoute)
将Dijkstra返回的标签数组转换为完整坐标数组。拼接多条路径段，去重相邻重复点。

### findPathBetweenPoints(startLabel, endLabel)
在pathNetwork中找包含startLabel→endLabel的连续子路径。支持伪标签和关键点。

---

## 调试

### 浏览器控制台
- `Object.keys(pathNetwork)` — 查看已保存路径数
- `robots` — 所有机器人对象
- `callStates` — 呼叫点状态机
- 日志前缀：`[呼叫]`、`[机器人]`、`[Dijkstra]` 等

### 常见问题

**机器人不动？**
- A-B路径是否存在 → 编辑模式检查是否有路径
- getDefaultABPath()是否找到 → 确保A点和B点位置正确

**呼叫无反应？**
- callStates是否初始化 → 点"▶️ 开始"后应自动初始化
- Dijkstra找不到路径 → pathNetwork路径未连接

**机器人瞬移？**
- fullPath第一个点是否为robot当前位置 → 任务分配时必须添加
- pathProgress计算是否正确 → startDefaultShuttle()中estimatedProgress

---

## 部署

### 本地测试
双击 `path-network.html` 打开（无需服务器）。

### Vercel部署
```bash
cd robot-sim
git add path-network.html
git commit -m "..."
git push origin master
```

自动构建到 https://robot-sim-iota.vercel.app

---

## 技术栈

- **HTML5 Canvas** — 绘图和可视化
- **原生JavaScript** — 无框架
- **localStorage** — 路径持久化
- **Dijkstra算法** — 路由计算

---

## 文件

- `path-network.html` — 完整应用（~1700行）
  - Canvas绘图模块（编辑、删除、显示）
  - 路径保存和加载（localStorage）
  - Dijkstra寻路（带缓存）
  - 机器人仿真引擎（状态机、动画）
  - UI面板（速度、呼叫按钮）

---

## 最后更新

**2026-05-26**
- ✅ 机器人状态机完成（轮巡+服务+返回）
- ✅ 呼叫点状态机实现（粘性分配+距离选择）
- ✅ 瞬移修复（pathProgress初始化、路径起点验证）
- ✅ 任务分配算法（Dijkstra+getFullPath+粘性预留）

---

## License

MIT
