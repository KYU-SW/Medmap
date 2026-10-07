package kr.medmap.app;

import android.os.SystemClock;
import android.util.Base64;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.ShortBuffer;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Transcribes speech on the phone with whisper.cpp. The audio never leaves the device. */
@CapacitorPlugin(name = "Whisper")
public class WhisperPlugin extends Plugin {
    // Copied onto the phone with adb (docs/ANDROID_APP.md); too large to ship inside the APK.
    // The first file present is used. q8_0 is the default: on a Galaxy Note20 it ran as fast as q4_0 (about 6 s
    // per utterance, both use the ARM repacked kernels) without q4_0's misheard word; q5_0 has no repacked kernel
    // and took 17-19 s (docs/ANDROID_APP.md). The others stay listed for speed tests.
    static final String[] MODEL_FILES = {
        "ggml-large-v3-turbo-q8_0.bin", "ggml-large-v3-turbo-q4_0.bin", "ggml-large-v3-turbo-q5_0.bin",
    };

    static {
        System.loadLibrary("medmap_whisper");
    }

    private static native long nativeInit(String modelPath);

    private static native byte[] nativeTranscribe(long context, float[] samples, int threads, boolean preview);

    // A small model for the caption shown while the patient speaks; the transcript itself always comes from turbo.
    static final String PREVIEW_MODEL_FILE = "ggml-base-q8_0.bin";

    // One model in memory, used by one transcription at a time.
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private long context = 0;
    private long previewContext = 0;

    private File modelFile() {
        File directory = getContext().getExternalFilesDir(null);
        for (String name : MODEL_FILES) {
            File file = new File(directory, name);
            if (file.isFile()) return file;
        }
        return new File(directory, MODEL_FILES[MODEL_FILES.length - 1]);
    }

    @PluginMethod
    public void status(PluginCall call) {
        JSObject result = new JSObject();
        result.put("modelReady", modelFile().isFile());
        result.put("modelPath", modelFile().getAbsolutePath());
        call.resolve(result);
    }

    /** Takes 16 kHz mono 16-bit PCM as base64 ("pcm16") and returns the transcript. */
    @PluginMethod
    public void transcribe(PluginCall call) {
        run(call, false);
    }

    /** A quick, rough caption of the recording so far, from the small model. */
    @PluginMethod
    public void preview(PluginCall call) {
        run(call, true);
    }

    private void run(PluginCall call, boolean preview) {
        String pcm16 = call.getString("pcm16");
        int threads = call.getInt("threads", 4);
        if (pcm16 == null || pcm16.isEmpty()) {
            call.reject("녹음된 음성이 없습니다.");
            return;
        }
        worker.execute(() -> {
            try {
                File model = preview
                        ? new File(getContext().getExternalFilesDir(null), PREVIEW_MODEL_FILE)
                        : modelFile();
                if (!model.isFile()) {
                    call.reject("휴대폰에 음성 인식 모델이 없습니다: " + model.getAbsolutePath());
                    return;
                }
                long loadStarted = SystemClock.elapsedRealtime();
                if (preview && previewContext == 0) previewContext = nativeInit(model.getAbsolutePath());
                if (!preview && context == 0) context = nativeInit(model.getAbsolutePath());
                long handle = preview ? previewContext : context;
                if (handle == 0) {
                    call.reject("음성 인식 모델을 불러오지 못했습니다.");
                    return;
                }
                long started = SystemClock.elapsedRealtime();

                ShortBuffer pcm = ByteBuffer.wrap(Base64.decode(pcm16, Base64.DEFAULT))
                        .order(ByteOrder.LITTLE_ENDIAN).asShortBuffer();
                float[] samples = new float[pcm.remaining()];
                for (int i = 0; i < samples.length; i++) samples[i] = pcm.get(i) / 32768f;

                byte[] text = nativeTranscribe(handle, samples, threads, preview);
                if (text == null) {
                    call.reject("음성을 글자로 바꾸지 못했습니다.");
                    return;
                }
                JSObject result = new JSObject();
                // A broken character ("테레�", "타이래�을") hides the word from the intake rules; without it the
                // rest of the word still reads as a medicine name the patient can correct.
                result.put("transcript", new String(text, StandardCharsets.UTF_8).replace("�", "").trim());
                result.put("load_seconds", (started - loadStarted) / 1000.0);
                result.put("processing_seconds", (SystemClock.elapsedRealtime() - started) / 1000.0);
                result.put("model", model.getName());
                result.put("audio_seconds", samples.length / 16000.0);
                call.resolve(result);
            } catch (RuntimeException error) {
                call.reject("음성 변환 중 오류가 났습니다: " + error.getMessage());
            }
        });
    }
}
