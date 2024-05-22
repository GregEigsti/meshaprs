#!/bin/bash

while true; do
    python3 igate.py

    if [ $? -eq 0 ]; then
        exit 0
    fi

    echo "Restarting meshaprs service in 5s..."
    sleep 5s
done
