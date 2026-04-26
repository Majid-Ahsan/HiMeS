# Code Quality Tools

This project uses several tools to ensure code quality and consistency.

## Tools

### 1. **mypy** - Static Type Checking

Type checking with strict rules to catch type errors before runtime.

**Configuration**: `pyproject.toml` → `[tool.mypy]`

**Run manually**:
```bash
make type-check
# or
uv run mypy src/mcp_caldav --ignore-missing-imports
```

**Key settings**:
- Strict type checking enabled
- Disallows untyped function definitions
- Checks untyped function calls
- Tests excluded from strict checking

### 2. **ruff** - Linting and Formatting

Fast Python linter and formatter that replaces multiple tools (flake8, isort, black, etc.).

**Configuration**: `pyproject.toml` → `[tool.ruff]`

**Run manually**:
```bash
# Check for issues
make lint

# Auto-fix issues (lint with --fix)
make lint  # ruff auto-fixes when possible

# Format code
make format
```

**Enabled rules**:
- `E`, `W` - pycodestyle errors and warnings
- `F` - pyflakes
- `I` - isort (import sorting)
- `B` - flake8-bugbear
- `C4` - flake8-comprehensions
- `UP` - pyupgrade
- `SIM` - flake8-simplify
- `TCH` - flake8-type-checking
- `TID` - flake8-tidy-imports
- `Q` - flake8-quotes
- `RUF` - ruff-specific rules

### 3. **pre-commit** - Git Hooks

Automatically runs quality checks before each commit.

**Configuration**: `.pre-commit-config.yaml`

**Setup**:
```bash
uv run pre-commit install
```

**Run manually**:
```bash
# Run on all files
make pre-commit-run
# or
uv run pre-commit run --all-files

# Run on staged files only
uv run pre-commit run
```

**Hooks configured**:
- Trailing whitespace removal
- End of file fixer
- YAML/JSON/TOML validation
- Large file detection
- Merge conflict detection
- Debug statement detection
- Ruff linting and formatting
- mypy type checking

## Workflow

### Before Committing

1. **Automatic checks** (via pre-commit hook):
   - Runs automatically when you `git commit`
   - Fixes auto-fixable issues
   - Blocks commit if errors remain

2. **Manual checks** (optional):
   ```bash
   # Run all checks
   make check

   # Or individually
   make lint
   make format
   make type-check
   ```

### CI/CD Integration

Add to your CI pipeline:

```yaml
- name: Code Quality Checks
  run: |
    uv sync --group dev
    uv run ruff check src/
    uv run ruff format --check src/
    uv run mypy src/mcp_caldav --ignore-missing-imports
```

## Ignoring Rules

### Ruff

Add to `pyproject.toml`:
```toml
[tool.ruff.lint.per-file-ignores]
"tests/*" = ["ARG", "S101", "PLR2004"]
```

### mypy

Add inline comments:
```python
some_code()  # type: ignore[error-code]
```

Or in `pyproject.toml`:
```toml
[[tool.mypy.overrides]]
module = "module.name"
ignore_missing_imports = true
```

## Common Issues and Fixes

### Import Sorting (I001)
```bash
uv run ruff check --fix src/  # Auto-fixes
```

### Type Annotations (UP006, UP035)
- Use `list` instead of `List`
- Use `dict` instead of `Dict`
- Use `X | Y` instead of `Union[X, Y]`
- Use `X | None` instead of `Optional[X]`

### Exception Handling (B904)
Always use `raise ... from err` or `raise ... from None`:
```python
except Exception as e:
    raise RuntimeError("message") from e
```

### Unused Arguments (ARG001)
Prefix with `_` or add `# noqa: ARG001`:
```python
def func(_unused_arg: int) -> None:  # or # noqa: ARG001
    pass
```

## Configuration Files

- `pyproject.toml` - mypy and ruff configuration
- `.pre-commit-config.yaml` - pre-commit hooks configuration
- `.ruff.toml` - Alternative ruff config (if needed)

## Dependencies

All quality tools are in the `dev` dependency group:

```bash
uv sync --group dev
```

This installs:
- `mypy>=1.8.0`
- `ruff>=0.4.0`
- `pre-commit>=3.6.0`
- `types-click>=7.1.0` (type stubs for click)
