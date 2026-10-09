# project-tooling Specification

## Purpose
Defines how the xincord repository is packaged and which automated checks guard every commit.

## Requirements

### Requirement: Two distributions share the xincord namespace
The repository SHALL build a `xincord` distribution providing the import package `xincord.core`
and a `xincord-plugins` distribution providing `xincord.plugins`. Neither distribution SHALL ship
`xincord/__init__.py`, so `xincord` stays a namespace that both can extend.

#### Scenario: Both import packages load
- **WHEN** the workspace is synced and `xincord.core` and `xincord.plugins` are imported
- **THEN** both imports succeed

#### Scenario: xincord is a namespace package
- **WHEN** the `xincord` package is inspected after import
- **THEN** it has no `__file__` and its search path covers both distributions

### Requirement: Python sources contain no CJK characters
The pre-commit configuration SHALL reject a Python file that contains a CJK character: CJK
symbols and punctuation, kana, CJK ideographs (including extensions and compatibility
ideographs) or fullwidth forms. Other non-ASCII characters SHALL be allowed.

#### Scenario: CJK ideograph is rejected
- **WHEN** a Python file contains a CJK unified ideograph
- **THEN** the check reports that file

#### Scenario: Fullwidth punctuation is rejected
- **WHEN** a Python file contains a fullwidth comma or an ideographic full stop
- **THEN** the check reports that file

#### Scenario: Other text passes
- **WHEN** a Python file contains only ASCII, accented Latin letters, or emoji
- **THEN** the check passes

### Requirement: Commit messages are ASCII Conventional Commits
The commit-msg hook SHALL accept a message only when its first line is `type(scope): subject` or
`type: subject`, the type is one of feat, fix, test, refactor, docs, build, ci or chore, the scope
is core, build, ci, docs or `plugin-<name>` in lowercase kebab case, and the whole message is
ASCII. Comment lines and everything after the scissors line of `git commit -v` SHALL be ignored.

#### Scenario: Valid message is accepted
- **WHEN** the message is `feat(plugin-auto-role): assign roles on join` with an ASCII bullet body
- **THEN** the hook accepts it

#### Scenario: Non-ASCII text is rejected
- **WHEN** the subject or the body contains a CJK character
- **THEN** the hook rejects the message and names the offending line

#### Scenario: Unknown type or scope is rejected
- **WHEN** the type is `feature` or the scope is `Core`
- **THEN** the hook rejects the message

#### Scenario: Comments and the verbose diff are ignored
- **WHEN** non-ASCII text appears only in `#` comment lines or below the scissors line
- **THEN** the hook accepts the message

### Requirement: Commit messages carry no tool attribution
The commit-msg hook SHALL reject a message with a tool attribution line: a `Co-Authored-By:` or
`Claude-Session:` trailer, or `Generated with [Claude Code]`, in any letter case. Comment lines and
the verbose diff SHALL be ignored as above.

#### Scenario: Attribution lines are rejected
- **WHEN** the body contains a `Co-Authored-By:` or `Claude-Session:` line, or `Generated with [Claude Code]`
- **THEN** the hook rejects the message and names the offending line
