#include <iostream>
#include <cmath>
#include <unordered_map>
#include <fstream>
#include <chrono>
#include <thread>
#include <bpf/libbpf.h>
#include <nlohmann/json.hpp>
#include "sentinel.h"
#include "sentinel.skel.h" 

using json = nlohmann::json;

std::unordered_map<uint32_t, int> syscall_freq;
int total_events = 0;
const std::string TELEMETRY_PATH = "/home/posiedon/Desktop/Coding/Hack-NMIMS-CHD/core-pulse/layer3_governor/telemetry.json";

double calculate_shannon_entropy() {
    double entropy = 0.0;
    if (total_events == 0) return 0.0;
    for (const auto& [id, count] : syscall_freq) {
        double p_x = (double)count / total_events;
        entropy -= p_x * std::log2(p_x);
    }
    return entropy;
}

int handle_bpf_event(void *ctx, void *data, size_t data_sz) {
    const struct event_t *e = (const struct event_t *)data;
    syscall_freq[e->syscall_id]++;
    total_events++;
    return 0;
}

int main() {
    struct sentinel_bpf *skel = sentinel_bpf__open_and_load();
    if (!skel) return 1;
    sentinel_bpf__attach(skel);

    struct ring_buffer *rb = ring_buffer__new(bpf_map__fd(skel->maps.rb), handle_bpf_event, NULL, NULL);
    
    std::cout << "[Layer 0] Sentinel polling kernel tracepoints..." << std::endl;

    auto last_write = std::chrono::steady_clock::now();
    while (true) {
        ring_buffer__poll(rb, 100);

        auto now = std::chrono::steady_clock::now();
        if (std::chrono::duration_cast<std::chrono::seconds>(now - last_write).count() >= 1) {
            double entropy = calculate_shannon_entropy();
            
            // THE FIX: Calculate raw spam volume. 
            // If you generate >5000 syscalls a second, that is pure jitter.
            double volume_spike = (double)total_events / 5000.0; 
            
            // Blend them. High unpredictability OR high volume = Burnout.
            double raw_bp = (entropy / 10.0) + volume_spike;
            double final_bp = std::min(raw_bp, 1.0); // Clamp to max 1.0 (100%)

            // Generate valid JSON
            json j;
            j["timestamp"] = std::time(nullptr);
            j["user_id"] = "posiedon-local";
            j["burnout_probability"] = final_bp; 
            j["status"] = (final_bp > 0.70) ? "CRITICAL" : "NOMINAL";
            j["active_distractions"] = {"kernel_raw_input"};
            j["synergy_friction_score"] = std::min(volume_spike, 1.0); // Show friction

            std::ofstream f(TELEMETRY_PATH);
            f << j.dump();
            f.close();

            syscall_freq.clear();
            total_events = 0;
            last_write = now;
        }
    }
    return 0;
}
