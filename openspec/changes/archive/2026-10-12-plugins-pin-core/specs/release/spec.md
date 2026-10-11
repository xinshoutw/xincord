## MODIFIED Requirements

### Requirement: Signed release tags
Pushing a `v*` tag SHALL run the release workflow, which SHALL fail unless the tag is an annotated
tag with a valid signature by a GPG key of the repository owner's GitHub account and names the
version that both distributions declare. `scripts/release_version.py` SHALL print that version and
fail when the distributions disagree, `xincord-plugins` does not require `xincord` at exactly
that version, or a given tag names another version.

#### Scenario: Trigger and signature
- **WHEN** `.github/workflows/release.yml` is read
- **THEN** it runs on pushed `v*` tags and on a manual dispatch, and on a tag it imports the owner's
  GitHub GPG keys and verifies the tag before anything is built

#### Scenario: Matching versions
- **WHEN** both distributions declare 1.2.3, the plugins require `xincord==1.2.3`, and the tag
  is `v1.2.3` or no tag is given
- **THEN** `release_version` returns `1.2.3`

#### Scenario: Mismatched versions
- **WHEN** the distributions declare different versions, or the tag names another version
- **THEN** `release_version` fails with a message naming the versions, and the script exits 1

#### Scenario: Plugins pinned to their core
- **WHEN** `xincord-plugins` requires another version of `xincord`, or none
- **THEN** `release_version` fails with a message naming the requirement, and the script exits 1
