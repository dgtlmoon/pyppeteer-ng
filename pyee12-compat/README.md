# pyee 12 Compatibility Test Suite

This directory contains test files created to validate compatibility with pyee >=12.0.0.

## Test Files Overview

- **basic_websocket_test.py** - Simple websocket connection test
- **comprehensive_connection_test.py** - Extended connection tests covering various edge cases
- **connection_stability_test.py** - Tests for connection stability over time
- **connection_stress_test.py** - Stress tests for websocket connections
- **connection_test_script.py** - Core connection test script
- **cpu_verification.py** - CPU usage verification during connection operations
- **direct_test_runner.py** - Utility for running tests directly
- **final_connection_test.py** - Final validation tests for connection functionality
- **pyee_compatibility_test.py** - Direct tests for pyee compatibility
- **real_websocket_test.py** - Tests with real websocket connections
- **simple_connection_test.py** - Basic connection tests
- **simplified_test.py** - Simplified test cases
- **test_connection_fix.py** - Tests for connection fixes
- **unit_test.py** - Unit tests for specific components
- **websocket_connection_test.py** - Tests for websocket transport layer

## Running the Tests

To run individual tests:

```bash
# Running a specific test
python -m pyee12-compat.pyee_compatibility_test

# Running connection tests
python -m pyee12-compat.connection_test_script
python -m pyee12-compat.comprehensive_connection_test

# Running the websocket tests
python -m pyee12-compat.websocket_connection_test
python -m pyee12-compat.basic_websocket_test
```

To run all tests:

```bash
# Run all tests in the directory
for test in pyee12-compat/*.py; do
    if [[ $test != *"__"* ]]; then  # Skip __init__.py or similar
        echo "Running $test"
        python -m "$test"
    fi
done
```

These tests verify compatibility with pyee >=12.0.0, focusing on proper event handling, connection stability, and exception handling.