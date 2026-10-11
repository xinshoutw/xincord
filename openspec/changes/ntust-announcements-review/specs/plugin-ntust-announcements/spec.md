## ADDED Requirements

### Requirement: Answers that hold a refused text are retried
`config.yaml` SHALL take `reject-texts`, a list of texts, by default one: three backticks. An
answer of the model that holds one of them SHALL be a failed attempt, retried as any failed
attempt, and the log SHALL name the text. An empty list SHALL refuse nothing; a blank text SHALL
stop the plugin from loading, with the key named.

#### Scenario: Fenced answer
- **WHEN** the model answers with a fenced block, then with plain Markdown
- **THEN** the first attempt fails naming the refused text, and the plain answer is the conversion
  after the first retry wait

#### Scenario: Nothing refused
- **WHEN** `reject-texts` is `[]` and the model answers with a fenced block
- **THEN** that answer is the conversion

#### Scenario: Blank text
- **WHEN** `reject-texts` holds an empty text
- **THEN** the plugin does not load and the error names `reject-texts`

### Requirement: Posted messages are remembered
The plugin SHALL store each message that it posts for an announcement under the message's ID in
the store's namespace `NtustAnnouncements.posts`, with the announcement's board, URL and title,
the channel and the IDs of all the announcement's messages. A failure to store SHALL be logged and
SHALL NOT post the announcement again.

#### Scenario: Two messages
- **WHEN** an announcement is posted in two messages
- **THEN** both IDs are stored, each with the announcement, the channel and both IDs

### Requirement: A reviewer's cross mark redoes a post
`config.yaml` SHALL take `reviewers`, user IDs, empty by default. When one of them adds ❌ to a
stored message, the plugin SHALL fetch the article again, convert it, have the model review the
conversion with `review-prompt` (keeping the conversion when every review attempt fails), post the
result to the same channel and store it, then delete the old messages and forget them. Reactions of
others or with other emojis, unstored messages and a second ❌ during a redo SHALL be ignored.

#### Scenario: Redo
- **WHEN** a reviewer adds ❌ to the second message of an announcement posted in two messages
- **THEN** the article is fetched and converted again, the review prompt holds the HTML and the new
  conversion, the reviewed text is posted, and both old messages are deleted and forgotten

#### Scenario: Ignored reactions
- **WHEN** a user who is no reviewer adds ❌, a reviewer adds another emoji, or a reviewer adds ❌
  to a message the plugin did not post
- **THEN** nothing is fetched, posted or deleted

#### Scenario: One redo at a time
- **WHEN** a reviewer adds ❌ to an announcement twice before its redo ends
- **THEN** the article is redone once

#### Scenario: The old post stays
- **WHEN** the article page fails during a redo, or the channel refuses the new post
- **THEN** the old messages stay, and a warning names the announcement

#### Scenario: The review fails
- **WHEN** every review attempt fails
- **THEN** the new conversion is posted, with a warning

### Requirement: The review prompt
`config.yaml` SHALL take `review-prompt`, which SHALL hold `{{html}}` and `{{markdown}}`. When it
is missing, the review prompt of the bundled `config.yaml` SHALL be used. Errors SHALL name the
key.

#### Scenario: Missing key
- **WHEN** `config.yaml` has no `review-prompt` and a reviewer redoes a post
- **THEN** the review uses the bundled file's prompt

#### Scenario: Missing token
- **WHEN** `review-prompt` lacks `{{markdown}}`
- **THEN** the plugin does not load and the error names `review-prompt`

## MODIFIED Requirements

### Requirement: The prompt is filled in one pass
The `prompt` and the `review-prompt` SHALL be filled in one pass: `{{page_title}}` with the link's
title, `{{page_url}}` with its URL, `{{base_url}}` with `https://` and the URL's host
(`ntust.edu.tw` when it has none), `{{now}}` with the local time as `yyyy-MM-dd HH:mm:ss`,
`{{html}}` with the article's HTML and `{{markdown}}` with the conversion under review (empty in
`prompt`); values are inserted as they are.

#### Scenario: Tokens
- **WHEN** the prompt holds every token and is filled for an article at 2026-10-11 09:05:03, with
  a conversion under review
- **THEN** each token is replaced with its value

#### Scenario: Values as they are
- **WHEN** a title holds `{{html}}`
- **THEN** the filled prompt shows `{{html}}` in place of the title, not the article's HTML
