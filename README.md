# Project: TotalControl

A smarter G-Code engine.

The Problem

Standard 3D printer slicers are straight-up dumb. They just follow a simple set of rules and make static G-code. They don't adapt to the geometry you're printing, they waste time on stupid travel moves, and they don't have a real feel for the material. To do anything truly advanced, you have to manually edit G-code, and that's a nightmare.

The Solution

A smarter G-code engine. TotalControl is a tool that takes a high-level description of a print path and uses AI to generate highly optimized, material-aware G-code. It's built to move beyond the limitations of traditional slicers, giving you a level of control that's impossible with off-the-shelf software.

What It Does (And Where It's Going)

This is an active project. Here's what's working now and what's planned.

    ✅ G-Code Generation: It reliably converts a JSON file describing paths into executable G-code. (Done)

    ✅ AI Travel Optimization: It uses Nearest Neighbor and 2-opt algorithms to reorder print segments and drastically cut down on wasted travel time. (In Progress)

    ✅ Redundant Move Cleanup: Automatically finds and deletes useless travel moves.

    🅿️ Advanced AI Optimization (Planned): The next step is to use AI to fine-tune extrusion rates, speeds, and acceleration based on the specific geometry of a print.

    🅿️ Intent-Based Generation (Planned): The future goal is to generate G-code from high-level commands, like "make a strong but lightweight infill."

    🅿️ Error Prediction (Planned): Eventually, the AI will be able to simulate a print and predict potential failures before they happen.

Current Status

We are currently in Phase 2, focusing on the AI-Driven Path Optimization. The core algorithms are in place, and the current work is focused on benchmarcking them and refining the logic to ensure it's robust.

For a detailed breakdown of the development plan, check out DEVELOPMENT.ini.

The Guts (Architecture)

The project is built to be modular so we can bolt on new features easily.

totalcontrol/
├── core/
│   ├── gcode_generator.py      # The core engine for turning paths into G-code.
│   ├── ai_optimizer.py         # The AI logic for path and travel optimization.
│   └── ... (other core modules)
├── modules/
│   └── ai_pathing.py           # Advanced path generation (e.g., nonplanar).
├── tests/
│   ├── test_optimization.py    # Unit tests for the AI optimizers.
│   └── test_gcode.py           # Validation tests for the generated G-code.
├── main.py                     # The main entry point for the script.
└── README.md

What It's Good For (Use Cases)

This isn't for printing another Benchy. This is for advanced fabrication.

    Nonplanar Printing: Create truly curved layers that follow a surface, making parts stronger and eliminating layer lines.

    Procedural Infill: Generate complex lattice structures or other infills that are optimized for strength and weight.

    Custom Supports: Design smart, parametric supports that are strong but easy to remove.

    Material Science: Experiment with new or difficult materials by giving the AI rules on how to handle them.

How to Run It

Clone the repo, install the dependencies, and run the main script.
Bash

git clone https://github.com/JamesTheGiblet/TotalControl.git
cd TotalControl
pip install -r requirements.txt
python main.py

How to Contribute

This is an open project for anyone who thinks standard slicers are too limiting.

    Fork the repo.

    Tackle one of the planned features or fix a bug.

    Submit a pull request with a clear description of what you've done.

License

This project is licensed under the MIT License.

Standard tools give you standard results. To do something new, you have to build a better tool. The code is the proof. Let's build it.
