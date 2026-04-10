# layer3_governor/CMakeLists.txt
cmake_minimum_required(VERSION 3.14)
project(layer3_governor)

set(CMAKE_CXX_STANDARD 17)

# 1. System Dependencies
find_package(ZeroMQ REQUIRED)
find_package(nlohmann_json REQUIRED) # Install via pacman: sudo pacman -S nlohmann-json

# 2. Fetch FTXUI automatically
include(FetchContent)
FetchContent_Declare(
  ftxui
  GIT_REPOSITORY https://github.com/ArthurSonzogni/FTXUI
  GIT_TAG main
)
FetchContent_MakeAvailable(ftxui)

# 3. Build the Target (Assuming you saved main.cpp as tui_matrix.cpp)
add_executable(governor src/tui_matrix.cpp)

target_link_libraries(governor
    PRIVATE
    libzmq
    nlohmann_json::nlohmann_json
    ftxui::screen
    ftxui::dom
    ftxui::component
)
