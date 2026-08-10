cmake_minimum_required(VERSION 3.20)
project(AlokViewportIsolate LANGUAGES CXX)

if(NOT MAXSDK_ROOT)
    set(MAXSDK_ROOT "C:/Program Files/Autodesk/3ds Max 2026 SDK/maxsdk"
        CACHE PATH "Path to the 3ds Max 2026 maxsdk folder")
endif()

if(NOT EXISTS "${MAXSDK_ROOT}/include/max.h")
    message(FATAL_ERROR
        "3ds Max SDK not found. Set MAXSDK_ROOT to the folder containing include/max.h.")
endif()

add_library(AlokViewportIsolate SHARED
    AlokViewportIsolate.cpp
)

target_compile_features(AlokViewportIsolate PRIVATE cxx_std_17)

target_compile_definitions(AlokViewportIsolate PRIVATE
    UNICODE
    _UNICODE
    NOMINMAX
)

if(MSVC)
    set_property(TARGET AlokViewportIsolate PROPERTY
        MSVC_RUNTIME_LIBRARY "MultiThreadedDLL")
    target_compile_options(AlokViewportIsolate PRIVATE
        /permissive-
        /EHsc
        /U_MBCS
    )
endif()

target_include_directories(AlokViewportIsolate PRIVATE
    "${MAXSDK_ROOT}/include"
)

target_link_directories(AlokViewportIsolate PRIVATE
    "${MAXSDK_ROOT}/lib"
    "${MAXSDK_ROOT}/lib/x64/Release"
)

target_link_libraries(AlokViewportIsolate PRIVATE
    core.lib
    maxutil.lib
)

set_target_properties(AlokViewportIsolate PROPERTIES
    OUTPUT_NAME "AlokViewportIsolate"
)
