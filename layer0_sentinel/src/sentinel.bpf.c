#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include "sentinel.h"

// Ring buffer for pushing high-frequency events to user-space
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024); // 256 KB buffer
} rb SEC(".maps");

SEC("tracepoint/raw_syscalls/sys_enter")
int trace_sys_enter(struct trace_event_raw_sys_enter *ctx) {
    // Filter out background noise, focus on input/wayland/IPC related syscalls
    // 0: read, 1: write, 7: poll, 45: recvfrom (Wayland IPC usually rides on these)
    __u32 id = ctx->id;
    if (id != 0 && id != 1 && id != 7 && id != 45) {
        return 0;
    }

    struct event_t *e;
    e = bpf_ringbuf_reserve(&rb, sizeof(*e), 0);
    if (!e) return 0; // Drop if buffer is full

    __u64 id_tgid = bpf_get_current_pid_tgid();
    e->pid = id_tgid >> 32;
    e->tgid = id_tgid & 0xFFFFFFFF;
    e->syscall_id = id;
    e->timestamp_ns = bpf_ktime_get_ns();
    bpf_get_current_comm(&e->comm, sizeof(e->comm));

    bpf_ringbuf_submit(e, 0);
    return 0;
}

char LICENSE[] SEC("license") = "GPL";
