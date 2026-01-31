# Contributing

Thank you for your interest in contributing! This document provides guidelines and information for contributing to the project.

## Contribution Guidelines

We welcome contributions that:

- Improve or enhance core functionality
- Fix bugs in existing features
- Add essential features that align with the project's goals

## Development Setup

1. Fork and clone the repository
2. Install the package with development dependencies

   ```bash
   pip install -e ".[dev]"
   ```

3. Run tests before submitting changes:

   ```bash
   python -m pytest
   ```

4. Build the frontend:
   The project includes a Svelte-based frontend that must be built for the app to function correctly.

   ```bash
   cd daggr/frontend
   npm install
   npm run build
   cd ../..
   ```

5. Format your code using Ruff:

   ```bash
   ruff check --fix --select I && ruff format
   ```

## Pull Request Process

1. Ensure your code passes all tests
2. Format your code using Ruff
3. Update documentation if necessary
4. Submit a pull request with a clear description of your changes

Thank you for contributing!
