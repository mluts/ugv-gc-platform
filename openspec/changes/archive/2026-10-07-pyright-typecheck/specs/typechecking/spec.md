# typechecking Specification

## Purpose

Ensures the production code stays statically type-checked: one command runs the project's type checker over it, the verification loop always includes that command, and the convention is documented so new work keeps the baseline clean.

## ADDED Requirements

### Requirement: One command type-checks the project
`make typecheck` SHALL run the project's static type checker over the production package and SHALL exit with status 0 when the checker reports no errors.

#### Scenario: Clean tree passes
- **WHEN** the working tree contains no type errors and `make typecheck` is run
- **THEN** the command exits with status 0

#### Scenario: Type error is reported
- **WHEN** a type error is present in the code and `make typecheck` is run
- **THEN** the command exits non-zero and names the file and the error

### Requirement: Verification always type-checks
`make test-fast` and `make test` SHALL run the type checker as part of verification and SHALL fail when the checker reports errors, before a test run can report success.

#### Scenario: Fast verification fails on a type error
- **WHEN** a type error is present and `make test-fast` is run
- **THEN** the command fails and the checker's errors are shown

#### Scenario: Fast verification passes when clean
- **WHEN** the tree is clean of type errors and `make test-fast` is run
- **THEN** the command runs the fast test suite and exits with status 0

### Requirement: The type check covers production code only
The type checker SHALL analyze the production package and SHALL exclude the test suite, so test doubles may stay duck-typed without being reshaped to satisfy the checker.

#### Scenario: Test files are not analyzed
- **WHEN** the type checker runs
- **THEN** no diagnostic is reported for any file under `tests/`

#### Scenario: A duck-typed test double is accepted
- **WHEN** a test substitutes a hand-written fake for a production type
- **THEN** the type checker reports no error for that substitution

### Requirement: The codebase type-checks clean
The production package SHALL contain no type errors under the project's configured type-checking settings, and the gate SHALL be green on the checked-in tree.

#### Scenario: Clean baseline at introduction
- **WHEN** the type-checking gate is introduced
- **THEN** every type error present at that moment has been fixed and `make typecheck` exits with status 0

### Requirement: The convention is documented
The project's agent instructions SHALL state that the project type-checks with pyright, that `make typecheck` must pass before a commit, and the OpenSpec apply guidance SHALL require a passing type check when reporting a completed task.

#### Scenario: Agent instructions name the rule
- **WHEN** the project's `AGENTS.md` is consulted
- **THEN** it states that pyright is the project's type checker and that `make typecheck` must pass before committing

#### Scenario: Apply loop includes the checker
- **WHEN** the OpenSpec apply guidance in `openspec/config.yaml` is consulted
- **THEN** each task's stop-and-report step includes a passing `make typecheck`