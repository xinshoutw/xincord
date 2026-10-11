## ADDED Requirements

### Requirement: Deleted texts can be kept
`config.yaml` SHALL take `keep_deleted`, false by default. With it true, a deleted message, alone
or in a bulk deletion, SHALL stay stored after its deletion is logged, until the retention period
removes it, as v3 kept it. A value that is not a boolean SHALL stop the plugin from loading, with
the key named.

#### Scenario: Kept
- **WHEN** `keep_deleted` is true and a stored message, then three in a bulk deletion, are deleted
- **THEN** the four deletions are logged and the four messages are still stored

#### Scenario: Default
- **WHEN** `plugins/ChatLogger/config.yaml` has no `keep_deleted` and a stored message is deleted
- **THEN** the message is no longer stored

#### Scenario: Invalid value
- **WHEN** `keep_deleted` is `maybe`
- **THEN** the plugin does not load and the error names `keep_deleted`

## MODIFIED Requirements

### Requirement: Deletions of stored messages are logged
When a stored message is deleted, alone or in a bulk deletion, the plugin SHALL remove it from the
store, unless `keep_deleted` keeps it, and post `on-msg-delete` to the detecting listen channels
with the author's values, `cl_channel_mention`, `cl_category_mention` (`-` without a category),
`cl_change_count` and `cl_msg_before`. An author who is no longer a member SHALL show as a mention
of the stored ID, with `-` for the names and no thumbnail.

#### Scenario: Delete
- **WHEN** the stored `hi`, edited once, by member 7 in channel 30 of category 20 is deleted, in an
  en-US or a zh-TW guild where listen channel 5 detects channel 30
- **THEN** listen channel 5 gets v3's delete embed in that locale with the member, the category, the
  channel, 1 change and `hi`, and the message is no longer stored

#### Scenario: Author gone
- **WHEN** the author is no longer a member of the guild
- **THEN** the embed shows the mention of the stored author ID and no thumbnail

#### Scenario: Not stored
- **WHEN** a message that is not stored is deleted
- **THEN** nothing is posted and no member is fetched

#### Scenario: Not detected
- **WHEN** no listen channel detects the channel
- **THEN** the message is no longer stored, nothing is posted and no member is fetched

#### Scenario: Deleted at once
- **WHEN** `log_all` is false and a message and its deletion reach the plugin together
- **THEN** the deletion is logged and the message is not stored

#### Scenario: Bulk deletion
- **WHEN** three stored messages of one author and one message that is not stored are deleted at
  once
- **THEN** the three are posted oldest first, the author is fetched once, and none is stored
