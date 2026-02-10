#!/bin/sh
set -eu

# Generated files should be readable by nginx and other containers.
umask 022

exec "$@"
