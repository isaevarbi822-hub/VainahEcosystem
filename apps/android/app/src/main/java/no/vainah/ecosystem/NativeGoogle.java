package no.vainah.ecosystem;

import android.app.Activity;
import android.os.CancellationSignal;

import androidx.annotation.NonNull;
import androidx.credentials.CredentialManager;
import androidx.credentials.CredentialManagerCallback;
import androidx.credentials.CustomCredential;
import androidx.credentials.GetCredentialRequest;
import androidx.credentials.GetCredentialResponse;
import androidx.credentials.exceptions.GetCredentialCancellationException;
import androidx.credentials.exceptions.GetCredentialException;

import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption;
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential;

/** Native system Google account picker. Never displays Google in an embedded WebView. */
public final class NativeGoogle {
    public interface Callback {
        void onToken(String idToken);
        void onError(String error);
    }

    public static boolean configured() {
        return BuildConfig.VAINAH_GOOGLE_WEB_CLIENT_ID.endsWith(".apps.googleusercontent.com");
    }

    public static void signIn(Activity activity, Callback callback) {
        if (!configured()) {
            callback.onError("Для входа через Google настройте VAINAH_GOOGLE_WEB_CLIENT_ID в GitHub Variables и пересоберите APK.");
            return;
        }
        try {
            GetSignInWithGoogleOption option = new GetSignInWithGoogleOption.Builder(
                    BuildConfig.VAINAH_GOOGLE_WEB_CLIENT_ID).build();
            GetCredentialRequest request = new GetCredentialRequest.Builder()
                    .addCredentialOption(option).build();
            CredentialManager.create(activity).getCredentialAsync(
                    activity, request, new CancellationSignal(), activity.getMainExecutor(),
                    new CredentialManagerCallback<GetCredentialResponse, GetCredentialException>() {
                        @Override public void onResult(@NonNull GetCredentialResponse result) {
                            if (!(result.getCredential() instanceof CustomCredential)) {
                                callback.onError("Google вернул неподдерживаемые данные входа.");
                                return;
                            }
                            CustomCredential credential = (CustomCredential) result.getCredential();
                            if (!GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL.equals(credential.getType())) {
                                callback.onError("Google не предоставил ID-токен.");
                                return;
                            }
                            try {
                                callback.onToken(GoogleIdTokenCredential.createFrom(
                                        credential.getData()).getIdToken());
                            } catch (Exception e) {
                                callback.onError("Не удалось прочитать подтверждение Google.");
                            }
                        }
                        @Override public void onError(@NonNull GetCredentialException e) {
                            if (e instanceof GetCredentialCancellationException) return;
                            callback.onError("Не удалось открыть Google-вход. Проверьте OAuth Android Client (package и SHA-1).");
                        }
                    });
        } catch (Exception e) {
            callback.onError("Google-вход недоступен на этом устройстве.");
        }
    }
}
