# layer0_sentinel/CMakeLists.txt
cmake_minimum_required(VERSION 3.10)
project(layer0_sentinel)

set(CMAKE_CXX_STANDARD 17)

# 1. eBPF and Networking Dependencies
find_package(PkgConfig REQUIRED)
pkg_check_modules(LIBBPF REQUIRED libbpf)
find_package(ZeroMQ REQUIRED)

# 2. Include paths (point to where sentinel.skel.h is)
include_directories(include ${LIBBPF_INCLUDE_DIRS})

# 3. Build the Target
add_executable(sentinel_daemon src/loader.cpp) # Adjust name if you combined the files

# 4. Link against kernel tracing libraries
target_link_libraries(sentinel_daemon
    PRIVATE
    ${LIBBPF_LIBRARIES}
    libzmq
    elf
    z
)
