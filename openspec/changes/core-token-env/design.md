## Decisions

### The environment over the config

`XINCORD_TOKEN` wins over `config.yaml`'s `token`, as `--token` did, so an operator moves the
token to `.env` without editing `config.yaml` first. An empty value counts as unset: compose
passes `${XINCORD_TOKEN:-}`, an empty string, when `.env` has none. The variable is read once, in
`run`, next to the config; a reload does not read it again, as it never read the token again.

The environment is not secret from the host's administrators (`docker inspect` shows it), who
can read `config.yaml` as well; what it avoids is the command line, which every user of the host
can list.

### No --token

v3 behaved differently: `-t <token>` passed the token on the command line. The option goes rather
than stays with a warning, since a warning comes after the token was listed. argparse rejects it as
an unknown option, with status 2.
