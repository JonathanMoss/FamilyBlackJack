#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

# Run the secret generator script at startup
if [ -f "./generate_secret.sh" ]; then
    ./generate_secret.sh
fi

# Execute the CMD passed to the container
exec "$@"
