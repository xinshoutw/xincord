# Spec Delta

## Purpose

Gives the core and plugins one durable, async store for their data: JSON values by namespace and
key, plus plugin-defined tables, all in one SQLite database.

## ADDED Requirements

### Requirement: Values are stored by namespace and key
The store SHALL save JSON values under a namespace and a key. Getting a missing key SHALL return
nothing; deleting SHALL report whether the key existed; listing a namespace SHALL return its keys
or items ordered by key. Namespaces SHALL NOT see each other's keys.

#### Scenario: Value round-trips
- **WHEN** a nested JSON value is put and then read back
- **THEN** the same value is returned

#### Scenario: Missing key and delete
- **WHEN** a missing key is read, and an existing and a missing key are deleted
- **THEN** the read returns nothing and the deletes report true and false

#### Scenario: Namespaces are isolated and listed in key order
- **WHEN** keys are put into two namespaces
- **THEN** listing one namespace returns only its keys and items, ordered by key

### Requirement: Only JSON values are accepted
Putting a value that is not representable as standard JSON (for example a set, or NaN) SHALL fail
without storing anything.

#### Scenario: Non-JSON value is rejected
- **WHEN** a set or NaN is put
- **THEN** the put fails and the key stays absent

### Requirement: Awaited writes are durable
When a write has been awaited, the change SHALL be committed: another connection to the same file
sees it, and it survives closing and reopening the store.

#### Scenario: Value survives reopening
- **WHEN** a value is put, the store is closed and the same file is opened again
- **THEN** the value is returned

#### Scenario: Commit is visible to another connection
- **WHEN** a value is put and awaited
- **THEN** a separate sqlite3 connection to the file reads it

### Requirement: Read-modify-write is atomic
Updating a key with a function SHALL apply the function to the current value (nothing if absent)
and store the result in one step, so concurrent updates never lose a write.

#### Scenario: Concurrent increments
- **WHEN** one hundred updates that each add one run concurrently
- **THEN** the stored value is one hundred

### Requirement: Plugins can use their own tables
Running a function with the connection SHALL execute it in the store's transaction model: the
work is committed when the function returns and rolled back when it raises.

#### Scenario: Own table is created and queried
- **WHEN** a function creates a table and inserts rows, and a later function queries them
- **THEN** the query returns the inserted rows

#### Scenario: Failure rolls back
- **WHEN** a function writes and then raises
- **THEN** the error propagates and none of its writes are kept

### Requirement: Corrupt databases are never reset
Opening a file that is not a valid SQLite database SHALL fail and leave the file unchanged.

#### Scenario: Garbage file
- **WHEN** the store is opened on a file containing arbitrary bytes
- **THEN** opening fails and the file's bytes are unchanged

### Requirement: Keyed locks serialize multi-step flows
The store SHALL hand out one asyncio lock per key, the same lock for equal keys and different
locks for different keys.

#### Scenario: Same key, same lock
- **WHEN** a lock is requested twice for the same key and once for another key
- **THEN** the first two are the same lock and the third is different
