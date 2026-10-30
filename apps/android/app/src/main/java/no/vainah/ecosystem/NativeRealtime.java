package no.vainah.ecosystem;

import android.os.Handler;
import android.os.Looper;
import org.json.JSONObject;
import java.util.concurrent.TimeUnit;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/**
 * Authenticated foreground live channel. Never embeds a session in a URL.
 * Handles disconnections with bounded retry and leaves periodic REST fallback.
 * This is NOT background push messaging.
 */
public final class NativeRealtime {
    public interface Events {
        void onEvent(JSONObject message);
    }
    private final Handler main = new Handler(Looper.getMainLooper());
    private final OkHttpClient client = new OkHttpClient.Builder()
            .pingInterval(25, TimeUnit.SECONDS)
            .connectTimeout(12, TimeUnit.SECONDS).build();
    private final String origin;
    private final Events events;
    private WebSocket socket;
    private boolean desired = false;
    private int retryCount = 0;
    private String sessionCookie = "";
    private Runnable pendingRetry;
    private long generation = 0;

    public NativeRealtime(String origin, Events events) {
        this.origin = origin.replaceAll("/+$", "");
        this.events = events;
    }

    public void start(String cookie) {
        if (cookie == null || !cookie.startsWith("vainah_session=")) return;
        if (desired && cookie.equals(sessionCookie)) return;
        stop();
        desired = true;
        sessionCookie = cookie;
        retryCount = 0;
        connect(++generation);
    }

    private void connect(long epoch) {
        if (!desired || epoch != generation) return;
        String address = origin.replaceFirst("^https://", "wss://") +
                "/api/messenger/v2/live";
        if (!address.startsWith("wss://")) return;
        Request request = new Request.Builder().url(address)
                .header("Origin", origin)
                .header("Cookie", sessionCookie)
                .build();
        socket = client.newWebSocket(request, new WebSocketListener() {
            @Override public void onOpen(WebSocket ws, Response response) {
                main.post(() -> {
                    if (epoch == generation) retryCount = 0;
                    else ws.close(1000, "stale");
                });
            }
            @Override public void onMessage(WebSocket ws, String text) {
                main.post(() -> {
                    if (!desired || epoch != generation || text.length() > 16384) return;
                    try { events.onEvent(new JSONObject(text)); }
                    catch (Exception ignored) { /* malformed live event */ }
                });
            }
            @Override public void onClosed(WebSocket ws, int code, String reason) {
                main.post(() -> {
                    // Policy rejection usually means expired authentication; don't retry.
                    if (code != 1008) retry(epoch);
                });
            }
            @Override public void onFailure(WebSocket ws, Throwable cause, Response response) {
                main.post(() -> {
                    if (response != null && (response.code() == 401 ||
                            response.code() == 403)) return;
                    retry(epoch);
                });
            }
        });
    }

    private void retry(long epoch) {
        if (!desired || epoch != generation || pendingRetry != null) return;
        int delay = Math.min(30_000, 1_000 * (1 << Math.min(5, retryCount++)));
        pendingRetry = () -> {
            pendingRetry = null;
            connect(epoch);
        };
        main.postDelayed(pendingRetry, delay);
    }

    public void stop() {
        generation++;
        desired = false;
        sessionCookie = "";
        if (pendingRetry != null) main.removeCallbacks(pendingRetry);
        pendingRetry = null;
        if (socket != null) {
            socket.close(1000, "background");
            socket = null;
        }
    }

    public void close() {
        stop();
        client.connectionPool().evictAll();
        client.dispatcher().executorService().shutdown();
    }
}
