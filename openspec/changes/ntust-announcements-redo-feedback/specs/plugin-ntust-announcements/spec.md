## ADDED Requirements

### Requirement: A redo shows that it runs
When the plugin takes a reviewer's ❌ for a redo, it SHALL add ⏳ (U+23F3) to the marked message
before the article is fetched. When the old post stays, because the article or the new post failed
or the redo raised, it SHALL remove its ⏳. A reaction that Discord refuses SHALL be logged and
SHALL NOT stop the redo.

#### Scenario: Sign
- **WHEN** a reviewer adds ❌ to a stored message
- **THEN** the bot adds ⏳ to that message before the article is fetched, and the redo replaces the
  post

#### Scenario: The old post stays
- **WHEN** the article page fails during the redo, or the redo raises
- **THEN** the bot removes its ⏳ from the marked message

#### Scenario: Refused reaction
- **WHEN** Discord refuses the ⏳
- **THEN** a warning names the message and the post is still redone
