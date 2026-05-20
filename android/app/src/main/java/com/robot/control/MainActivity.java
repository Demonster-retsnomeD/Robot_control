package com.robot.control;

import android.annotation.SuppressLint;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.*;
import android.widget.*;
import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private SharedPreferences prefs;
    private static final String PREF_IP = "server_ip";
    private static final int PORT = 5000;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Full-screen immersive
        getWindow().setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        );
        getWindow().getDecorView().setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION |
            View.SYSTEM_UI_FLAG_FULLSCREEN |
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        );

        prefs = getSharedPreferences("robot_prefs", MODE_PRIVATE);
        String savedIp = prefs.getString(PREF_IP, null);

        if (savedIp == null) {
            showIpDialog(null);
        } else {
            setupWebView(savedIp);
        }
    }

    private void showIpDialog(String current) {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("连接设置");
        builder.setMessage("输入电脑的 IP 地址（电脑与手机需在同一WiFi）");

        final EditText input = new EditText(this);
        input.setHint("例如: 192.168.1.100");
        input.setText(current != null ? current : "");
        input.setPadding(48, 24, 48, 24);
        builder.setView(input);

        builder.setPositiveButton("连接", (dialog, which) -> {
            String ip = input.getText().toString().trim();
            if (ip.isEmpty()) {
                Toast.makeText(this, "请输入IP地址", Toast.LENGTH_SHORT).show();
                showIpDialog(current);
                return;
            }
            prefs.edit().putString(PREF_IP, ip).apply();
            setupWebView(ip);
        });

        if (current != null) {
            builder.setNegativeButton("取消", null);
        } else {
            builder.setCancelable(false);
        }

        builder.show();
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebView(String ip) {
        webView = new WebView(this);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request,
                                        WebResourceError error) {
                if (request.isForMainFrame()) {
                    String errorPage = "<html><body style='background:#0f172a;color:#94a3b8;"
                        + "font-family:sans-serif;text-align:center;padding:40px'>"
                        + "<h2 style='color:#ef4444'>无法连接</h2>"
                        + "<p>无法连接到 " + ip + ":" + PORT + "</p>"
                        + "<p>请确认：<br>① 电脑已启动机器人控制台<br>"
                        + "② 手机与电脑在同一WiFi<br>"
                        + "③ IP地址正确</p>"
                        + "<button onclick='location.reload()' style='margin-top:20px;"
                        + "padding:12px 24px;background:#0ea5e9;color:white;"
                        + "border:none;border-radius:8px;font-size:16px'>重试</button>"
                        + "<br><br><button onclick='Android.changeIp()' style='padding:10px 20px;"
                        + "background:#334155;color:#94a3b8;border:none;border-radius:8px;"
                        + "font-size:14px'>修改IP地址</button>"
                        + "</body></html>";
                    view.loadDataWithBaseURL(null, errorPage, "text/html", "UTF-8", null);
                }
            }
        });

        webView.addJavascriptInterface(new Object() {
            @android.webkit.JavascriptInterface
            public void changeIp() {
                runOnUiThread(() -> showIpDialog(prefs.getString(PREF_IP, "")));
            }
        }, "Android");

        webView.loadUrl("http://" + ip + ":" + PORT + "/mobile");
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView != null && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    // Long-press anywhere to show IP change option
    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus && webView != null) {
            webView.setOnLongClickListener(v -> {
                new AlertDialog.Builder(this)
                    .setTitle("设置")
                    .setItems(new String[]{"修改服务器IP", "刷新页面"}, (d, which) -> {
                        if (which == 0) showIpDialog(prefs.getString(PREF_IP, ""));
                        else webView.reload();
                    }).show();
                return true;
            });
        }
    }
}
