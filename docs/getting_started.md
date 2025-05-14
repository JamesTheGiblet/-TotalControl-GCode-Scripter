# Getting Started with TotalControl G-Code Scripter

Welcome to TotalControl G-Code Scripter! This guide will help you get the project set up, understand its basic operation, and start exploring its capabilities.

## Prerequisites

*   Python 3.x
*   Git

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/TotalControl-GCode-Scripter.git
    cd TotalControl-GCode-Scripter
    ```

2.  **Set up a virtual environment (recommended) and install dependencies:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

## Running the Project

The `main.py` script serves as the primary entry point for demonstrating the current capabilities of TotalControl.

Currently, it is set up to:
1.  Process example G-code files (defined in `example_tests/gcode_test_files.py`).
2.  Apply the Phase 2 travel optimization logic (Nearest Neighbor + 2-opt) to these G-code files.
3.  Print the original and optimized G-code (or relevant statistics) to the console.

```bash
python main.py
Understanding the Output
When you run main.py, you will see console output detailing:

The G-code file being processed.
Logging information from the optimization process, including travel distances before and after optimization for different segments of the print.
Potentially, snippets of the original and optimized G-code.
For a high-level overview of features and the project's direction, refer to the main README.md. For a detailed development roadmap, see DEVELOPMENT.ini.