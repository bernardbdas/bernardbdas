# Set shell
set shell := ["bash", "-c"]

# Default recipe: runs the full generation pipeline in a single command
default: run

# Run the stats generation pipeline and output SVGs to outputs/
run:
    uv run python main.py

# Install and sync dependencies with uv
sync:
    uv sync

# Run linter and formatting checks
lint:
    uv run ruff check .
    uv run ruff format --check .

# Auto-format and auto-fix lint issues
format:
    uv run ruff format .
    uv run ruff check --fix .

# Type check using mypy
typecheck:
    uv run mypy main.py

# Clean the cache directory to force a fresh fetch
clean-cache:
    rm -rf cache

# Clean output SVGs and cache
clean:
    rm -f outputs/*.svg
    rm -rf cache

# Force a fresh run: cleans cache and runs stats generation
force-run: clean-cache run

# Complete workflow: sync dependencies, verify linting, and generate stats
all: sync lint run
