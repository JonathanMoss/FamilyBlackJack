#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# File to store the environment variables
ENV_FILE=".env"

# Generate a random UUID/GUID-style secret key
# Try python3 first for maximum portability, then fallback to uuidgen, /proc/sys, or openssl
if command -v python3 >/dev/null 2>&1; then
    SECRET_KEY=$(python3 -c "import uuid; print(uuid.uuid4())")
elif command -v uuidgen >/dev/null 2>&1; then
    SECRET_KEY=$(uuidgen)
elif [ -f /proc/sys/kernel/random/uuid ]; then
    SECRET_KEY=$(cat /proc/sys/kernel/random/uuid)
elif command -v openssl >/dev/null 2>&1; then
    SECRET_KEY=$(openssl rand -hex 16)
else
    SECRET_KEY=$(od -x /dev/urandom | head -n 1 | awk '{print $2$3$4$5}')
fi

# Create or update the .env file
if [ -f "$ENV_FILE" ]; then
    if grep -q "^SECRET_KEY=" "$ENV_FILE"; then
        # Replace the existing SECRET_KEY in place
        sed -i.bak "s/^SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" "$ENV_FILE" && rm -f "${ENV_FILE}.bak"
        echo "Updated existing SECRET_KEY in $ENV_FILE"
    else
        # Append to the existing file
        echo "" >> "$ENV_FILE"
        echo "SECRET_KEY=$SECRET_KEY" >> "$ENV_FILE"
        echo "Appended SECRET_KEY to $ENV_FILE"
    fi
else
    # Create a new .env file
    echo "SECRET_KEY=$SECRET_KEY" > "$ENV_FILE"
    echo "Created $ENV_FILE with new SECRET_KEY"
fi
