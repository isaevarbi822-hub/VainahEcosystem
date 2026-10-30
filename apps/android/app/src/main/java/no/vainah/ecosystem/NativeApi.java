package no.vainah.ecosystem;

import android.app.Activity;
import android.net.Uri;
import android.database.Cursor;
import android.provider.OpenableColumns;
import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import org.json.JSONObject;

import java.io.InputStream;
import java.io.File;
import java.io.FileOutputStream;
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
    public interface MediaCallback {
        void complete(File file, String error);
    }
    private static final long MAX_MEDIA = 20L * 1024 * 1024;

    private final Activity activity;
    private final String origin;
    private final ExecutorService queue = Executors.newSingleThreadExecutor();
    private final ExecutorService mediaQueue = Executors.newFixedThreadPool(2);
    private volatile String cookie = "";
    private volatile String csrf = "";
    private static final String KEY_ALIAS = "vainah-native-session-v1";

    public NativeApi(Activity activity, String origin) {
        this.activity = activity;
        this.origin = origin.replaceAll("/+$", "");
        restore();
    }

    /** Apple OAuth handoff: code is verified on the server and proof remains in Android. */
    public String baseUrl() { return origin; }

    public boolean hasSession() { return !cookie.isEmpty(); }
    public String liveCookie() { return cookie; }

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
                        // Never persist unrelated proxy/application cookies as an auth session.
                        if (pair.startsWith("vainah_session=") && !pair.endsWith("=")
                                && !pair.contains("\\n") && !pair.contains("\\r")) cookie = pair;
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


    /** Bounded multipart upload; file content never enters a JSON string or public URL. */
    public void uploadAttachment(String contactId, boolean group, Uri uri, String desiredFilename,
                                 String contentType, Callback callback) {
        uploadAttachment(contactId,group,uri,desiredFilename,contentType,
                java.util.UUID.randomUUID().toString(),callback);
    }

    public void uploadAttachment(String contactId, boolean group, Uri uri, String desiredFilename,
                                 String contentType, String uploadId, Callback callback) {
        mediaQueue.execute(() -> {
            HttpURLConnection conn=null;
            JSONObject result=new JSONObject();
            String error=null;
            try {
                if (!contactId.matches("[a-fA-F0-9-]{36}") || cookie.isEmpty())
                    throw new IllegalArgumentException("Требуется авторизация");
                long size=-1;
                try (Cursor info=activity.getContentResolver().query(uri,
                        new String[]{OpenableColumns.SIZE},null,null,null)) {
                    if(info!=null && info.moveToFirst())
                        size=info.getLong(0);
                } catch(Exception ignored) { }
                if(size>MAX_MEDIA)
                    throw new IllegalArgumentException("Файл больше 20 МБ");
                String filename=desiredFilename.replaceAll("[^\\p{L}\\p{N}._ -]","_");
                if(filename.isEmpty())filename="media.bin";
                filename=filename.substring(0,Math.min(filename.length(),130));
                String mime=contentType==null?"application/octet-stream":
                        contentType.replaceAll("[^a-zA-Z0-9/+.\\-]","");
                String boundary="vainah-"+java.util.UUID.randomUUID();
                String route=group?
                    "/api/messenger/v2/groups/"+contactId+"/send-file":
                    "/api/messenger/v2/send-file";
                conn=(HttpURLConnection)new URL(origin+route).openConnection();
                conn.setRequestMethod("POST");conn.setConnectTimeout(12000);
                conn.setReadTimeout(45000);conn.setInstanceFollowRedirects(false);
                conn.setDoOutput(true);conn.setChunkedStreamingMode(16384);
                conn.setRequestProperty("Accept","application/json");
                conn.setRequestProperty("Origin",origin);
                conn.setRequestProperty("Cookie",cookie);
                conn.setRequestProperty("X-CSRF-Token",csrf);
                conn.setRequestProperty("Content-Type","multipart/form-data; boundary="+boundary);
                conn.setRequestProperty("X-Upload-Id", uploadId);
                try(OutputStream out=conn.getOutputStream();
                    InputStream input=activity.getContentResolver().openInputStream(uri)){
                    if(input==null)throw new IllegalArgumentException("Невозможно прочитать файл");
                    if(!group)out.write(("--"+boundary+"\r\nContent-Disposition: form-data; name=\"contact_id\"\r\n\r\n"+
                            contactId+"\r\n").getBytes(StandardCharsets.UTF_8));
                    out.write(("--"+boundary+"\r\nContent-Disposition: form-data; name=\"file\"; filename=\""+
                            filename+"\"\r\nContent-Type: "+mime+"\r\n\r\n").getBytes(StandardCharsets.UTF_8));
                    byte[] block=new byte[16384];
                    long total=0;int n;
                    while((n=input.read(block))!=-1){
                        total+=n;
                        if(total>MAX_MEDIA)throw new IllegalArgumentException("Файл больше 20 МБ");
                        out.write(block,0,n);
                    }
                    out.write(("\r\n--"+boundary+"--\r\n").getBytes(StandardCharsets.UTF_8));
                }
                int status=conn.getResponseCode();
                try(InputStream input=(status>=400?conn.getErrorStream():conn.getInputStream())){
                    if(input!=null){
                        ByteArrayOutputStream buffer=new ByteArrayOutputStream();
                        byte[] data=new byte[4096];int n;
                        while((n=input.read(data))!=-1){
                            buffer.write(data,0,n);
                            if(buffer.size()>1000000)throw new IllegalArgumentException("Ошибка сервера слишком велика");
                        }
                        if(buffer.size()>0)result=new JSONObject(buffer.toString("UTF-8"));
                    }
                }
                if(status==401){clear();error="Сессия завершена. Войдите снова.";}
                else if(status<200 || status>=300) {
                    error=result.optString("detail","Сервер отклонил вложение: "+status);
                    if(status==413)error="Файл слишком большой для сервера (максимум 20 МБ).";
                    else if(status==415)error="Этот формат файла не поддерживается сервером.";
                    else if(status==429)error="Слишком много отправок. Повторите немного позже.";
                    else if(status>=500)error="Ошибка сервера ("+status+"). Проверьте чат перед повторной отправкой.";
                }
            }catch(Exception ex){
                error=ex instanceof IllegalArgumentException?ex.getMessage():
                    "Не удалось подтвердить отправку. Проверьте чат перед повторной попыткой, чтобы избежать дубликата.";
            }finally{if(conn!=null)conn.disconnect();}
            JSONObject response=result;String failure=error;
            activity.runOnUiThread(()->callback.complete(response,failure));
        });
    }

    /** Authenticated attachment download into a temporary private cache file. */
    public void fetchAttachment(String path, MediaCallback callback) {
        mediaQueue.execute(()->{
            HttpURLConnection conn=null;
            File file=null;String error=null;
            try {
                if(!path.matches("(/api/messenger/v2/file/[a-fA-F0-9-]{36}|/api/messenger/v2/groups/[a-fA-F0-9-]{36}/file/[a-fA-F0-9-]{36})") || cookie.isEmpty())
                    throw new IllegalArgumentException("Недоступный файл");
                conn=(HttpURLConnection)new URL(origin+path).openConnection();
                conn.setRequestMethod("GET");conn.setConnectTimeout(12000);
                conn.setReadTimeout(30000);conn.setInstanceFollowRedirects(false);
                conn.setRequestProperty("Cookie",cookie);
                conn.setRequestProperty("Accept","*/*");
                int status=conn.getResponseCode();
                if(status!=200)throw new IllegalArgumentException("Файл недоступен ("+status+")");
                file=File.createTempFile("vainah-preview-",".bin",activity.getCacheDir());
                try(InputStream in=conn.getInputStream();
                    FileOutputStream out=new FileOutputStream(file)){
                    byte[] block=new byte[16384];int count;long length=0;
                    while((count=in.read(block))!=-1){
                        length+=count;
                        if(length>MAX_MEDIA)throw new IllegalArgumentException("Файл превышает лимит");
                        out.write(block,0,count);
                    }
                }
            }catch(Exception ex){
                error=ex instanceof IllegalArgumentException?ex.getMessage():
                    "Не удалось загрузить вложение";
                if(file!=null){file.delete();file=null;}
            }finally{if(conn!=null)conn.disconnect();}
            File delivered=file;String failure=error;
            activity.runOnUiThread(()->callback.complete(delivered,failure));
        });
    }

    public void close() { queue.shutdownNow();mediaQueue.shutdownNow(); }
}
