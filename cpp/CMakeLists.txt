cmake_minimum_required(VERSION 3.20)

project(jr100_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(jr100_core STATIC
    src/core.cpp
    src/cpu.cpp
    src/via.cpp
)
target_include_directories(jr100_core PUBLIC include)
target_compile_options(jr100_core PRIVATE -Wall -Wextra -Wpedantic -Werror)

if(EMSCRIPTEN)
    add_executable(jr100_wasm src/wasm_api.cpp)
    target_link_libraries(jr100_wasm PRIVATE jr100_core)
    target_compile_options(jr100_wasm PRIVATE -Wall -Wextra -Wpedantic -Werror -fexceptions)
    target_link_options(jr100_wasm PRIVATE
        --no-entry
        -fexceptions
        -sMODULARIZE=1
        -sEXPORT_NAME=createJR100Module
        -sENVIRONMENT=worker
        -sALLOW_MEMORY_GROWTH=1
        -sFILESYSTEM=0
        -sNO_EXIT_RUNTIME=1
        -sEXPORTED_RUNTIME_METHODS=['ccall','UTF8ToString','HEAPU8']
    )
    set_target_properties(jr100_wasm PROPERTIES OUTPUT_NAME "jr100-core" SUFFIX ".js")
else()
    enable_testing()
    add_executable(jr100_core_tests tests/core_test.cpp)
    target_link_libraries(jr100_core_tests PRIVATE jr100_core)
    target_compile_options(jr100_core_tests PRIVATE -Wall -Wextra -Wpedantic -Werror)
    add_test(NAME jr100_core_tests COMMAND jr100_core_tests)

    add_executable(jr100_core_runner tools/core_runner.cpp)
    target_link_libraries(jr100_core_runner PRIVATE jr100_core)
    target_compile_options(jr100_core_runner PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
