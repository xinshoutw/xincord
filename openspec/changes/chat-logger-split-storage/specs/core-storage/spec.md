## MODIFIED Requirements

### Requirement: Plugins can use their own tables
Running a function with the connection SHALL execute it in the store's transaction model: the
work is committed when the function returns and rolled back when it raises or when its commit
fails, so that no later call commits it.

#### Scenario: Own table is created and queried
- **WHEN** a function creates a table and inserts rows, and a later function queries them
- **THEN** the query returns the inserted rows

#### Scenario: Failure rolls back
- **WHEN** a function writes and then raises
- **THEN** the error propagates and none of its writes are kept

#### Scenario: Failed commit rolls back
- **WHEN** a function writes and its commit fails, as when another connection holds a lock on the
  file past the wait, and a later call commits
- **THEN** the error propagates and none of the failed function's writes are kept
