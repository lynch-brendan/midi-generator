cmake_minimum_required(VERSION 3.22)
project(nasty-audio-engine VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# --- JUCE ---
# Bring in JUCE. Expected at ./juce as a git submodule.
# Fallback: user has JUCE elsewhere and passes -DJUCE_DIR=/path/to/JUCE.
if(NOT DEFINED JUCE_DIR)
    set(JUCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/juce")
endif()

if(NOT EXISTS "${JUCE_DIR}/CMakeLists.txt")
    message(FATAL_ERROR
        "JUCE not found at ${JUCE_DIR}.\n"
        "Run:  git submodule add https://github.com/juce-framework/JUCE.git juce\n"
        "      git submodule update --init --recursive\n"
        "Or:   pass -DJUCE_DIR=/path/to/JUCE to cmake."
    )
endif()

add_subdirectory(${JUCE_DIR} juce EXCLUDE_FROM_ALL)

# --- our binary ---
juce_add_console_app(nasty-audio-engine
    PRODUCT_NAME "nasty-audio-engine"
)

target_sources(nasty-audio-engine PRIVATE
    src/main.cpp
    src/PluginHost.cpp
    src/IpcServer.cpp
)

target_compile_definitions(nasty-audio-engine PRIVATE
    JUCE_PLUGINHOST_VST3=1
    JUCE_PLUGINHOST_AU=1
    JUCE_PLUGINHOST_LADSPA=0
    JUCE_USE_CURL=0
    JUCE_WEB_BROWSER=0
)

target_link_libraries(nasty-audio-engine PRIVATE
    juce::juce_audio_utils
    juce::juce_audio_processors
    juce::juce_audio_plugin_client
    juce::juce_core
    juce::juce_data_structures
    juce::juce_events
    juce::juce_recommended_config_flags
    juce::juce_recommended_lto_flags
    juce::juce_recommended_warning_flags
)
