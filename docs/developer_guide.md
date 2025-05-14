# TotalControl Developer Guide

This guide provides information for developers looking to contribute to TotalControl or understand its internal workings.

## Project Architecture

The project is broadly divided into two main phases of development, reflected in the codebase:

**Phase 1: Parametric G-Code Generation (Primarily in `core/`)**
*   **`core/gcode_generator.py`**: The main engine for converting JSON-based path descriptions (lines, arcs, Béziers, etc.) into executable G-code.
*   **`core/segment_primitives.py`**: Contains functions to generate G-code for individual geometric primitives.
*   **`core/transform.py`**: Handles geometric transformations (e.g., scale, rotate, offset) applied to path segments.
*   **`core/input_handler.py`**: Provides a way to directly generate G-code for specific shapes or test patterns.
*   **Data Flow (Phase 1):** JSON describing paths -> `core/gcode_generator.py` -> Raw G-code output.

**Phase 2: AI-Driven Path Optimization (Primarily in `core/optimizer/`)**
*   **`core/optimizer/gcode_optimizer.py`**: Orchestrates the G-code optimization process. It takes G-code (potentially from Phase 1 or an external slicer) and applies travel minimization.
*   **`core/optimizer/gcode_parser.py`**: Parses input G-code lines into structured `GCodeCommand` objects.
*   **`core/optimizer/gcode_segmenter.py`**: Segments the parsed G-code into layers and then into logical `PrintSegment` objects (e.g., extrude, travel) based on feature types.
*   **`core/optimizer/path_optimization.py`**: Implements path optimization algorithms like Nearest Neighbor (NN) and 2-opt to reorder `PrintSegment` objects.
*   **`core/optimizer/gcode_generator.py`**: Regenerates G-code commands based on the optimized order of segments. Note: This is distinct from `core/gcode_generator.py`.
*   **Data Flow (Phase 2):** Input G-code lines -> Parser -> Segmenter -> Optimizer (NN, 2-opt) -> Regenerator -> Optimized G-code lines.

**Other Key Directories:**
*   **`modules/`**: Intended for future, more advanced, and potentially pluggable functionalities (e.g., `ai_pathing.py`).
*   **`example_tests/`**: Contains example G-code files (`gcode_test_files.py`) used for testing and demonstration, and Pytest configuration (`conftest.py`).
*   **`main.py`**: The main script to run demonstrations, currently focused on showcasing Phase 2 optimization.

Refer to the `DEVELOPMENT.ini` for a detailed roadmap and current development status.

## Contribution Guidelines

Please refer to the `CONTRIBUTING.md` file at the root of the project for general contribution guidelines. Key points for developers include:
*   **Code Style:** Aim for PEP 8 compliance. Consider using a formatter like Black or Ruff to maintain consistency.
*   **Modularity:** Strive to keep functions and modules focused on specific tasks.
*   **Documentation:** Add docstrings to new functions and classes. Update relevant documentation in the `docs/` folder if your changes impact architecture or user-facing behavior.
*   **Testing:**
    *   When adding new features or fixing bugs, consider adding unit tests.
    *   The `example_tests/` directory can be used for integration-style tests.
    *   (Future: Define a more formal testing strategy and how to run tests, e.g., `pytest`).
*   **Commit Messages:** Write clear and concise commit messages explaining the "what" and "why" of your changes.

## Key Algorithms and Concepts

*   **Phase 1 (Parametric G-Code Generation):**
    *   Processing of structured JSON inputs defining geometric paths.
    *   Application of transformations.
*   **Phase 2 (AI Path Optimization):**
    *   **G-Code Parsing & Segmentation:** Breaking down G-code into manageable, typed segments.
    *   **Travel Minimization:**
        *   **Nearest Neighbor (NN):** A heuristic to quickly find a good initial order for print segments within a feature block.
        *   **2-opt:** An iterative local search algorithm to refine the order produced by NN, aiming to reduce total travel distance by swapping pairs of segments.
    *   **Feature Print Order (`FEATURE_PRINT_ORDER`):** A predefined order (e.g., perimeters before infill) to maintain structural integrity and print quality. Optimization is typically applied to segments within the same feature type.

## Setting up Development Environment

Follow the installation steps in `getting_started.md`. For development, ensure you have any additional tools (e.g., linters, testing frameworks) installed.

We encourage you to explore the code, experiment, and share your insights or contributions!
