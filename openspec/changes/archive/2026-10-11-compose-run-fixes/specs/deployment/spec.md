## ADDED Requirements

### Requirement: No cursor position requests
The image SHALL set `PROMPT_TOOLKIT_NO_CPR=1`, so the console never asks a terminal that nobody
attached for the cursor position.

#### Scenario: Image environment
- **WHEN** the Dockerfile is read
- **THEN** its runtime stage sets `PROMPT_TOOLKIT_NO_CPR=1`
