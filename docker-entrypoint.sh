#!/bin/sh
# Deployment-time guard: assert the container was told which environment it is running in.
#
# **Why this cannot live in config.py.** By the time Python runs, `os.getenv("APP_ENV",
# "development")` has already applied its fallback, so "nobody set it" and "somebody deliberately
# set it to development" are indistinguishable. Only the entrypoint sees the difference -- and only
# the *container* needs to, since local runs and pytest legitimately want the convenient default.
#
# **What it prevents.** A deployment that configures every secret but misses this one variable boots
# into the development tier: DEBUG on (internal details returned in error responses) and
# JWT_SECRET_KEY left at the public placeholder `change-me` -- with none of config.py's
# staging/production checks running, because the app does not believe it is in staging or production.
# Everywhere else this config fails closed; an unknown APP_ENV is rejected rather than defaulted.
# An *absent* one was the single door that failed open. This closes it.
#
# Bible Step 1 ("entrypoint secret-check"): secret *values* are already checked, and checked better,
# by config.py's startup guard, which knows the tier. This checks the one thing Python structurally
# cannot see.
set -eu

if [ -z "${APP_ENV:-}" ]; then
    cat >&2 <<'BANNER'

========================================================================
STARTUP FAILED -- the application did not begin serving.
========================================================================
  missing_app_env: APP_ENV is not set

  APP_ENV selects which environment this container is, and every startup
  safety check keys off it. Left unset the app would fall back to the
  development tier and skip all of them -- DEBUG on, placeholder secrets
  accepted -- while appearing to start perfectly normally.

  Set it explicitly, e.g.
    docker run -e APP_ENV=production ...
    compose:               environment: ["APP_ENV=staging"]
    Azure Container Apps:  add APP_ENV to the app's environment variables

  Valid values are the keys of ENVIRONMENT_TIERS in app/core/config.py.

BANNER
    exit 1
fi

# `exec` so uvicorn replaces this shell as PID 1 and receives SIGTERM directly. Without it the shell
# stays PID 1, uvicorn never sees the stop signal, and every `docker stop` waits out the 10s kill
# timeout and severs in-flight requests -- the opposite of the graceful shutdown Step 4 asks for.
exec "$@"
