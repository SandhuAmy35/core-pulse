#!/bin/bash
# Reverts Hyprland to nominal state

hyprctl keyword decoration:dim_inactive false
hyprctl keyword general:col.active_border "rgba(33ccffee) rgba(00ff99ee) 45deg"

echo "[$(date +'%H:%M:%S')] Hyprland environment restored. Lockout lifted."
