#!/bin/bash
# Executes Hyprland interventions to reduce screen stimulus

# Enable aggressive dimming for inactive windows
hyprctl keyword decoration:dim_inactive true
hyprctl keyword decoration:dim_strength 0.8

# Force active borders to a warning color (Red) to signal lockout
hyprctl keyword general:col.active_border "rgba(ff0000ff)"

# Optional: Force the layout into a monocle/fullscreen mode to hide distractions
hyprctl dispatch fullscreen 1

echo "[$(date +'%H:%M:%S')] Hyprland environment dimmed. Lockout protocol engaged."
