cmake_minimum_required(VERSION 3.16)
project(helm_x VERSION 0.0.7 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(MSVC)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
    # Source files carry UTF-8 (CJK) string literals — tell MSVC so.
    add_compile_options(/utf-8)
elseif(APPLE)
    # macOS/clang has no fully static libc — link dynamically, just optimize.
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2")
else()
    # Linux / MinGW: static link so the binary is dependency-free.
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -static -static-libgcc -static-libstdc++ -O2 -s")
endif()

add_executable(helmx
    src/main.cpp
    src/config.cpp
    src/log.cpp
    src/platform.cpp
    src/resources.cpp
    src/resources_generated.cpp
    src/tamper.cpp
    src/proxy.cpp
    src/sse.cpp
    src/rewrite.cpp
    src/http.cpp
    src/ui.cpp
    src/verify.cpp
    src/watch.cpp
)

target_include_directories(helmx PRIVATE src)

if(WIN32)
    target_link_libraries(helmx ws2_32 shell32 winhttp)
else()
    # std::thread needs the platform threading library on POSIX.
    find_package(Threads REQUIRED)
    target_link_libraries(helmx Threads::Threads)
endif()
