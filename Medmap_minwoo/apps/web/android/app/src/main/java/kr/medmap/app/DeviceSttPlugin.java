package kr.medmap.app;

import android.content.Intent;
import android.media.AudioFormat;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;
import android.speech.RecognitionListener;
import android.speech.RecognitionSupport;
import android.speech.RecognitionSupportCallback;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.util.Base64;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.FileOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Android's on-device speech recognizer for live captions and the first transcript (docs/ANDROID_APP.md).
 * createOnDeviceSpeechRecognizer never falls back to a server, unlike the plain SpeechRecognizer; it was
 * checked in airplane mode. The app records the microphone itself and writes the same audio here (start / push /
 * stop), so turbo can verify exactly what the recognizer heard. Needs Android 13 to take audio from the app.
 * recognize() feeds a whole recording at speaking speed for the comparison benchmark.
 */
@CapacitorPlugin(name = "DeviceStt")
public class DeviceSttPlugin extends Plugin {
    private final Handler main = new Handler(Looper.getMainLooper());

    // The live session: one at a time. Recognizer calls happen on the main thread, audio writes on `writer`.
    private final ExecutorService writer = Executors.newSingleThreadExecutor();
    private SpeechRecognizer live;
    private FileOutputStream liveInput;
    private final ArrayList<String> committed = new ArrayList<>();
    private PluginCall stopCall;
    private boolean liveDone;
    private Integer liveError;

    private Intent intent() {
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ko-KR");
        intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        return intent;
    }

    /** Whether Korean can be recognized on the device, and whether its model is installed. */
    @PluginMethod
    public void support(PluginCall call) {
        if (Build.VERSION.SDK_INT < 33) {
            call.reject("Android 13 이상이 필요합니다.");
            return;
        }
        main.post(() -> {
            boolean available = SpeechRecognizer.isOnDeviceRecognitionAvailable(getContext());
            if (!available) {
                JSObject result = new JSObject();
                result.put("onDeviceAvailable", false);
                call.resolve(result);
                return;
            }
            SpeechRecognizer recognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(getContext());
            recognizer.checkRecognitionSupport(intent(), Executors.newSingleThreadExecutor(), new RecognitionSupportCallback() {
                @Override
                public void onSupportResult(RecognitionSupport support) {
                    JSObject result = new JSObject();
                    result.put("onDeviceAvailable", true);
                    result.put("installed", new JSArray(support.getInstalledOnDeviceLanguages()));
                    result.put("pending", new JSArray(support.getPendingOnDeviceLanguages()));
                    result.put("supported", new JSArray(support.getSupportedOnDeviceLanguages()));
                    result.put("online", new JSArray(support.getOnlineLanguages()));
                    main.post(recognizer::destroy);
                    call.resolve(result);
                }

                @Override
                public void onError(int error) {
                    main.post(recognizer::destroy);
                    call.reject("지원 언어 확인 실패: " + error);
                }
            });
        });
    }

    /** Asks the device to download the on-device Korean model (it may show a system prompt). */
    @PluginMethod
    public void download(PluginCall call) {
        main.post(() -> {
            SpeechRecognizer recognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(getContext());
            recognizer.triggerModelDownload(intent());
            main.postDelayed(recognizer::destroy, 1000);
            call.resolve();
        });
    }

    /**
     * Recognizes 16 kHz mono 16-bit PCM ("pcm16", base64), written into the recognizer at real speaking speed
     * when "realtime" is true. Returns every partial result with the time it arrived, measured from the start of
     * the audio, and how long the final result took after the last sample was written.
     */
    @PluginMethod
    public void recognize(PluginCall call) {
        if (Build.VERSION.SDK_INT < 33) {
            call.reject("Android 13 이상이 필요합니다.");
            return;
        }
        byte[] pcm = Base64.decode(call.getString("pcm16", ""), Base64.DEFAULT);
        boolean realtime = call.getBoolean("realtime", true);
        main.post(() -> {
            ParcelFileDescriptor[] pipe;
            try {
                pipe = ParcelFileDescriptor.createPipe();
            } catch (IOException error) {
                call.reject("파이프를 만들지 못했습니다: " + error.getMessage());
                return;
            }
            SpeechRecognizer recognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(getContext());
            JSArray partials = new JSArray();
            ArrayList<String> segments = new ArrayList<>();
            long[] audioStart = {0};
            long[] audioEnd = {0};
            boolean[] done = {false};

            Runnable finish = () -> {
                if (done[0]) return;
                done[0] = true;
                JSObject result = new JSObject();
                result.put("partials", partials);
                result.put("final", String.join(" ", segments));
                result.put("audio_seconds", pcm.length / 32000.0);
                result.put("final_after_end", audioEnd[0] == 0 ? -1 : (SystemClock.elapsedRealtime() - audioEnd[0]) / 1000.0);
                recognizer.destroy();
                call.resolve(result);
            };

            recognizer.setRecognitionListener(new RecognitionListener() {
                private double since() {
                    return (SystemClock.elapsedRealtime() - audioStart[0]) / 1000.0;
                }

                private void partial(Bundle bundle) {
                    ArrayList<String> texts = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                    if (texts == null || texts.isEmpty()) return;
                    JSObject item = new JSObject();
                    item.put("t", since());
                    item.put("text", texts.get(0));
                    partials.put(item);
                }

                @Override public void onReadyForSpeech(Bundle params) {}
                @Override public void onBeginningOfSpeech() {}
                @Override public void onRmsChanged(float rmsdB) {}
                @Override public void onBufferReceived(byte[] buffer) {}
                @Override public void onEndOfSpeech() {}
                @Override public void onEvent(int eventType, Bundle params) {}

                @Override
                public void onPartialResults(Bundle bundle) {
                    partial(bundle);
                }

                @Override
                public void onSegmentResults(Bundle bundle) {
                    ArrayList<String> texts = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                    if (texts != null && !texts.isEmpty()) segments.add(texts.get(0));
                }

                @Override
                public void onEndOfSegmentedSession() {
                    finish.run();
                }

                @Override
                public void onResults(Bundle bundle) {
                    ArrayList<String> texts = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                    if (texts != null && !texts.isEmpty()) segments.add(texts.get(0));
                    finish.run();
                }

                @Override
                public void onError(int error) {
                    if (done[0]) return;
                    done[0] = true;
                    recognizer.destroy();
                    call.reject("기기 음성 인식 오류 " + error);
                }
            });

            Intent intent = intent();
            intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE, pipe[0]);
            intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_CHANNEL_COUNT, 1);
            intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_ENCODING, AudioFormat.ENCODING_PCM_16BIT);
            intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_SAMPLING_RATE, 16000);
            // A long recording is one session cut into segments at pauses, not ended at the first pause.
            intent.putExtra(RecognizerIntent.EXTRA_SEGMENTED_SESSION, RecognizerIntent.EXTRA_AUDIO_SOURCE);
            recognizer.startListening(intent);

            ParcelFileDescriptor writeEnd = pipe[1];
            Executors.newSingleThreadExecutor().execute(() -> {
                audioStart[0] = SystemClock.elapsedRealtime();
                try (FileOutputStream out = new ParcelFileDescriptor.AutoCloseOutputStream(writeEnd)) {
                    int chunk = 3200; // 100 ms
                    for (int offset = 0; offset < pcm.length; offset += chunk) {
                        out.write(pcm, offset, Math.min(chunk, pcm.length - offset));
                        if (realtime) {
                            long due = audioStart[0] + (offset + chunk) / 32;
                            long wait = due - SystemClock.elapsedRealtime();
                            if (wait > 0) SystemClock.sleep(wait);
                        }
                    }
                    // From here the final result is timed: the last sample of the recording has been written.
                    audioEnd[0] = SystemClock.elapsedRealtime();
                    // Silence after the last word, at speaking speed, then end of input.
                    for (int i = 0; i < 20; i++) {
                        out.write(new byte[3200]);
                        if (realtime) SystemClock.sleep(100);
                    }
                } catch (IOException ignored) {
                    // The recognizer closed its end early; the listener reports what it got.
                }
            });
            main.postDelayed(finish, (long) (pcm.length / 32.0) + 30_000); // never hang the test
        });
    }

    private Intent audioIntent(ParcelFileDescriptor source) {
        Intent intent = intent();
        intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE, source);
        intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_CHANNEL_COUNT, 1);
        intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_ENCODING, AudioFormat.ENCODING_PCM_16BIT);
        intent.putExtra(RecognizerIntent.EXTRA_AUDIO_SOURCE_SAMPLING_RATE, 16000);
        // A long recording is one session cut into segments at pauses, not ended at the first pause.
        intent.putExtra(RecognizerIntent.EXTRA_SEGMENTED_SESSION, RecognizerIntent.EXTRA_AUDIO_SOURCE);
        return intent;
    }

    /** Starts a live session. Captions arrive as "caption" events: {text} = finished segments + current guess. */
    @PluginMethod
    public void start(PluginCall call) {
        if (Build.VERSION.SDK_INT < 33) {
            call.reject("Android 13 이상이 필요합니다.");
            return;
        }
        main.post(() -> {
            closeLive();
            ParcelFileDescriptor[] pipe;
            try {
                pipe = ParcelFileDescriptor.createPipe();
            } catch (IOException error) {
                call.reject("파이프를 만들지 못했습니다: " + error.getMessage());
                return;
            }
            committed.clear();
            stopCall = null;
            liveDone = false;
            liveError = null;
            liveInput = new ParcelFileDescriptor.AutoCloseOutputStream(pipe[1]);
            live = SpeechRecognizer.createOnDeviceSpeechRecognizer(getContext());
            SpeechRecognizer session = live;
            session.setRecognitionListener(new RecognitionListener() {
                private String first(Bundle bundle) {
                    ArrayList<String> texts = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                    return texts == null || texts.isEmpty() ? "" : texts.get(0).trim();
                }

                private void caption(String current) {
                    ArrayList<String> parts = new ArrayList<>(committed);
                    if (!current.isEmpty()) parts.add(current);
                    JSObject event = new JSObject();
                    event.put("text", String.join(" ", parts));
                    notifyListeners("caption", event);
                }

                @Override public void onReadyForSpeech(Bundle params) {}
                @Override public void onBeginningOfSpeech() {}
                @Override public void onRmsChanged(float rmsdB) {}
                @Override public void onBufferReceived(byte[] buffer) {}
                @Override public void onEndOfSpeech() {}
                @Override public void onEvent(int eventType, Bundle params) {}

                @Override
                public void onPartialResults(Bundle bundle) {
                    if (session == live) caption(first(bundle));
                }

                @Override
                public void onSegmentResults(Bundle bundle) {
                    if (session != live) return;
                    String text = first(bundle);
                    if (!text.isEmpty()) committed.add(text);
                    caption("");
                }

                @Override
                public void onEndOfSegmentedSession() {
                    if (session == live) finishLive(null);
                }

                @Override
                public void onResults(Bundle bundle) {
                    if (session != live) return;
                    String text = first(bundle);
                    if (!text.isEmpty()) committed.add(text);
                    finishLive(null);
                }

                @Override
                public void onError(int error) {
                    // "No match" just means the last stretch had no words; keep what was recognized.
                    if (session == live) finishLive(error == SpeechRecognizer.ERROR_NO_MATCH ? null : error);
                }
            });
            session.startListening(audioIntent(pipe[0]));
            call.resolve();
        });
    }

    /** Writes the next stretch of 16 kHz mono 16-bit PCM ("pcm16", base64) into the live session. */
    @PluginMethod
    public void push(PluginCall call) {
        byte[] pcm = Base64.decode(call.getString("pcm16", ""), Base64.DEFAULT);
        FileOutputStream input = liveInput;
        writer.execute(() -> {
            try {
                if (input != null) input.write(pcm);
            } catch (IOException ignored) {
                // The session already ended; stop() reports what was recognized.
            }
        });
        call.resolve();
    }

    /** Ends the input and resolves with the whole transcript once the recognizer has finished. */
    @PluginMethod
    public void stop(PluginCall call) {
        FileOutputStream input = liveInput;
        writer.execute(() -> {
            try {
                if (input != null) input.close();
            } catch (IOException ignored) {
                // Already closed.
            }
        });
        main.post(() -> {
            if (live == null) {
                call.reject("진행 중인 음성 인식이 없습니다.");
                return;
            }
            if (liveDone) {
                resolveStop(call);
                return;
            }
            stopCall = call;
            // Normally done about 0.1 s after the input closes; never leave the patient waiting on it.
            SpeechRecognizer session = live;
            main.postDelayed(() -> {
                if (session == live) finishLive(null);
            }, 4000);
        });
    }

    private void finishLive(Integer error) {
        if (liveDone) return;
        liveDone = true;
        liveError = error;
        if (stopCall != null) resolveStop(stopCall);
    }

    private void resolveStop(PluginCall call) {
        if (liveError != null && committed.isEmpty()) {
            call.reject("기기 음성 인식 오류 " + liveError);
        } else {
            JSObject result = new JSObject();
            result.put("transcript", String.join(" ", committed).trim());
            call.resolve(result);
        }
        stopCall = null;
        closeLive();
    }

    private void closeLive() {
        if (live != null) live.destroy();
        live = null;
        liveInput = null;
    }
}
