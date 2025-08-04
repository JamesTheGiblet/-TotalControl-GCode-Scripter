# 🌀 TotalControl: An AI-Powered GCode Invocation Engine

## **MODULARITY IS MYTHOS // GLYPH IS IDENTITY // DESIGN IS RITUAL**

**TotalControl** is an intelligent artifact that transforms GCode scripting into an adaptive ritual. By leveraging AI-driven optimization, material-aware configurations, and real-time feedback, it moves beyond static divination and into dynamic fabrication control. Whether crafting nonplanar paths, optimizing extrusion dynamics, or predicting print errors, TotalControl brings intelligent automation to your 3D invocations.

-----

## 🌟 Key Invocations & Core Glyphs

* ✅ **Structured Path to G-Code Generation** – Convert JSON-based path descriptions (lines, arcs, Béziers, spirals, repeats, transforms) into executable G-code (Phase 1 Complete).
* ✅ **Initial AI-Driven Travel Optimization** – Implemented Nearest Neighbor and 2-opt algorithms to reorder printing segments within layers, reducing non-extruding travel moves and respecting feature invocation order (e.g., perimeters before infill) (Phase 2 In Progress).
* ✅ **Redundant Move Elimination** – Automatically identifies and removes unnecessary travel commands.
* 🅿️ **Advanced AI-Driven Optimization (Planned)** – Future enhancements will include fine-tuning extrusion rates, speeds, acceleration, and jerk control based on geometry and material properties.
* 🅿️ **Intent-Based GCode Generation (Planned)** – Future support for defining paths via higher-level directives, potentially including natural language.
* 🅿️ **Error Prediction & Correction (Planned)** – Future goals include proactive detection of print failures and automated corrective strategies.
* 🅿️ **Material-Aware Adaptation (Planned)** – Future capabilities to adjust parameters dynamically based on material behavior.
* ✅ **Extensibility** – A modular framework built for custom commands, integration with slicers, and advanced fabrication techniques.

-----

### 🎯 Current Status & Path of Evolution

The project is actively in **Phase 2: AI-Driven Path Optimization**, with a current focus on:

* Solidifying and verifying initial Travel Minimization algorithms (Nearest Neighbor + 2-opt).
* Correcting and refining layer reassembly logic post-optimization.

**Next Milestones:**

* Complete robust benchmarking of the current travel minimization.
* Begin exploration and development for Deposition Sequence Optimization within layers.

For a detailed development plan and progress tracking, please see the `DEVELOPMENT.ini` file in this repository.

-----

### 📂 Architectural Glyphs

The project is evolving. The core structure from Phase 1, which handles JSON to G-code generation, includes:

totalcontrol/  
│  
├── core/  
│   ├── intent_interpreter.py     # Maps structured/natural invocations to GCode actions  
│   ├── ai_optimizer.py           # Adjusts path smoothness, extrusion, acceleration  
│   ├── error_detection.py        # Predicts print failures and generates solutions  
│   ├── material_model.py         # Adapts printing based on filament/material properties  
│   ├── gcode_generator.py        # Generates dynamic, optimized GCode output  
│   ├── utils.py                  # Common helpers  
│  
├── modules/  
│   ├── ai_pathing.py             # Advanced path refinement (Voronoi, spiral, lattice)  
│   ├── real_time_tuning.py       # Live adjustment engine for supported firmware  
│   ├── heuristics.py             # Rule-based anomaly detection and correction  
│  
├── tests/  
│   ├── test_optimization.py      # Unit tests for AI-enhanced tuning  
│   ├── test_gcode.py             # Validates generated GCode quality  
│  
├── docs/  
│   ├── getting_started.md        # Installation & setup guide  
│   ├── developer_notes.md        # Architecture details for contributors  
│  
├── main.py                       # Entry point  
└── README.md

-----

### 🔧 The Ritual Unfolds

**TotalControl** allows builders to define GCode paths using two approaches:

* **🔹 Structured Parametric Invocations** – Define precise control parameters (e.g., Bézier curves, Voronoi patterns).
* **🔹 Higher-Level Intent Statements** – Use natural language (e.g., "create a strong, lightweight infill pattern").

The AI presence translates this input into optimized print paths, extrusion rates, speed variations, and hardware-compatible GCode.

## **AI-Powered Optimization Layers**

* 🧠 **Path Efficiency Analysis** – Minimizes travel moves, enhances layer adhesion.
* 🧠 **Extrusion Adaptation** – Adjusts flow based on geometry and material properties.
* 🧠 **Acceleration & Jerk Control** – Custom tuning for print stability and vibration reduction.
* 🧠 **Dynamic Material Response** – The AI adapts print settings based on a filament's behavior.

## **Error Prediction & Correction**

* 🚨 **Simulation-Based Failure Prediction** – Pre-print analysis detects collisions and layer separation risks.
* 🚨 **Heuristic Anomaly Detection** – Rule-based identification of common print issues (e.g., thin walls, overhang stability).
* 🚨 **Reinforcement Learning from Past Invocations** – The AI refines settings based on historical success/failure patterns.
* 🚨 **Automated Fixes & Live Adjustments (optional)** – Suggested corrective actions before or during the printing ritual.

-----

### 🖥️ Integration & Use Cases

## **Standalone Processing**

* 🔹 Generate optimized GCode from raw paths without relying on traditional slicers.
* 🔹 AI-powered fine-tuning for precision fabrication projects.

## **Firmware-Aware Adaptation**

* 🔹 Works with Marlin, Klipper, and other adaptable firmwares.
* 🔹 Supports real-time parameter tuning for dynamic material adjustments.

## **Advanced Use Cases**

* ✨ **Nonplanar extrusion** – Zigzag deposition, dynamic layer height modulation.
* ✨ **Procedural lattice structures** – Optimized for mechanical properties.
* ✨ **3D printed scaffolding and parametric supports** – AI-driven geometry for strength & flexibility.
* ✨ **Sustainable material experimentation** – Adaptive settings for novel biomaterials.

-----

### 🛠️ The Initiation Ritual

Clone the repository and install dependencies:

```bash
git clone https://github.com/JamesTheGiblet/TotalControl.git
cd TotalControl
pip install -r requirements.txt
```

Run core processing:

```bash
python main.py
```

For real-time printer tuning, ensure your firmware supports dynamic GCode modification.

-----

### 🚀 Communal Invocations

**TotalControl** thrives on open development—whether exploring adaptive fabrication, optimizing procedural paths, or integrating real-time print intelligence, your glyphs are always welcome\!

Pull requests, discussions, and ideas are encouraged—let’s push the boundaries of AI-powered fabrication together. 🚀
