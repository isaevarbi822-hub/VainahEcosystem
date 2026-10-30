package no.vainah.ecosystem;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import org.json.JSONObject;

import java.io.InputStream;
import java.io.OutputStream;
import java.io.ByteArrayOutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.SecureRandom;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * Native Messenger HTTP API. Never loads HTML or a WebView.
 * The backend still supplies remote messages and authenticates Google ID tokens.
 * Session cookies are encrypted with an Android Keystore AES-GCM key before saving.
 */
public final class NativeApi {
    public interface Callback {
        void complete(JSONObject response, String error);
    }

    private final Activity activity;
    private final String origin;
    private final ExecutorService queue = Executors.newSingleThreadExecutor();
    private String cookie = "";
    private String csrf = "";
    private static final String KEY_ALIAS = "vainah-native-session-v1";

    public NativeApi(Activity activity, String origin) {
        this.activity = activity;
        this.origin = origin.replaceAll("/+$", "");
        restore();
    }

    /** Apple OAuth handoff: code is verified on the server and proof remains in Android. */
    public String baseUrl() { return origin; }

    public boolean hasSession() { return !cookie.isEmpty(); }

    private SecretKey secretKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(KEY_ALIAS)) return ((KeyStore.SecretKeyEntry) store.getEntry(KEY_ALIAS, null)).getSecretKey();
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build());
        return generator.generateKey();
    }

    private void store() {
        try {
            JSONObject state = new JSONObject();
            state.put("cookie", cookie);
            state.put("csrf", csrf);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, secretKey(), new SecureRandom());
            byte[] encrypted = cipher.doFinal(state.toString().getBytes(StandardCharsets.UTF_8));
            byte[] iv = cipher.getIV();
            byte[] combined = new byte[iv.length + encrypted.length];
            System.arraycopy(iv, 0, combined, 0, iv.length);
            System.arraycopy(encrypted, 0, combined, iv.length, encrypted.length);
            activity.getSharedPreferences("vainah-native", Context.MODE_PRIVATE).edit()
                    .putString("credentials", Base64.encodeToString(combined, Base64.NO_WRAP)).apply();
        } catch (Exception ignored) {
            // Use current in-memory session if Android Keystore is unavailable.
        }
    }

    private void restore() {
        try {
            SharedPreferences preferences = activity.getSharedPreferences("vainah-native", Context.MODE_PRIVATE);
            String saved = preferences.getString("credentials", "");
            if (saved.isEmpty()) return;
            byte[] raw = Base64.decode(saved, Base64.DEFAULT);
            if (raw.length < 29) throw new IllegalArgumentException("Invalid session");
            byte[] iv = new byte[12];
            System.arraycopy(raw, 0, iv, 0, iv.length);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, secretKey(), new GCMParameterSpec(128, iv));
            byte[] plain = cipher.doFinal(raw, iv.length, raw.length - iv.length);
            JSONObject state = new JSONObject(new String(plain, StandardCharsets.UTF_8));
            cookie = state.optString("cookie", "");
            csrf = state.optString("csrf", "");
        } catch (Exception ignored) { clear(); }
    }

    public void clear() {
        cookie = "";
        csrf = "";
        activity.getSharedPreferences("vainah-native", Context.MODE_PRIVATE).edit().remove("credentials").apply();
    }

    public void call(String method, String path, JSONObject payload, Callback callback) {
        queue.execute(() -> {
            HttpURLConnection connection = null;
            JSONObject result = new JSONObject();
            String error = null;
            try {
                if (!path.startsWith("/") || path.startsWith("//") || path.contains("://"))
                    throw new IllegalArgumentException("Invalid API path");
                connection = (HttpURLConnection) new URL(origin + path).openConnection();
                connection.setConnectTimeout(12000);
                connection.setReadTimeout(16000);
                connection.setRequestMethod(method);
                connection.setInstanceFollowRedirects(false);
                connection.setRequestProperty("Accept", "application/json");
                connection.setRequestProperty("Origin", origin);
                if (!cookie.isEmpty()) connection.setRequestProperty("Cookie", cookie);
                if (!csrf.isEmpty() && !"GET".equals(method))
                    connection.setRequestProperty("X-CSRF-Token", csrf);
                if (payload != null) {
                    connection.setDoOutput(true);
                    connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                    byte[] bytes = payload.toString().getBytes(StandardCharsets.UTF_8);
                    try (OutputStream output = connection.getOutputStream()) { output.write(bytes); }
                }
                int status = connection.getResponseCode();
                InputStream input = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
                if (input != null) {
                    try (InputStream stream = input; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                        byte[] block = new byte[4096];
                        int n;
                        while ((n = stream.read(block)) >= 0) {
                            out.write(block, 0, n);
                            if (out.size() > 1_000_000) throw new IllegalStateException("API response too large");
                        }
                        String body = out.toString("UTF-8");
                        if (!body.isEmpty()) result = new JSONObject(body);
                    }
                }
                if (status >= 200 && status < 300) {
                    String setCookie = connection.getHeaderField("Set-Cookie");
                    if (setCookie != null && setCookie.contains("=")) {
                        String pair = setCookie.split(";", 2)[0];
                        if (pair.matches("[A-Za-z0-9_\\-]+=[^;]*") && !pair.endsWith("=")) cookie = pair;
                    }
                    if (result.has("csrf_token")) csrf = result.optString("csrf_token", "");
                    if (!cookie.isEmpty()) store();
                } else if (status == 401) {
                    clear();
                    error = result.optString("detail", "Сессия истекла. Войдите снова.");
                } else {
                    Object detail = result.opt("detail");
                    error = detail instanceof String ? (String) detail : "Сервер ответил: " + status;
                }
            } catch (Exception e) {
                error = "Не удалось связаться с API Vainah. Проверьте подключение и адрес сервера.";
            } finally {
                if (connection != null) connection.disconnect();
            }
            final JSONObject finalResult = result;
            final String finalError = error;
            activity.runOnUiThread(() -> callback.complete(finalResult, finalError));
        });
    }

    public void close() { queue.shutdownNow(); }
}
