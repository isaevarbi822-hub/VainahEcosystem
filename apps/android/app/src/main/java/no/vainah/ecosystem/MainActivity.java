package no.vainah.ecosystem;

import android.app.Activity;
import android.Manifest;
import android.content.pm.PackageManager;
import android.webkit.PermissionRequest;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.SslErrorHandler;
import android.net.http.SslError;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

public final class MainActivity extends Activity {
    private WebView webView;
    private LinearLayout errorView;
    private boolean connectionFailed = false;
    private static final int FILE_PICKER_REQUEST = 1401;
    private static final int MICROPHONE_REQUEST = 1402;
    private PermissionRequest pendingMediaPermission;
    private String[] pendingMediaResources;
    private ValueCallback<Uri[]> fileChooserCallback;
    private final String homeUrl = BuildConfig.VAINAH_BASE_URL + BuildConfig.VAINAH_START_PATH;
    private final Uri trustedUri = Uri.parse(BuildConfig.VAINAH_BASE_URL);

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(10, 16, 28));
        getWindow().setNavigationBarColor(Color.rgb(10, 16, 28));
        FrameLayout root = new FrameLayout(this);
        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(9, 14, 24));
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true); // required by our first-party application UI
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);
        webView.setWebChromeClient(new WebChromeClient() {
            @Override public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> {
                    Uri origin = request.getOrigin();
                    if (!sameOrigin(origin)) { request.deny(); return; }
                    java.util.ArrayList<String> needs = new java.util.ArrayList<>();
                    for (String requested : request.getResources()) {
                        if (PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(requested)) {
                            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED)
                                needs.add(Manifest.permission.RECORD_AUDIO);
                        } else if (PermissionRequest.RESOURCE_VIDEO_CAPTURE.equals(requested)) {
                            if (checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED)
                                needs.add(Manifest.permission.CAMERA);
                        } else { request.deny(); return; }
                    }
                    if (needs.isEmpty()) request.grant(request.getResources());
                    else {
                        if (pendingMediaPermission != null) pendingMediaPermission.deny();
                        pendingMediaPermission = request;
                        pendingMediaResources = request.getResources();
                        requestPermissions(needs.toArray(new String[0]), MICROPHONE_REQUEST);
                    }
                });
            }
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileChooserCallback != null) fileChooserCallback.onReceiveValue(null);
                fileChooserCallback = callback;
                Intent choose = new Intent(Intent.ACTION_GET_CONTENT);
                choose.addCategory(Intent.CATEGORY_OPENABLE);
                choose.setType("*/*");
                choose.putExtra(Intent.EXTRA_MIME_TYPES, new String[] {"image/jpeg", "image/png", "image/gif", "image/webp", "audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4", "audio/webm"});
                try {
                    startActivityForResult(Intent.createChooser(choose, "Выберите файл Vainah"), FILE_PICKER_REQUEST);
                    return true;
                } catch (ActivityNotFoundException exc) {
                    fileChooserCallback = null;
                    callback.onReceiveValue(null);
                    return false;
                }
            }
        });
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (!request.isForMainFrame()) return false;
                Uri url = request.getUrl();
                if (sameOrigin(url)) return false;
                if ("https".equals(url.getScheme()) || "http".equals(url.getScheme())) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, url)); }
                    catch (ActivityNotFoundException ignored) { }
                }
                return true;
            }
            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                connectionFailed = false;
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) { connectionFailed = true; showError(); }
            }
            @Override public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError error) {
                handler.cancel(); // Never bypass invalid HTTPS certificates
                connectionFailed = true;
                showError();
            }
            @Override public void onPageFinished(WebView view, String url) {
                CookieManager.getInstance().flush();
                if (!connectionFailed && sameOrigin(Uri.parse(url))) errorView.setVisibility(View.GONE);
            }
        });
        root.addView(webView, new FrameLayout.LayoutParams(-1, -1));
        errorView = makeErrorView();
        errorView.setVisibility(View.GONE);
        root.addView(errorView, new FrameLayout.LayoutParams(-1, -1));
        setContentView(root);
        webView.loadUrl(homeUrl);
    }

    private boolean sameOrigin(Uri uri) {
        if (uri == null) return false;
        int port = uri.getPort();
        int expectedPort = trustedUri.getPort();
        return trustedUri.getScheme().equalsIgnoreCase(uri.getScheme())
            && trustedUri.getHost().equalsIgnoreCase(uri.getHost()) && port == expectedPort;
    }

    private LinearLayout makeErrorView() {
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER);
        layout.setPadding(40, 40, 40, 40);
        layout.setBackgroundColor(Color.rgb(9, 14, 24));
        TextView heading = new TextView(this);
        heading.setText("Vainah пока не подключён");
        heading.setTextSize(25);
        heading.setTextColor(Color.WHITE);
        layout.addView(heading);
        TextView note = new TextView(this);
        note.setText("Для USB-разработки запустите Vainah API на компьютере и выполните adb reverse tcp:8000 tcp:8000. Для публикации требуется HTTPS-сервер.");
        note.setTextColor(Color.rgb(163, 180, 208));
        note.setTextSize(15);
        note.setPadding(0, 22, 0, 30);
        layout.addView(note);
        Button retry = new Button(this);
        retry.setText("Повторить подключение");
        retry.setOnClickListener(v -> { errorView.setVisibility(View.GONE); webView.loadUrl(homeUrl); });
        layout.addView(retry);
        return layout;
    }

    private void showError() { runOnUiThread(() -> { if (errorView != null) errorView.setVisibility(View.VISIBLE); }); }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grants) {
        super.onRequestPermissionsResult(requestCode, permissions, grants);
        if (requestCode == MICROPHONE_REQUEST && pendingMediaPermission != null) {
            boolean allGranted = grants.length > 0;
            for (int grant : grants) if (grant != PackageManager.PERMISSION_GRANTED) allGranted = false;
            if (allGranted) pendingMediaPermission.grant(pendingMediaResources);
            else pendingMediaPermission.deny();
            pendingMediaPermission = null;
            pendingMediaResources = null;
        }
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == FILE_PICKER_REQUEST && fileChooserCallback != null) {
            Uri[] uris = resultCode == RESULT_OK && data != null && data.getData() != null
                ? new Uri[] { data.getData() } : null;
            fileChooserCallback.onReceiveValue(uris);
            fileChooserCallback = null;
        }
    }

    @Override public void onBackPressed() {
        if (errorView.getVisibility() == View.VISIBLE) { errorView.setVisibility(View.GONE); webView.loadUrl(homeUrl); }
        else if (webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (webView != null) { webView.destroy(); webView = null; }
        super.onDestroy();
    }
}
