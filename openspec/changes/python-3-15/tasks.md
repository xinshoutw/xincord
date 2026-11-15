# Tasks

## 1. Container image

- [x] 1.1 Change the container test to the 3.15 series, run it and see it fail against the 3.14
  Dockerfile; commit it marked `xfail(strict=True)`
- [ ] 1.2 Move both Dockerfile stages to `python:3.15.2-slim-trixie` and `.python-version` to 3.15;
  remove the marker; build the image on a remote host; commit

## 2. Docs and archive

- [ ] 2.1 Update the docs that name the Python version
- [ ] 2.2 Run `scripts/gate.sh`, archive the change, then validate all specs strictly
