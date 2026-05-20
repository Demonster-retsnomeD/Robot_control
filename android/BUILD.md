# Android APK 构建说明

## 需要安装
- [Android Studio](https://developer.android.com/studio)（免费）

## 构建步骤

1. 打开 Android Studio
2. File → Open → 选择这个 `android/` 文件夹
3. 等待 Gradle 同步完成（首次约5分钟，需联网下载依赖）
4. Build → Build Bundle(s) / APK(s) → Build APK(s)
5. APK 生成在 `app/build/outputs/apk/debug/app-debug.apk`

## 安装到手机

```
# 方法1：USB连接手机，用adb安装
adb install app/build/outputs/apk/debug/app-debug.apk

# 方法2：把apk文件复制到手机，手机端直接安装（需开启"允许未知来源"）
```

## 首次使用

1. 打开 App，输入电脑的 IP 地址
2. 点击连接（电脑须已启动 `启动.bat`）
3. 长按屏幕 → 可修改 IP / 刷新页面

## 查电脑 IP 的方法

电脑启动控制台后，窗口会显示：
```
手机访问: http://192.168.x.x:5000/mobile
```
输入那个 IP 即可。
