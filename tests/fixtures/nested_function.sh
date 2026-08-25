#!/bin/bash

check_disk() {
    local usage
    usage=$(df / | awk 'NR==2{print $5}' | tr -d '%')
    if [ "$usage" -gt 90 ]; then
        echo "CRITICAL: disk usage at ${usage}%"
    fi
}

check_disk
echo "check complete"
