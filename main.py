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
import os
from modules.safety_limits import PrinterProfile, SafetyLimiter
from strategies import apply_deposition_sequence_optimization # Import from the new module

# Import the modules
from modules.ai_pathing import generate_gcode_lattice, generate_gcode_honeycomb, apply_modifier, apply_constraint
from modules.initialization import initialize_environment # Import the new initialization function

from modules.example_data import json_example, material_properties, printer_capabilities # Import example data
# Setup a logger for this module
logger = logging.getLogger(__name__)

# Basic logging configuration for standalone execution
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

# Example JSON input (same as before for demonstration)

if __name__ == "__main__":
    logger.info("Starting G-code generation and optimization pipeline...")

    project_root = os.path.dirname(os.path.abspath(__file__))

    # Initialize environment: setup paths, validate inputs, create output directory
    env_paths = initialize_environment(
        project_root,
        json_example,
        material_properties,
        printer_capabilities,
        logger
    )

    default_printer_profile_path = env_paths["default_printer_profile_path"]
    output_gcode_path_raw = env_paths["output_gcode_path_raw"]
    output_gcode_path_optimized = env_paths["output_gcode_path_optimized"]
    output_gcode_path_safe = env_paths["output_gcode_path_safe"]

    gcode_commands = []
    optimized_gcode = []
    # safe_gcode = [] # This variable is initialized but not used later. Consider removing if not needed.

    try:
        # 1. Generate raw G-code
        logger.info("Step 1: Generating G-code from JSON input...")
        gcode_commands = generate_gcode_from_json(json_example)
        logger.info(f"Successfully generated {len(gcode_commands)} raw G-code commands.")
        print("Raw G-code:\n", "\n".join(gcode_commands))

        # Save raw G-code
        with open(output_gcode_path_raw, 'w') as f:
            for line in gcode_commands:
                f.write(line + "\n")
        logger.info(f"Raw G-code saved to {output_gcode_path_raw}")

        # 1.5 Apply deposition sequence optimization
        logger.info("Step 1.5: Applying deposition sequence optimization...")
        gcode_commands = apply_deposition_sequence_optimization(gcode_commands)
        logger.info("Deposition sequence optimization applied.")

        # 2. Optimize G-code using the AI optimizer
        logger.info("Step 2: Optimizing G-code...")
        optimized_gcode = optimize_gcode(gcode_commands, material_properties, printer_capabilities)
        logger.info(f"Successfully generated {len(optimized_gcode)} optimized G-code commands.")
        print("\nOptimized G-code:\n", "\n".join(optimized_gcode))
        # Save optimized G-code
        with open(output_gcode_path_optimized, "w") as f: # Corrected path for saving optimized G-code
            for line in optimized_gcode:
                f.write(line + "\n")
        logger.info(f"Optimized G-code saved to {output_gcode_path_optimized}")

        # 2.5 Apply Safety Limits
        logger.info(f"Step 2.5: Applying safety limits using profile: {default_printer_profile_path}...")
        if not os.path.exists(default_printer_profile_path):
            logger.error("Printer profile not found at %s. Skipping safety limits for optimized G-code.", default_printer_profile_path)
            # If profile not found, just copy optimized to safe output
            try:
                with open(output_gcode_path_safe, 'w') as f_out:
                    for line in optimized_gcode:
                        f_out.write(line + "\n")
                logger.info("Skipped safety limits. Original optimized G-code saved to %s.", output_gcode_path_safe)
            except Exception as write_error:
                logger.error("Error writing optimized G-code to safe output file when profile is missing: %s", write_error, exc_info=True)
                print(f"\nError writing optimized G-code to safe output file when profile is missing: {write_error}")
        else:
            try:
                printer_profile = PrinterProfile(default_printer_profile_path)
                safety_limiter = SafetyLimiter(printer_profile)
                
                # Stream processing and writing
                with open(output_gcode_path_safe, 'w') as f_out:
                    for line in optimized_gcode:
                        safe_line = safety_limiter.apply_safety_limits(line) # Use the correct method name
                        f_out.write(safe_line + "\n")

                logger.info("Safety limits applied and saved to %s.", output_gcode_path_safe)
                print(f"\nSafety limits applied and saved to {output_gcode_path_safe}.")
            except FileNotFoundError as fnf_error:
                logger.error("File not found error during safety limit application: %s", fnf_error, exc_info=True)
                print(f"\nFile not found error during safety limit application: {fnf_error}")
            except Exception as e:
                logger.error(f"Error during safety limit application: {e}. Proceeding with original optimized G-code.", exc_info=True)
                # safe_gcode = list(optimized_gcode) # Fallback to original optimized G-code. 'safe_gcode' is not used.
                print(f"\nError in safety limit application: {e}")
                print(f"Proceeding with original optimized G-code.")
                # Fallback: Write the original optimized G-code to the safe file
                try:
                    with open(output_gcode_path_safe, 'w') as f_out:
                        for line in optimized_gcode:
                            f_out.write(line + "\n")
                    logger.info("Fallback: Original optimized G-code saved to %s.", output_gcode_path_safe)
                except Exception as fallback_write_error:
                    logger.error("Error during fallback writing of optimized G-code: %s", fallback_write_error, exc_info=True)
                    print(f"\nError during fallback writing of optimized G-code: {fallback_write_error}")
    except json.JSONDecodeError as json_error:
        logger.error("JSON decoding error during G-code generation: %s", json_error, exc_info=True)
        print(f"\nJSON decoding error during G-code generation: {json_error}")
    except FileNotFoundError as fnf_error:
        logger.error(f"File not found error: {fnf_error}", exc_info=True)
        print(f"\nFile not found: {fnf_error}")
    except json.JSONDecodeError as json_error:
        logger.error(f"JSON decoding error: {json_error}", exc_info=True)
        print(f"\nJSON decoding error: {json_error}")
    except KeyError as key_error:
        logger.error(f"KeyError: {key_error}", exc_info=True)
        print(f"\nKeyError: {key_error}")
    except TypeError as type_error:
        logger.error(f"TypeError: {type_error}", exc_info=True)
        print(f"\nTypeError: {type_error}")
    except ValueError as value_error:
        logger.error(f"ValueError: {value_error}", exc_info=True)
        print(f"\nValueError: {value_error}")
    except PermissionError as perm_error:
        logger.error(f"PermissionError: {perm_error}", exc_info=True)
        print(f"\nPermissionError: {perm_error}")
    except OSError as os_error:
        logger.error(f"OSError: {os_error}", exc_info=True)
        print(f"\nOSError: {os_error}")
    except ImportError as import_error:
        logger.error(f"ImportError: {import_error}", exc_info=True)
        print(f"\nImportError: {import_error}")
    except RuntimeError as runtime_error:
        logger.error(f"RuntimeError: {runtime_error}", exc_info=True)
        print(f"\nRuntimeError: {runtime_error}")
    except AttributeError as attr_error:
        logger.error(f"AttributeError: {attr_error}", exc_info=True)
        print(f"\nAttributeError: {attr_error}")
    except IndexError as index_error:
        logger.error(f"IndexError: {index_error}", exc_info=True)
        print(f"\nIndexError: {index_error}")
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
    if gcode_commands:  # Proceed only if initial G-code generation was successful
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
        except KeyError as key_error:
            logger.error(f"KeyError during modifier/constraint application: {key_error}", exc_info=True)
            print(f"\nKeyError during modifier/constraint application: {key_error}")
        except Exception as e:
            logger.error(f"Error during modifier/constraint demonstration: {e}", exc_info=True)
            print(f"\nError during modifier/constraint demonstration: {e}")
        except KeyError as key_error:
            logger.error(f"KeyError during modifier/constraint demonstration: {key_error}", exc_info=True)
            print(f"\nKeyError in modifier/constraint demonstration: {key_error}")
        except Exception as e:
            logger.error(f"Unexpected error during modifier/constraint demonstration: {e}", exc_info=True)
            print(f"\nUnexpected error in modifier/constraint demonstration: {e}")
    else:
        logger.warning("No G-code commands generated. Skipping modifier/constraint demonstration.")
        print("\nNo G-code commands generated. Skipping modifier/constraint demonstration.")
    logger.info("G-code generation and optimization pipeline completed.")
    print("\nG-code generation and optimization pipeline completed.")
    # End of the script