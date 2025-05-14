# core/ai_optimizer.py
# This module focuses on optimizing G-code commands. It includes functions
# for parsing G-code and applying AI-driven optimizations based on material
# and printer properties.

#Imports
from typing import List, Dict
import logging # Added for logging
from core.constants import DEFAULT_FEEDRATE

# Setup a logger for this module
logger = logging.getLogger(__name__)

# 1. Function to parse a GCode line into a dictionary of command and parameters.
def parse_gcode_line(line: str) -> Dict:
    """Parses a GCode line into a dictionary of command and parameters."""
    line = line.strip()
    if not line or line.startswith(';'): # Ignore empty lines or comments
        return {}

    # Remove leading/trailing whitespace and split the line into parts
    parts = line.split()
    if not parts:
        logger.warning(f"Received empty or invalid G-code line for parsing: '{line}'")
        return {}

    # The first part is the G-code command (e.g., G1, M2)
    cmd = parts[0].upper()
    params = {}

    # Process the remaining parts as parameters (e.g., X10.0, F1500)
    # Each parameter is a key-value pair (e.g., 'X': 10.0)
    for part in parts[1:]:
        if not part:
            continue
        try:
            key = part[0].upper()
            if not key.isalpha():
                logger.warning(f"Invalid parameter key in '{part}' from line '{line}'. Skipping.")
                continue
            value_str = part[1:]
            if not value_str: # Handle cases like "G1 X"
                logger.warning(f"Missing value for parameter '{key}' in line '{line}'. Skipping.")
                continue
            params[key] = float(value_str)
        except (ValueError, IndexError) as e:
            logger.warning(f"Could not parse parameter '{part}' in line '{line}': {e}. Skipping.")
    return {"cmd": cmd, "params": params}

# 2. Function to reconstruct a GCode line from a command dictionary.
def reconstruct_gcode_line(parsed_line: Dict) -> str:
    """Reconstructs a GCode line from a command dictionary."""
    cmd = parsed_line.get("cmd")
    if not cmd:
        logger.error("Cannot reconstruct G-code line: 'cmd' is missing from parsed data.")
        return "" # Or raise an error

    params = parsed_line.get("params", {})
    # Format each parameter back into a string (e.g., X10.0000)
    # Feedrate (F) is typically an integer, so it's formatted differently.
    parts = [f"{key}{value:.4f}" if key != "F" else f"{key}{int(value)}" for key, value in params.items()]
    # Join the command and its parameters with spaces
    return f"{cmd} {' '.join(parts)}"

# 3. Function to optimize GCode commands based on printer and material properties.
def optimize_gcode(gcode_commands: List[str],
                   material_properties: dict,
                   printer_capabilities: dict) -> List[str]:
    """
    Optimizes GCode commands based on printer and material properties.

    Args:
        gcode_commands: List of raw GCode strings.
        material_properties: Dict of material properties.
        printer_capabilities: Dict of printer capabilities.

    Returns:
        List of optimized GCode strings.
    """
    # Initialize an empty list to store the optimized G-code commands
    optimized_gcode = []

    for line in gcode_commands:
        original_line = line # Keep a copy for fallback
        try:
            parsed_line = parse_gcode_line(line)
            if not parsed_line or "cmd" not in parsed_line:
                # If parsing results in an empty dict (e.g. comment, empty line) or no command
                optimized_gcode.append(original_line)
                continue

            cmd_val = parsed_line["cmd"]
            params_val = parsed_line.get("params", {})

            # Only attempt to optimize G1 commands for now
            if cmd_val != "G1":
                optimized_gcode.append(original_line)
                continue

            # AI Placeholder: adjust parameters based on analysis
            # Get the original feedrate or use the default if not specified
            original_feedrate = params_val.get("F", DEFAULT_FEEDRATE)
            # Example optimization: Increase feedrate by 20%, but cap it at the printer's max feedrate
            # Ensure printer_capabilities has 'max_feedrate' or provide a sensible default
            max_feed = printer_capabilities.get("max_feedrate", original_feedrate * 1.5) # Default to 1.5x if not specified
            optimized_feedrate = min(original_feedrate * 1.2, max_feed)
            # Update the feedrate in the command dictionary
            params_val["F"] = optimized_feedrate

            # Future Placeholder: Use material_properties to adjust extrusion, cooling, etc.

            # Reconstruct the G-code line with the optimized parameters
            optimized_line = reconstruct_gcode_line({"cmd": cmd_val, "params": params_val})
            optimized_gcode.append(optimized_line)
        except Exception as e:
            logger.error(f"Error optimizing G-code line '{original_line}': {e}. Appending original line.")
            optimized_gcode.append(line)

    return optimized_gcode
