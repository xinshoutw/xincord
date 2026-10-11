## ADDED Requirements

### Requirement: The distributions carry the license
Both distributions SHALL carry the AGPL's text: `pyproject.toml` and the plugins' `pyproject.toml`
SHALL list `LICENSE` in `license-files`, and the plugins' `LICENSE` SHALL equal the root file.

#### Scenario: Declared and equal
- **WHEN** both `pyproject.toml` files and both `LICENSE` files are read
- **THEN** each project lists `LICENSE` in `license-files` and the two files are equal
