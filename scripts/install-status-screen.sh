#!/usr/bin/env bash
# Superseded: the status screen now reads from the core service over MQTT.
exec "$(dirname "$0")/install-services.sh" "$@"
