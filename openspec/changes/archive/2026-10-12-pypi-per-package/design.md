## Context

PyPI's database keeps pending GitHub publishers unique by repository, owner, workflow and
environment, not project name (`warehouse/accounts/views.py` turns the violation into "A pending
trusted publisher matching this configuration has already been registered for a different project
name"). Once a project exists, one publisher may serve several projects, and the token it mints
covers them all; the limit only bites the first upload. When several publishers match a token's
claims, PyPI takes the one of the token's environment before one without an environment
(`warehouse/oidc/models/github.py`).

## Goals / Non-Goals

**Goals:** both projects created by the first 1.0.0 release, in one run, with trusted publishing
and an environment that the owner approves.

**Non-Goals:** publishing earlier than 1.0.0; TestPyPI.

## Decisions

### A job and an environment per package

`pypi` publishes the files `xincord-*` in the environment `pypi`; `pypi-plugins` publishes
`xincord_plugins-*` in `pypi-plugins` and `needs: pypi`, so that the plugins never reach PyPI
before the core they depend on, nor after a failed core upload. The owner's choice of 2026-10-12.

Alternatives: one environment and a two-step first release (the plugins' upload fails once; the
owner then registers their pending publisher and reruns the job, `uv publish --check-url` skipping
the files already uploaded); or the plugins' publisher without an environment (any job of the
workflow could publish them).

## Manual check

At the first 1.0.0 tag: both jobs wait for the owner's approval in turn; the two projects appear on
PyPI with their files.
