cmake_minimum_required(VERSION 3.20)
project(CameraPerViewportFilter LANGUAGES CXX)

if(NOT MAXSDK_ROOT)
    set(MAXSDK_ROOT "C:/Program Files/Autodesk/3ds Max 2026 SDK/maxsdk"
        CACHE PATH "Path to the 3ds Max 2026 maxsdk folder")
endif()

if(NOT EXISTS "${MAXSDK_ROOT}/include/max.h")
    message(FATAL_ERROR
        "3ds Max SDK not found. Set MAXSDK_ROOT to the folder containing include/max.h.")
endif()

add_library(CameraPerViewportFilter SHARED
    CameraPerViewportFilter.cpp
)

target_compile_features(CameraPerViewportFilter PRIVATE cxx_std_17)

target_compile_definitions(CameraPerViewportFilter PRIVATE
    UNICODE
    _UNICODE
    NOMINMAX
)

if(MSVC)
    set_property(TARGET CameraPerViewportFilter PROPERTY
        MSVC_RUNTIME_LIBRARY "MultiThreadedDLL")
    target_compile_options(CameraPerViewportFilter PRIVATE
        /permissive-
        /EHsc
        /U_MBCS
    )
endif()

target_include_directories(CameraPerViewportFilter PRIVATE
    "${MAXSDK_ROOT}/include"
    "${CMAKE_CURRENT_SOURCE_DIR}"
)

target_link_directories(CameraPerViewportFilter PRIVATE
    "${MAXSDK_ROOT}/lib"
    "${MAXSDK_ROOT}/lib/x64/Release"
)

target_link_libraries(CameraPerViewportFilter PRIVATE
    core.lib
    maxutil.lib
)

set_target_properties(CameraPerViewportFilter PROPERTIES
    OUTPUT_NAME "CameraPerViewportFilter"
)

# Pure logic test: runs on GitHub without 3ds Max installed at runtime.
add_executable(CameraPerViewportFilterTests
    CameraPerViewportFilterTests.cpp
)
target_compile_features(CameraPerViewportFilterTests PRIVATE cxx_std_17)
target_include_directories(CameraPerViewportFilterTests PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}"
)

enable_testing()
add_test(NAME CameraPerViewportFilterLogic COMMAND CameraPerViewportFilterTests)
