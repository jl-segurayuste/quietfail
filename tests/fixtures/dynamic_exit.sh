#!/bin/bash

command_that_might_fail
status=$?

if [ "$status" -ne 0 ]; then
    echo "ERROR: command failed with status $status"
    exit "$status"
fi
