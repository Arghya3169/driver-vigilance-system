# Contributing to Driver Vigilance & Safety System

Thank you for your interest in contributing! We welcome contributions to help improve automotive safety and fatigue detection algorithms.

## How to Contribute

### 1. Reporting Bugs
- Search existing issues to verify the bug hasn't already been reported.
- Open a new issue with a clear title, environment details (Python version, OS, camera type), reproduction steps, and error traces.

### 2. Suggesting Features
- Open an issue describing your proposed feature, why it is useful, and potential implementation approaches.

### 3. Submitting Pull Requests
1. Fork the repository on GitHub.
2. Create a feature branch:
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. Make your code changes following PEP 8 conventions.
4. Ensure all automated tests pass:
   ```bash
   python -m unittest discover -s tests -p "test_*.py"
   ```
5. Commit your changes with a descriptive commit message:
   ```bash
   git commit -m "feat(vision): improve eye closure smoothing under low light"
   ```
6. Push to your fork:
   ```bash
   git push origin feature/amazing-feature
   ```
7. Open a Pull Request with a summary of the changes and test results.

## Code Standards
- Adhere to **PEP 8** style guidelines.
- Add unit tests under `tests/` for new mathematical or decision logic.
- Ensure non-blocking background threads properly release system resources.

## License
By contributing to this repository, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
