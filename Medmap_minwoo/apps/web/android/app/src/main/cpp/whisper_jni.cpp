// JNI bridge between WhisperPlugin.java and whisper.cpp.
#include <android/log.h>
#include <jni.h>

#include <sched.h>

#include <algorithm>
#include <fstream>
#include <string>
#include <vector>

#include "whisper.h"

// Phones mix fast and slow cores (Galaxy Note20: 4 at 2.4-3.1 GHz, 4 at 1.8 GHz). A worker left on a slow
// core holds the whole encoder back: on the phone, 4 threads took 10 s unpinned and 5-7 s on the fast cores.
// Pin this thread to the fast cores; the OpenMP workers it starts inherit the mask. Apps cannot read the
// cpufreq files on Android 13, so the slow cores are told apart by their "CPU part" in /proc/cpuinfo.
// Returns how many cores it kept, or 0 when it could not tell or pin (whisper.cpp then uses the default).
static int pin_to_fast_cores() {
    // Efficiency cores: Cortex-A53, A35, A55, A510, A520 and Qualcomm Kryo Silver (A53/A55 based).
    static const std::vector<std::string> slow_parts = {"0xd03", "0xd04", "0xd05", "0xd46", "0xd80", "0x801", "0x803", "0x805"};
    std::ifstream cpuinfo("/proc/cpuinfo");
    std::vector<std::string> parts;  // index = processor number
    std::string line;
    int processor = -1;
    while (std::getline(cpuinfo, line)) {
        const size_t colon = line.find(':');
        if (colon == std::string::npos) continue;
        std::string key = line.substr(0, line.find_last_not_of(" \t", colon - 1) + 1);
        std::string value = line.substr(line.find_first_not_of(" \t", colon + 1) == std::string::npos ? line.size() : line.find_first_not_of(" \t", colon + 1));
        if (key == "processor") processor = std::stoi(value);
        if (key == "CPU part" && processor >= 0) {
            if (parts.size() <= static_cast<size_t>(processor)) parts.resize(processor + 1);
            parts[processor] = value;
        }
    }
    cpu_set_t mask;
    CPU_ZERO(&mask);
    int kept = 0;
    for (size_t cpu = 0; cpu < parts.size(); ++cpu) {
        if (!parts[cpu].empty() && std::find(slow_parts.begin(), slow_parts.end(), parts[cpu]) == slow_parts.end()) {
            CPU_SET(cpu, &mask);
            ++kept;
        }
    }
    // Nothing recognised as slow (or nothing fast left): leave scheduling to Android.
    if (kept == 0 || kept == static_cast<int>(parts.size())) return 0;
    return sched_setaffinity(0, sizeof(mask), &mask) == 0 ? kept : 0;
}

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
        JNIEnv *env, jclass, jlong handle, jfloatArray samples, jint threads, jboolean preview) {
    auto *context = reinterpret_cast<whisper_context *>(handle);
    const jsize count = env->GetArrayLength(samples);
    jfloat *data = env->GetFloatArrayElements(samples, nullptr);

    // The final transcript decodes like the server and the PC comparison: beam search 5.
    // The live caption (small model, re-run every couple of seconds) only needs to be quick: greedy.
    whisper_full_params params = whisper_full_default_params(preview ? WHISPER_SAMPLING_GREEDY : WHISPER_SAMPLING_BEAM_SEARCH);
    params.beam_search.beam_size = 5;
    if (preview) {
        // No temperature fallback and a token cap: a caption that loops ("복통이 너무 심하고 복통이 너무 심하고")
        // or retries took 10-12 s instead of 0.2 s, and the final transcription waits for it.
        params.temperature_inc = 0.0f;
        // Korean speech is under about 6 tokens a second; a longer caption is a loop.
        params.max_tokens = 8 + 6 * (count / 16000);
    }
    params.language = "ko";
    params.translate = false;
    const int fast_cores = pin_to_fast_cores();
    params.n_threads = fast_cores > 0 ? fast_cores : threads;
    __android_log_print(ANDROID_LOG_INFO, "whisper", "medmap: threads=%d (fast cores %d)", params.n_threads, fast_cores);
    params.no_timestamps = true;
    params.print_progress = false;
    params.print_realtime = false;
    params.print_special = false;
    params.print_timestamps = false;
    // The encoder always runs over a 30 s window (1500 frames, 50 per second), which on a phone CPU is most
    // of the time (37 s on a Galaxy Note20). Encode only the recording plus 5 s, but never less than 15 s:
    // tighter windows changed words in the PC comparison (docs/STT_SPEC.md).
    // A caption may be rough, so it encodes just the recording plus 1 s.
    const int needed = (count / 16000 + (preview ? 1 : 5)) * 50;
    params.audio_ctx = std::min(1500, std::max(preview ? 128 : 768, (needed + 63) / 64 * 64));

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
