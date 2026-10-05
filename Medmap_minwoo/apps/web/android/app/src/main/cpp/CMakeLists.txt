# Builds whisper.cpp into the app so speech is transcribed on the phone.
cmake_minimum_required(VERSION 3.22)
project(medmap_whisper LANGUAGES C CXX)

include(FetchContent)
# Same release line as the PC comparison (docs/STT_SPEC.md). A source archive needs no git at build time.
FetchContent_Declare(
    whisper
    URL https://github.com/ggml-org/whisper.cpp/archive/refs/tags/v1.9.4.tar.gz
)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(WHISPER_BUILD_SERVER OFF CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(whisper)

add_library(medmap_whisper SHARED whisper_jni.cpp)
target_link_libraries(medmap_whisper PRIVATE whisper log)
