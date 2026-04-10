#ifndef __SENTINEL_H
#define __SENTINEL_H

#define MAX_ENTROPY_EVENTS 256

// Shared struct pushed to the BPF Ring Buffer
struct event_t {
    __u32 pid;
    __u32 tgid;
    __u32 syscall_id;
    __u64 timestamp_ns;
    char comm[16];
};

// Raw telemetry payload to broadcast to Layer 1 via ZMQ
struct TelemetryPayload {
    double shannon_entropy;
    unsigned long long timestamp;
    int event_count;
};

#endif
