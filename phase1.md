# Project Documentation: Phase 1

This document outlines the structure and functionality of the TotalControl G-code generation system as of Phase 1.

## 1. `c:\Users\gilbe\Desktop\TotalControl\totalcontrol\main.py`

*   **Purpose**:
    This script serves as the main entry point and a demonstration platform for the entire G-code generation and (potential) optimization pipeline. It showcases how to use the various core modules to convert a JSON-based path description into G-code, and how to apply further operations like optimization or specific pathing algorithms.
*   **Key Functionalities/How it Works**:
    *   It defines an example JSON structure (`json_example`) representing a complex path with various segment types (lines, arcs, béziers, spirals, styles, repeats, structures), along with global modifiers and constraints.
    *   It also defines example `material_properties` and `printer_capabilities` dictionaries, which would be used by more advanced optimization routines.
    *   **Step 1**: Calls `generate_gcode_from_json` (from `core.gcode_generator`) to convert the `json_example` into a list of G-code commands.
    *   **Step 2**: Calls `optimize_gcode` (from `core.ai_optimizer`) to apply (currently basic) optimizations to the generated G-code.
    *   **Step 3**: Demonstrates calling a specific structure generator (`generate_gcode_lattice` from `modules.ai_pathing`) directly.
    *   **Steps 4 & 5**: Showcases how `apply_modifier` and `apply_constraint` (from `modules.ai_pathing`) can be called iteratively. It's important to note that `generate_gcode_from_json` already applies these global modifiers/constraints, so these steps are more for demonstrating the individual functions' usage.
*   **Role in Overall System**:
    `main.py` is the high-level orchestrator for demonstration. It simulates how a user or another system might provide input (JSON, material, printer data) and receive processed G-code. It ties together the generation, (potential) AI pathing, and optimization steps.

## 2. `c:\Users\gilbe\Desktop\TotalControl\totalcontrol\core\gcode_generator.py`

*   **Purpose**:
    This is the central engine responsible for generating G-code from structured path segment definitions provided in a Python dictionary format (typically parsed from JSON). It handles the logic for different segment types, including complex ones like styles, repeats, and structures, and applies transformations and global modifiers/constraints.
*   **Key Functionalities/How it Works**:
    *   `generate_gcode_segment(segment: dict)`:
        *   The primary dispatcher function. It takes a segment dictionary, identifies its `type` (e.g., "line", "arc", "repeat").
        *   Calls the appropriate specialized generator function for that type (e.g., `generate_gcode_line` from `segment_primitives.py`, or `generate_gcode_repeat` defined locally).
        *   If the segment dictionary contains a "transform" key, it calls `apply_transformation` (from `core.transform`) to modify the G-code generated for that segment.
    *   `generate_gcode_style(segment: dict)`:
        *   Processes a "style" segment, which contains `sub_segments`.
        *   Iterates through `sub_segments` and calls `generate_gcode_segment` for each.
        *   Currently, it's a basic implementation; a more advanced version could modify sub-segments based on the `style_type`.
    *   `generate_gcode_repeat(segment: dict)`:
        *   Handles "repeat" segments. It takes a `count` and a `segment` to be repeated.
        *   It can also take `transform` parameters that are applied to each repetition.
        *   It uses `apply_transformation` for each instance, potentially with a `base_offset` to allow for cumulative transformations (e.g., stacking or arraying).
    *   `generate_gcode_structure(segment: dict)`:
        *   Generates G-code for predefined "structure" types like "lattice" or "honeycomb".
        *   It calls functions like `generate_gcode_lattice` or `generate_gcode_honeycomb` (imported from `modules.ai_pathing`). These are currently placeholders but would contain complex generation logic.
    *   `generate_gcode_from_json(json_input: Union[str, Dict])`:
        *   The main entry point for converting a full JSON description into G-code.
        *   Parses the JSON using `parse_json_input` (from `core.utils`).
        *   Initializes G-code with standard setup commands (G21, G90).
        *   Iterates through each segment defined in the JSON's "path.segments".
        *   **Crucially, it manages `current_position`**: Before generating G-code for segments like "arc" or "line" (if an explicit "start" is given), it checks if the `current_position` matches the segment's intended start. If not, it inserts a `G0` (rapid move) command to position the tool head correctly. This ensures continuity and correct relative calculations for commands like arcs (I, J parameters).
        *   Calls `generate_gcode_segment` for each segment.
        *   Updates `current_position` based on the last command of the generated segment's G-code.
        *   Applies global `modifiers` and `constraints` (defined in the JSON's "path") to the entire generated G-code list using functions from `modules.ai_pathing`.
        *   Filters redundant moves using `filter_redundant_moves` (from `core.utils`).
        *   Appends an end-of-program command (M2).
*   **Role in Overall System**:
    This is the heart of the G-code generation. It takes the abstract path description and translates it into concrete, executable G-code, handling various complexities like segment types, transformations, and ensuring path continuity.

## 3. `c:\Users\gilbe\Desktop\TotalControl\totalcontrol\core\segment_primitives.py`

*   **Purpose**:
    This module is dedicated to generating G-code for basic, primitive geometric path segments. It keeps the main `gcode_generator.py` cleaner by offloading the detailed G-code string formatting for these common shapes.
*   **Key Functionalities/How it Works**:
    *   `generate_gcode_line(segment: dict)`: Creates a `G1` command for a straight line movement to the specified `end` point.
    *   `generate_gcode_arc(segment: dict)`: Generates a `G2` (clockwise) or `G3` (counter-clockwise) arc command. It calculates the arc's end point based on `center`, `radius`, and `end_angle`. It also calculates the `I` and `J` parameters (offsets from the arc's start point to its center) based on the `start_angle`.
    *   `generate_gcode_bezier(segment: dict)`: Approximates a Bézier curve (quadratic or cubic based on the number of `control_points`) by generating a series of short `G1` line segments. The `num_points` parameter controls the resolution of this approximation.
    *   `generate_gcode_spiral(segment: dict)`: Generates a spiral path as a series of `G1` line segments. It calculates points along a spiral defined by `center`, `inner_radius`, `outer_radius`, `turns`, and `pitch`.
    *   All functions use constants like `DEFAULT_FEEDRATE` and `DEFAULT_EXTRUSION_RATE` from `core.constants`.
*   **Role in Overall System**:
    Provides the building blocks for more complex paths. `gcode_generator.py` calls these functions when it encounters segments of types "line", "arc", "bezier", or "spiral".

## 4. `c:\Users\gilbe\Desktop\TotalControl\totalcontrol\core\transform.py`

*   **Purpose**:
    This module is responsible for applying geometric transformations (scaling, rotation, translation/offset) to a list of G-code commands.
*   **Key Functionalities/How it Works**:
    *   `apply_transformation(gcode_commands: List[str], transform_params: dict, iteration: int, total_iterations: int, base_offset: List[float])`:
        *   Takes a list of G-code command strings and transformation parameters.
        *   Iterates through each command:
            *   Non-G0/G1/G2/G3 commands are passed through unchanged.
            *   For G0/G1/G2/G3 commands, it parses out existing X, Y, Z, I, J, K coordinates.
            *   **Base Offset**: Applies an initial `base_offset` (useful for `repeat` operations where each repetition is shifted).
            *   **Scaling**: If `scale` parameters are provided, it scales the X, Y, Z coordinates (and I, J, K vectors for arcs) around the origin.
            *   **Rotation**: If `rotate` parameters (axis and angle) are provided, it rotates the X, Y, Z coordinates (and I, J, K vectors for arcs) around the specified axis.
            *   **Offset**: If `offset` parameters are provided, it translates the X, Y, Z coordinates.
            *   Reconstructs the G-code command string with the transformed coordinates, formatted to three decimal places.
        *   The `iteration` and `total_iterations` parameters are available for more dynamic transformations, though not heavily used in the current implementation of this function itself (they are more for the calling context like `generate_gcode_repeat`).
*   **Role in Overall System**:
    Provides a crucial capability to manipulate generated G-code paths. It's used by `gcode_generator.py` to apply transformations defined either directly on a segment or within a "repeat" segment definition.

## 5. `c:\Users\gilbe\Desktop\TotalControl\totalcontrol\core\utils.py`

*   **Purpose**:
    This module contains general utility functions that are used across different parts of the G-code generation and processing system.
*   **Key Functionalities/How it Works**:
    *   `parse_json_input(json_input: Union[str, Dict])`:
        *   A robust function to parse JSON input. It accepts either a JSON-formatted string or an already parsed Python dictionary.
        *   Returns a Python dictionary. Includes error handling for invalid JSON strings.
    *   `_parse_gcode_params_for_filter(line: str)`:
        *   A helper function (internal use suggested by the underscore) that parses a single G-code line and extracts its parameters (X, Y, Z, F, E, etc.) into a dictionary.
    *   `filter_redundant_moves(gcode_commands: List[str], tolerance: float)`:
        *   Optimizes the G-code by removing redundant `G0` or `G1` commands.
        *   It tracks the `current_pos` (X, Y, Z).
        *   If a `G0`/`G1` command doesn't change the XYZ position (within a `tolerance`) and doesn't set other critical parameters like Feedrate (F) or Extrusion (E), it's removed.
        *   It correctly updates `current_pos` for various commands (G0, G1, G2, G3, G28, G92) to maintain an accurate state.
*   **Role in Overall System**:
    Provides essential helper functions. `parse_json_input` is used by `gcode_generator.py` to process the initial input. `filter_redundant_moves` is used by `gcode_generator.py` as a final G-code cleanup step.

## 6. `c:\Users\gilbe\Desktop\TotalControl\totalcontrol\core\constants.py`

*   **Purpose**:
    Defines default constant values that are used throughout the G-code generation and processing pipeline. This centralizes configuration and makes it easier to adjust default behaviors.
*   **Key Functionalities/How it Works**:
    *   It simply declares variables with default values:
        *   `DEFAULT_FEEDRATE`: Default movement speed.
        *   `DEFAULT_EXTRUSION_RATE`: Default amount of material to extrude per millimeter of movement.
        *   `DEFAULT_RESOLUTION`: Default number of points used to approximate curves (like Béziers or spirals).
        *   `DEFAULT_SMOOTHING_LEVEL`: Default level for smoothing operations (used by `ai_pathing.py`).
*   **Role in Overall System**:
    Provides consistent default parameters to various modules (`gcode_generator.py`, `segment_primitives.py`, `ai_pathing.py`), reducing hardcoding and improving configurability.

## 7. `c:\Users\gilbe\Desktop\TotalControl\totalcontrol\core\ai_optimizer.py`

*   **Purpose**:
    This module is intended to house AI-driven G-code optimization logic. Currently, it provides a basic placeholder for optimization.
*   **Key Functionalities/How it Works**:
    *   `parse_gcode_line(line: str)`: Parses a G-code line into a command and its parameters (similar to `_parse_gcode_params_for_filter` in `utils.py` but with a slightly different output structure).
    *   `reconstruct_gcode_line(cmd_dict: Dict[str, float])`: Rebuilds a G-code string from a parsed command dictionary.
    *   `optimize_gcode(gcode_commands: List[str], material_properties: dict, printer_capabilities: dict)`:
        *   The main optimization function.
        *   Currently, it performs a very simple optimization: if a line is a `G1` move, it increases the feedrate by 20%, capped by `printer_capabilities.get("max_feedrate")`.
        *   The `material_properties` and full `printer_capabilities` are passed in but largely unused by the current basic logic. A true AI optimizer would leverage these extensively.
*   **Role in Overall System**:
    Intended to be the module where intelligent G-code enhancements happen, considering material science and printer dynamics. `main.py` calls this function to demonstrate the optimization step in the pipeline.

## 8. `c:\Users\gilbe\Desktop\TotalControl\totalcontrol\core\input_handler.py`

*   **Purpose**:
    This module appears to be designed for handling specific, direct input descriptors (like Bézier control points or Voronoi points) and converting them into a list of G-code commands. It seems to offer a more direct, programmatic way to generate G-code for certain shapes compared to the JSON-driven approach of `gcode_generator.py`.
*   **Key Functionalities/How it Works**:
    *   `generate_bezier_gcode(control_points: List[tuple])`: Takes a list of (X,Y,Z) control point tuples and generates `G1` commands. The comment notes this is a simplified representation (connecting control points directly rather than interpolating the curve).
    *   `generate_voronoi_gcode(points: List[tuple])`: Similar to Bézier, takes a list of (X,Y,Z) points and generates `G1` commands to connect them.
    *   `generate_gcode_from_input(descriptor: Dict[str, Any])`: Acts as a dispatcher. It takes a dictionary `descriptor` with a "type" key (e.g., "bezier", "voronoi") and calls the appropriate generation function.
    *   Includes type and value checking for inputs.
*   **Role in Overall System**:
    This module provides an alternative or supplementary way to generate G-code for specific geometric patterns directly from Python data structures. It's not directly integrated into the main JSON processing pipeline shown in `main.py` and `gcode_generator.py` but could be used independently or integrated as another "segment type" if desired. The Bézier generation here is simpler than the one in `segment_primitives.py`.

## 9. `c:\Users\gilbe\Desktop\TotalControl\totalcontrol\modules\ai_pathing.py`

*   **Purpose**:
    This module is intended to house more advanced, potentially AI-driven, path generation and modification algorithms. This includes generating complex structures and applying sophisticated modifiers or constraints to G-code.
*   **Key Functionalities/How it Works (Inferred from usage)**:
    *   `generate_gcode_lattice(base_segment: dict, density: float)`: Placeholder for generating lattice structures.
    *   `generate_gcode_honeycomb(base_segment: dict, density: float)`: Placeholder for generating honeycomb structures.
    *   `apply_modifier(gcode, modifier, segment)`: Applies a named modifier (e.g., "offset", "smooth") to a list of G-code commands. The actual implementation for offset and smoothing involves geometric calculations on the path points.
    *   `apply_constraint(gcode_commands, constraint, segment)`: Applies constraints like ensuring connectivity between segments or maintaining tangency.
*   **Role in Overall System**:
    This module extends the capabilities of the core G-code generation by providing specialized pathing strategies and post-processing operations. Functions from this module are called by `gcode_generator.py` for "structure" type segments and for applying global modifiers/constraints.

## 10. `c:\Users\gilbe\Desktop\TotalControl\totalcontrol\test_gcode_generation.py`

*   **Purpose**:
    This module contains unit tests for the G-code generation functionalities, specifically focusing on `core.gcode_generator.generate_gcode_segment` and `core.transform.apply_transformation` (though `apply_transformation` is tested implicitly via segments with a "transform" key).
*   **Key Functionalities/How it Works**:
    *   It uses the `unittest` framework.
    *   `TestGCodeGeneration` class contains various test methods:
        *   `test_line_generation`, `test_arc_generation`, `test_bezier_generation`, `test_spiral_generation`: Test the G-code output for basic primitive segment types. They define a segment dictionary and compare the output of `generate_gcode_segment` with an `expected_gcode` list.
        *   `test_style_generation`, `test_repeat_generation`, `test_structure_generation`: Test the composite segment types.
        *   `test_transform_translation`, `test_transform_scaling`, `test_transform_rotation`: Test the application of transformations to a line segment. The rotation test uses `assertTrue` for floating-point comparisons due to potential minor precision differences.
        *   Error handling tests: `test_empty_segment_definition` and `test_unsupported_segment_type` check that appropriate `ValueError` exceptions are raised.
        *   Edge case tests: `test_edge_case_large_path`, `test_edge_case_small_path`, `test_edge_case_with_negative_coordinates`, `test_edge_case_zero_length_path` test behavior with various coordinate inputs.
*   **Role in Overall System**:
    Ensures the reliability and correctness of the core G-code generation logic. These tests help catch regressions and verify that individual components produce the expected output for given inputs.