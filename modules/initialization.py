# modules/initialization.py
import os
import sys
import logging # For type hinting, actual logger instance is passed

def initialize_environment(project_root: str,
                           json_example_data: dict,
                           material_props_data: dict,
                           printer_caps_data: dict,
                           logger_instance: logging.Logger):
    """
    Sets up the environment for G-code generation:
    - Defines and creates output directories.
    - Defines paths for input and output files.
    - Validates essential input data and configurations.
    - Exits on critical validation errors.

    Args:
        project_root (str): The root directory of the project.
        json_example_data (dict): Example JSON input for validation.
        material_props_data (dict): Material properties for validation.
        printer_caps_data (dict): Printer capabilities for validation.
        logger_instance (logging.Logger): Logger instance for logging messages.

    Returns:
        dict: A dictionary containing essential paths:
              'default_printer_profile_path', 'output_gcode_path_raw',
              'output_gcode_path_optimized', 'output_gcode_path_safe'.
    """
    # Define and create the G-code output directory
    gcode_output_dir_name = "gcode_outputs"
    gcode_output_dir_path = os.path.join(project_root, gcode_output_dir_name)
    try:
        os.makedirs(gcode_output_dir_path, exist_ok=True)
        logger_instance.info(f"Ensured G-code output directory exists at: {gcode_output_dir_path}")
    except OSError as ose:
        logger_instance.error(f"Error creating G-code output directory '{gcode_output_dir_path}': {ose}", exc_info=True)
        print(f"\nError creating G-code output directory: {ose}")
        sys.exit(1)

    # Define paths
    default_printer_profile_path = os.path.join(project_root, "printer_profiles", "generic_fdm.json")
    output_gcode_path_raw = os.path.join(gcode_output_dir_path, "output_raw.gcode")
    output_gcode_path_optimized = os.path.join(gcode_output_dir_path, "output_optimized.gcode")
    output_gcode_path_safe = os.path.join(gcode_output_dir_path, "output_safe.gcode")

    # --- Validations ---
    try:
        if not json_example_data or not isinstance(json_example_data, dict):
            raise ValueError("Invalid JSON example provided.")
        logger_instance.info("JSON example is valid.")
    except ValueError as ve:
        logger_instance.error(f"Invalid JSON example: {ve}", exc_info=True)
        print(f"\nInvalid JSON example: {ve}")
        sys.exit(1)

    try:
        if not material_props_data or not isinstance(material_props_data, dict):
            raise ValueError("Invalid material properties provided.")
        logger_instance.info("Material properties are valid.")
    except ValueError as ve:
        logger_instance.error(f"Invalid material properties: {ve}", exc_info=True)
        print(f"\nInvalid material properties: {ve}")
        sys.exit(1)

    try:
        if not printer_caps_data or not isinstance(printer_caps_data, dict):
            raise ValueError("Invalid printer capabilities provided.")
        logger_instance.info("Printer capabilities are valid.")
    except ValueError as ve:
        logger_instance.error(f"Invalid printer capabilities: {ve}", exc_info=True)
        print(f"\nInvalid printer capabilities: {ve}")
        sys.exit(1)

    paths = {
        "default_printer_profile_path": default_printer_profile_path,
        "output_gcode_path_raw": output_gcode_path_raw,
        "output_gcode_path_optimized": output_gcode_path_optimized,
        "output_gcode_path_safe": output_gcode_path_safe,
    }
    logger_instance.info("Environment initialization and validation complete.")
    return paths