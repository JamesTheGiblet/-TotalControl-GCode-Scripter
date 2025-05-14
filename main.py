# main.py
# This script serves as the main entry point and demonstrator for the TotalControl
# G-code generation and optimization pipeline. It showcases how to use various
# modules to convert a JSON path description into optimized G-code.

#Imports
import json
import logging # Added for logging
from core.gcode_generator import generate_gcode_from_json
from core.ai_optimizer import optimize_gcode
from core.utils import parse_json_input

# Import the modules
from modules.ai_pathing import generate_gcode_lattice, generate_gcode_honeycomb, apply_modifier, apply_constraint

# Setup a logger for this module
logger = logging.getLogger(__name__)

# Basic logging configuration for standalone execution
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

# Example JSON input (same as before for demonstration)
json_example = {
    "path": {
        "segments": [
            {"type": "line", "start": [0, 0, 0], "end": [100, 0, 0]},
            {"type": "arc", "center": [100, 50, 0], "radius": 50, "start_angle": 0, "end_angle": 90, "clockwise": True},
            {"type": "bezier", "control_points": [[150, 50, 0], [200, 100, 50], [250, 50, 0]], "num_points": 20},
            {"type": "spiral", "center": [0, 0, 0], "inner_radius": 10, "outer_radius": 50, "turns": 5, "pitch": 2},
            {"type": "style", "style_type": "organic", "sub_segments": [{"type": "spiral", "center": [0, 0, 0], "inner_radius": 10, "outer_radius": 50, "turns": 5, "pitch": 2}]},
            {"type": "repeat", "count": 3, "transform": {"rotate": ["z", 120]}, "segment": {"type": "line", "start": [0, 0, 0], "end": [50, 0, 0]}},
            {"type": "structure", "structure_type": "lattice", "density": 0.6, "base_segment": {"type": "line", "start": [0, 0, 0], "end": [10, 10, 10]}}
        ],
        "modifiers": [
            {"type": "offset", "distance": 5},
            {"type": "smooth", "level": 2}
        ],
        "constraints": [
            {"type": "connect", "previous_segment": True},
            {"type": "tangent", "direction": [1, 0, 0]}
        ]
    }
}

# Example material properties
material_properties = {
    "name": "PLA",
    "density": 1.24,
    "viscosity": 100,
    "thermal_conductivity": 0.13,
    "glass_transition_temp": 60,
    "max_flow_rate": 10,
}

# Example printer capabilities
printer_capabilities = {
    "max_acceleration": 500,
    "max_jerk": 10,
    "max_speed_x": 200,
    "max_speed_y": 200,
    "max_speed_z": 50,
    "max_ext_speed": 50,
    "nozzle_diameter": 0.4,
}

if __name__ == "__main__":
    logger.info("Starting G-code generation and optimization pipeline...")

    gcode_commands = []
    optimized_gcode = []

    try:
        # 1. Generate G-code from JSON input
        logger.info("Step 1: Generating G-code from JSON input...")
        gcode_commands = generate_gcode_from_json(json_example)
        logger.info(f"Successfully generated {len(gcode_commands)} raw G-code commands.")
        print("Raw G-code:\n", "\n".join(gcode_commands))

        # 2. Optimize G-code using the AI optimizer
        logger.info("Step 2: Optimizing G-code...")
        optimized_gcode = optimize_gcode(gcode_commands, material_properties, printer_capabilities)
        logger.info(f"Successfully generated {len(optimized_gcode)} optimized G-code commands.")
        print("\nOptimized G-code:\n", "\n".join(optimized_gcode))

    except Exception as e:
        logger.error(f"An error occurred during the main G-code generation/optimization pipeline: {e}", exc_info=True)
        print(f"\nAn error occurred: {e}")

    try:
        # 3. Example of generating a lattice structure G-code using AI pathing
        logger.info("Step 3: Demonstrating lattice structure G-code generation...")
        lattice_base_segment_data = json_example["path"]["segments"][-1].get("base_segment", {})
        lattice_density = json_example["path"]["segments"][-1].get("density", 0.5)
        lattice_gcode = generate_gcode_lattice(lattice_base_segment_data, lattice_density)
        logger.info(f"Generated {len(lattice_gcode)} G-code commands for lattice structure example.")
        print("\nLattice G-code (Example):\n", "\n".join(lattice_gcode))
    except Exception as e:
        logger.error(f"Error during lattice generation example: {e}", exc_info=True)
        print(f"\nError in lattice example: {e}")

    # Demonstrative steps for applying modifiers and constraints iteratively
    # Note: These are typically handled within generate_gcode_from_json
    if gcode_commands: # Proceed only if initial G-code generation was successful
        try:
            logger.info("Step 4: Demonstrating iterative application of modifiers...")
            segment_for_example = json_example["path"]["segments"][0]
            gcode_after_step4_modifiers = list(gcode_commands)
            for modifier_item in json_example["path"]["modifiers"]:
                gcode_after_step4_modifiers = apply_modifier(gcode_after_step4_modifiers, modifier_item, segment_for_example)
            logger.info("Iterative modifiers applied for demonstration.")
            print("\nG-code after modifiers (applied in main.py step 4 demo):\n", "\n".join(gcode_after_step4_modifiers))

            logger.info("Step 5: Demonstrating iterative application of constraints...")
            gcode_after_step5_constraints = list(gcode_after_step4_modifiers)
            for constraint_item in json_example["path"]["constraints"]:
                gcode_after_step5_constraints = apply_constraint(gcode_after_step5_constraints, constraint_item, segment_for_example)
            logger.info("Iterative constraints applied for demonstration.")
            print("\nG-code with constraints applied (in main.py step 5 demo):\n", "\n".join(gcode_after_step5_constraints))
        except KeyError as ke:
            logger.error(f"KeyError during demonstrative modifier/constraint application: {ke}. Check example JSON structure.", exc_info=True)
            print(f"\nError in demonstrative steps (check JSON structure): {ke}")
        except Exception as e:
            logger.error(f"Error during demonstrative modifier/constraint application: {e}", exc_info=True)
            print(f"\nError in demonstrative steps: {e}")
    else:
        logger.warning("Skipping demonstrative steps 4 & 5 as initial G-code generation failed or produced no commands.")

    logger.info("G-code generation and optimization pipeline finished.")
