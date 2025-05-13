# core/ai_optimizer.py
# This module focuses on optimizing G-code commands. It includes functions
# for parsing G-code and applying AI-driven optimizations based on material
# and printer properties.

#Imports
from typing import List, Dict
from core.constants import DEFAULT_FEEDRATE

# 1. Function to parse a GCode line into a dictionary of command and parameters.
def parse_gcode_line(line: str) -> Dict[str, float]:
    """Parses a GCode line into a dictionary of command and parameters."""
    # Remove leading/trailing whitespace and split the line into parts
    parts = line.strip().split()
    # The first part is the G-code command (e.g., G1, M2)
    cmd = parts[0]
    # Process the remaining parts as parameters (e.g., X10.0, F1500)
    # Each parameter is a key-value pair (e.g., 'X': 10.0)
    # Filter out parts that are not valid parameters (must have a letter and a parsable number)
    params = {p[0]: float(p[1:]) for p in parts[1:] if len(p) > 1 and p[1:].replace('.', '', 1).isdigit()}
    return {"cmd": cmd, **params}

# 2. Function to reconstruct a GCode line from a command dictionary.
def reconstruct_gcode_line(cmd_dict: Dict[str, float]) -> str:
    """Reconstructs a GCode line from a command dictionary."""
    cmd = cmd_dict.pop("cmd")
    # Format each parameter back into a string (e.g., X10.0000)
    # Feedrate (F) is typically an integer, so it's formatted differently.
    parts = [f"{key}{value:.4f}" if key != "F" else f"{key}{int(value)}" for key, value in cmd_dict.items()]
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
        # If the line doesn't start with "G1" (linear move), append it as is (for now)
        # More sophisticated optimization might handle other commands like G0, G2, G3, M-codes etc.
        if not line.strip().startswith("G1"):
            optimized_gcode.append(line)
            continue

        # Parse the G1 line into a command dictionary
        cmd_dict = parse_gcode_line(line)

        # AI Placeholder: adjust parameters based on analysis
        # Get the original feedrate or use the default if not specified
        original_feedrate = cmd_dict.get("F", DEFAULT_FEEDRATE)
        # Example optimization: Increase feedrate by 20%, but cap it at the printer's max feedrate
        optimized_feedrate = min(original_feedrate * 1.2, printer_capabilities.get("max_feedrate", 3000))
        # Update the feedrate in the command dictionary
        cmd_dict["F"] = optimized_feedrate

        # Future Placeholder: Use material_properties to adjust extrusion, cooling, etc.
        # For example, extrusion rate (E) could be adjusted based on material flow characteristics.

        # Reconstruct the G-code line with the optimized parameters
        optimized_line = reconstruct_gcode_line(cmd_dict)
        optimized_gcode.append(optimized_line)

    return optimized_gcode
