cmake_minimum_required(VERSION 3.20)
project(cyclops_eye_luckfox VERSION 0.1.0 LANGUAGES C)

option(CYCLOPS_EYE_WITH_LUCKFOX_SDK "Build the RV1106 MPP/RTSP firmware binary" OFF)
option(CYCLOPS_EYE_BUILD_TESTS "Build host-side unit tests" ON)
set(LUCKFOX_SDK_ROOT "" CACHE PATH "Path to the LuckFox SDK sysroot")

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

add_library(cyclops_eye_core STATIC
    src/config.c
    src/governor.c
    src/protocol.c
    src/control_server.c
)
target_include_directories(cyclops_eye_core PUBLIC include)
target_compile_options(cyclops_eye_core PRIVATE -Wall -Wextra -Werror -Wpedantic)

if(CYCLOPS_EYE_WITH_LUCKFOX_SDK)
    if(NOT LUCKFOX_SDK_ROOT)
        message(FATAL_ERROR "Set LUCKFOX_SDK_ROOT to the LuckFox SDK sysroot when enabling the firmware build")
    endif()
    add_executable(cyclops-eye src/main.c src/camera_rv1106.c src/http_client.c)
    target_include_directories(cyclops-eye PRIVATE
        include
        ${LUCKFOX_SDK_ROOT}/usr/include
        ${LUCKFOX_SDK_ROOT}/usr/include/rkaiq
    )
    target_compile_definitions(cyclops-eye PRIVATE CYCLOPS_EYE_RV1106=1)
    # LuckFox's public MPP headers intentionally use GNU empty structs, so
    # strict ISO pedantic warnings cannot be errors on the hardware target.
    target_compile_options(cyclops-eye PRIVATE -Wall -Wextra -Werror)
    target_link_directories(cyclops-eye PRIVATE ${LUCKFOX_SDK_ROOT}/usr/lib)
    target_link_libraries(cyclops-eye PRIVATE cyclops_eye_core pthread rtsp_demo rockit)
    install(TARGETS cyclops-eye RUNTIME DESTINATION usr/bin)
else()
    add_executable(cyclops-eye-config-check src/config_check.c)
    target_link_libraries(cyclops-eye-config-check PRIVATE cyclops_eye_core)
    target_compile_options(cyclops-eye-config-check PRIVATE -Wall -Wextra -Werror -Wpedantic)
endif()

if(CYCLOPS_EYE_BUILD_TESTS)
    enable_testing()
    add_executable(cyclops-eye-tests tests/test_core.c)
    target_link_libraries(cyclops-eye-tests PRIVATE cyclops_eye_core)
    target_compile_options(cyclops-eye-tests PRIVATE -Wall -Wextra -Werror -Wpedantic)
    add_test(NAME cyclops-eye-tests COMMAND cyclops-eye-tests)
endif()
