// JNI bridge between WhisperPlugin.java and whisper.cpp.
#include <android/log.h>
#include <jni.h>

#include <algorithm>
#include <string>

#include "whisper.h"

// whisper.cpp writes its timings and CPU features to stderr, which Android drops; send them to logcat ("whisper").
static void log_to_logcat(ggml_log_level, const char *text, void *) {
    __android_log_write(ANDROID_LOG_INFO, "whisper", text);
}

extern "C" JNIEXPORT jlong JNICALL
Java_kr_medmap_app_WhisperPlugin_nativeInit(JNIEnv *env, jclass, jstring model_path) {
    whisper_log_set(log_to_logcat, nullptr);
    __android_log_write(ANDROID_LOG_INFO, "whisper", whisper_print_system_info());
    const char *path = env->GetStringUTFChars(model_path, nullptr);
    whisper_context *context = whisper_init_from_file_with_params(path, whisper_context_default_params());
    env->ReleaseStringUTFChars(model_path, path);
    return reinterpret_cast<jlong>(context);
}

// Returns UTF-8 bytes, not a jstring: the model can emit a broken multibyte character,
// which NewStringUTF would reject. Java decodes the bytes with replacement characters.
extern "C" JNIEXPORT jbyteArray JNICALL
Java_kr_medmap_app_WhisperPlugin_nativeTranscribe(
        JNIEnv *env, jclass, jlong handle, jfloatArray samples, jint threads) {
    auto *context = reinterpret_cast<whisper_context *>(handle);
    const jsize count = env->GetArrayLength(samples);
    jfloat *data = env->GetFloatArrayElements(samples, nullptr);

    // Same decoding as the server and the PC comparison: Korean, beam search 5.
    whisper_full_params params = whisper_full_default_params(WHISPER_SAMPLING_BEAM_SEARCH);
    params.beam_search.beam_size = 5;
    params.language = "ko";
    params.translate = false;
    params.n_threads = threads;
    params.no_timestamps = true;
    params.print_progress = false;
    params.print_realtime = false;
    params.print_special = false;
    params.print_timestamps = false;
    // The encoder always runs over a 30 s window (1500 frames, 50 per second), which on a phone CPU is most
    // of the time (37 s on a Galaxy Note20). Encode only the recording plus 5 s, but never less than 15 s:
    // tighter windows changed words in the PC comparison (docs/STT_SPEC.md).
    const int needed = (count / 16000 + 5) * 50;
    params.audio_ctx = std::min(1500, std::max(768, (needed + 63) / 64 * 64));

    const int result = whisper_full(context, params, data, count);
    env->ReleaseFloatArrayElements(samples, data, JNI_ABORT);
    whisper_print_timings(context);
    whisper_reset_timings(context);
    if (result != 0) return nullptr;

    std::string text;
    for (int i = 0; i < whisper_full_n_segments(context); ++i) {
        text += whisper_full_get_segment_text(context, i);
    }
    jbyteArray bytes = env->NewByteArray(static_cast<jsize>(text.size()));
    env->SetByteArrayRegion(bytes, 0, static_cast<jsize>(text.size()), reinterpret_cast<const jbyte *>(text.data()));
    return bytes;
}
