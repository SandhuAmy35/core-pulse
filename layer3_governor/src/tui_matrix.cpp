#include <iostream>
#include <thread>
#include <atomic>
#include <cstdlib>
#include <mutex>
#include <deque>
#include <vector>
#include <chrono>
#include <iomanip>
#include <sstream>
#include <fstream>
#include <nlohmann/json.hpp>
#include <ftxui/component/component.hpp>
#include <ftxui/component/screen_interactive.hpp>
#include <ftxui/dom/elements.hpp>
#include <csignal>

using json = nlohmann::json;
using namespace ftxui;

std::recursive_mutex state_mutex; 
double current_burnout = 0.0;
double synergy_friction = 0.0;
bool critical_state = false;
std::string latest_user = "Awaiting Payload...";
std::vector<std::string> active_distractions;
std::deque<std::string> live_logs;
const size_t MAX_LOGS = 12;

// Master Algorithm Variables
double context_thrashing_score = 0.0;
double distraction_penalty = 0.0;
std::string current_app = "Desktop";
double smoothed_burnout = 0.0; 

std::string get_time() {
    auto now = std::chrono::system_clock::now();
    auto in_time_t = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&in_time_t), "%H:%M:%S");
    return ss.str();
}

void push_log(const std::string& msg) {
    std::lock_guard<std::recursive_mutex> lock(state_mutex); 
    live_logs.push_back("[" + get_time() + "] " + msg);
    if (live_logs.size() > MAX_LOGS) {
        live_logs.pop_front();
    }
}

void file_listener_thread() {
    push_log("Dual-Pipe Active. Polling Hardware & Context...");
    std::string last_telemetry = "";

    while (true) {
        using namespace std::chrono_literals;
        std::this_thread::sleep_for(0.2s); 

        // 1. READ HYPRLAND CONTEXT
        std::ifstream ctx_file("/home/posiedon/Desktop/Coding/Hack-NMIMS-CHD/core-pulse/layer3_governor/context.json");
        if (ctx_file.is_open()) {
            std::string ctx_str((std::istreambuf_iterator<char>(ctx_file)), std::istreambuf_iterator<char>());
            ctx_file.close();
            try {
                auto ctx_data = json::parse(ctx_str);
                std::lock_guard<std::recursive_mutex> lock(state_mutex);
                
                current_app = ctx_data["active_app"].get<std::string>();
                context_thrashing_score = ctx_data["context_thrashing"].get<double>();
                distraction_penalty = ctx_data["distraction_penalty"].get<double>();
                
                active_distractions.clear();
                if (distraction_penalty > 0.0) {
                    active_distractions.push_back(current_app + " (BLACKLISTED)");
                }
            } catch (...) {} 
        }

        // 2. READ HARDWARE TELEMETRY
        std::ifstream hw_file("/home/posiedon/Desktop/Coding/Hack-NMIMS-CHD/core-pulse/layer3_governor/telemetry.json");
        if (!hw_file.is_open()) continue;
        std::string hw_str((std::istreambuf_iterator<char>(hw_file)), std::istreambuf_iterator<char>());
        hw_file.close();

        if (hw_str.empty() || hw_str == last_telemetry) continue;
        last_telemetry = hw_str;

        try {
            auto hw_data = json::parse(hw_str);
            
            std::lock_guard<std::recursive_mutex> lock(state_mutex);
            double hardware_bp = hw_data["burnout_probability"].get<double>();
            latest_user = hw_data["user_id"].get<std::string>();

            double raw_burnout = (hardware_bp * 0.5) + (context_thrashing_score * 0.5) + distraction_penalty;
            raw_burnout = std::min(raw_burnout, 1.0); 
            
            smoothed_burnout = (raw_burnout * 0.02) + (smoothed_burnout * 0.98);
            
            current_burnout = smoothed_burnout; 
            synergy_friction = hw_data["synergy_friction_score"].get<double>();

            bool is_critical = (current_burnout > 0.70); 
            
            if (is_critical && !critical_state) {
                critical_state = true;
                push_log("CRITICAL: B_p Threshold Exceeded! Intervening...");
                std::system("bash ../scripts/dim_environment.sh &");
                std::system("bash ../scripts/throttle_network.sh &");
                
                // THE GUILLOTINE: Freeze distraction processes in memory
                push_log("SIGSTOP: Freezing distraction processes.");
                std::system("killall -STOP discord whatsapp zen-browser spotify 2>/dev/null &");

            } else if (!is_critical && critical_state) {
                critical_state = false;
                push_log("Nominal state restored. Lifting UI restrictions.");
                std::system("bash ../scripts/restore_environment.sh &");
                
                // UNFREEZE: Restore processes
                push_log("SIGCONT: Resuming distraction processes.");
                std::system("killall -CONT discord whatsapp zen-browser spotify 2>/dev/null &");

            } else {
                push_log("Telemetry synced. B_p: " + std::to_string(current_burnout).substr(0,4) + " | App: " + current_app);
            }
            
        } catch (...) {}
    }
}

void handle_exit(int sig) {
    std::system("bash ../scripts/restore_environment.sh &");
    std::system("killall -CONT discord whatsapp zen-browser spotify 2>/dev/null &");
    std::exit(sig);
}

int main() {
    std::signal(SIGINT, handle_exit);
    std::signal(SIGTERM, handle_exit);

    std::thread listener(file_listener_thread);
    listener.detach();

    auto screen = ScreenInteractive::Fullscreen();

    auto renderer = Renderer([&] {
        std::lock_guard<std::recursive_mutex> lock(state_mutex); 

        auto status_color = critical_state ? Color::Red : Color::Green;
        auto status_text = critical_state ? text(" CRITICAL : INTERVENTION ACTIVE ") | bold | color(Color::White) | bgcolor(Color::Red) 
                                          : text(" NOMINAL : MONITORING ") | bold | color(Color::Green);

        auto left_pane = window(text(" NEURAL METRICS ") | bold | color(Color::Cyan),
            vbox({
                hbox({text("Target UID: "), text(latest_user) | bold}),
                separator(),
                text("Burnout Probability (B_p)") | bold,
                gauge(current_burnout) | color(status_color),
                text(" " + std::to_string(current_burnout * 100).substr(0,5) + " %"),
                separator(),
                text("Synergy Friction Score") | bold,
                gauge(synergy_friction) | color(Color::Yellow),
                text(" " + std::to_string(synergy_friction * 100).substr(0,5) + " %"),
                separator(),
                vbox({
                    text("System State:"),
                    status_text
                }),
                filler() // THE UI FIX: This forces all the empty space to the bottom
            })
        );

        Elements dist_elements;
        if (active_distractions.empty()) {
            dist_elements.push_back(text("None detected") | color(Color::Green));
        } else {
            for (const auto& d : active_distractions) {
                dist_elements.push_back(text(" ✗ " + d) | color(Color::Red));
            }
        }
        
        auto right_pane = window(text(" ACTIVE DISTRACTIONS ") | bold | color(Color::Magenta), 
            vbox(std::move(dist_elements))
        );

        Elements log_elements;
        for (const auto& l : live_logs) {
            log_elements.push_back(text(l) | color(Color::GrayLight));
        }
        
        auto bottom_pane = window(text(" SYSTEM EVENT LOGS ") | bold | color(Color::Green), 
            vbox(std::move(log_elements))
        );

        return vbox({
            text(" CORE-PULSE : LAYER 3 GOVERNOR TUI ") | bold | hcenter | color(Color::White),
            separator(),
            hbox({
                left_pane | flex,
                right_pane | size(WIDTH, EQUAL, 40)
            }) | flex,
            bottom_pane | size(HEIGHT, EQUAL, MAX_LOGS + 2)
        }) | border;
    });

    std::atomic<bool> refresh_ui_continue = true;
    std::thread refresh_ui([&] {
        while (refresh_ui_continue) {
            using namespace std::chrono_literals;
            std::this_thread::sleep_for(0.1s);
            screen.PostEvent(Event::Custom);
        }
    });

    screen.Loop(renderer);
    refresh_ui_continue = false;
    refresh_ui.join();

    std::system("bash ../scripts/restore_environment.sh &");
    std::system("killall -CONT discord whatsapp zen-browser spotify 2>/dev/null &");
    
    return 0;
}
