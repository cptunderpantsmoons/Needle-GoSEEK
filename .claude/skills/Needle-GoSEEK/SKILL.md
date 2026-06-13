```markdown
# Needle-GoSEEK Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development patterns and conventions used in the Needle-GoSEEK Python codebase. You will learn how to structure files, write imports and exports, and follow commit and testing practices as observed in the repository. This guide is ideal for contributors aiming for consistency and maintainability in the project.

## Coding Conventions

### File Naming
- Use **snake_case** for all file names.
  - Example: `data_loader.py`, `user_utils.py`

### Import Style
- Prefer **relative imports** within modules.
  - Example:
    ```python
    from .utils import process_data
    from ..models import User
    ```

### Export Style
- Use **named exports**; explicitly define what is exported from a module.
  - Example:
    ```python
    def process_data(data):
        # processing logic
        return result

    __all__ = ['process_data']
    ```

### Commit Messages
- Freeform commit messages, often short (average 13 characters).
  - Example: `fix typo`, `add tests`, `update logic`

## Workflows

_No automated workflows detected in this repository._

## Testing Patterns

- **Testing Framework:** Not explicitly detected; framework is unknown.
- **Test File Naming:** Test files follow the pattern `*.test.*`.
  - Example: `user_service.test.py`, `data_loader.test.py`
- **Writing Tests:** Place test functions or classes in files matching the above pattern.
  - Example:
    ```python
    def test_process_data():
        assert process_data([1, 2, 3]) == expected_result
    ```

## Commands
| Command | Purpose |
|---------|---------|
| /test   | Run all test files matching `*.test.*` |
| /lint   | Lint the codebase for style consistency |
| /format | Auto-format code to match conventions   |
```
