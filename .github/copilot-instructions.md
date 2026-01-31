# Copilot Development Instructions

## Makefile Usage (MANDATORY)

Always use the Makefile for development tasks. Never run raw `pytest` or `ruff` commands directly.

### Quick Reference

| Task | Command | Description |
|------|---------|-------------|
| Run tests | `make test` | Run pytest suite |
| Run linter | `make lint` | Run ruff lint |
| Format code | `make format` | Auto-format with ruff |
| Full check | `make check` | Run lint + coverage |
| Coverage report | `make coverage` | Run pytest with coverage |
| Install dev deps | `make install-dev` | Install package + dev dependencies |
| Clean artifacts | `make clean` | Remove temp artifacts |
| See all targets | `make help` | Show all available commands |

### Development Workflow

1. **Before making changes**: Run `make check` to establish baseline
2. **After making changes**: Run `make check` to verify no regressions
3. **Full cleanup**: Use `make clean` for temp artifacts

**Always prefer `make check` for validation.** Do not run `pytest` or `ruff` directly—use `make test`, `make lint`, or `make check`.

### Version Management

- `make bump-patch` - Bump patch version and create git tag
- `make push` - Push commits and tags to origin

## Testing Guidelines

- Aim for good test coverage
- Review tests periodically to consolidate/parameterize and remove redundancy
- Use fixtures from `tests/conftest.py` instead of duplicating setup code
- Prefer parameterized tests for similar test cases

## Code Style

- Do not use heredocs or random shell commands
- Prefer `make` and ecosystem tools (pip) over manual operations
- Debug issues systematically - search for and review documentation as needed
- Before adding new functionality, check for existing helpers or duplicated logic and refactor for reuse.
- Avoid silent exception handling; log warnings/errors using the project logger instead of swallowing exceptions.

## Coding Style Guidelines

When contributing to this project, please adhere to the following coding style guidelines:

* SPACES, not TABS, for indentation. Use 4 spaces per indentation level.
* Code in a functional style, with concise functions that do one thing only.
* NEVER duplicate code. Always re-use existing code or create new helper functions. If they are reusable, add them to `utils.py` as appropriate.
* When importing, prefer explicit imports (`from sys import stderr`) rather than just importing the module. A critical example is doing `from os.path import join, dirname, abspath` instead of `import os` and then using `os.path.join()`, etc. Never mind how many imports this creates; explicit imports are preferred for clarity.
* Inside a package, prefer package-relative imports (`from .utils import helper_function`) rather than absolute imports (`from trmnl_server.utils import helper_function`).
* When creating new functions, include type hints for all parameters and return values.
* Do not create one-liner wrappers around existing/internal module functions unless absolutely necessary. Use the public ones instead.
* When considering creating utility functions, try not to create one or two-liners. Inline the logic instead if they are that simple.
* Add utility functions to `utils.py` and constants to `config.py`, making sure to import them where needed and that any major configuration parameters are handled in a consistent way.
* NEVER add import statements inside functions or methods. Add any and all imports at the top of the file.
* Before writing new helpers or adding inline logic for things that might be reusable, check if there are existing ones that can be re-used or adapted.
