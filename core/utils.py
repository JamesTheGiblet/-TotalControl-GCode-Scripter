# core/utils.py
# This module provides utility functions, such as parsing JSON input,
# that are used across different parts of the G-code generation system.

#Imports
import json
import math # Added for _filter_redundant_moves
from typing import Union, Dict, List # Added List for _filter_redundant_moves

# 1. Function to parse JSON input, handling both string and dictionary types.
def parse_json_input(json_input: Union[str, Dict]) -> Dict:
    # Ensures JSON input (string or dict) is returned as a dictionary.
    """
    Parses the JSON input, whether it's a JSON-formatted string or a dictionary.

    Args:
        json_input (str | dict): The JSON input.

    Raises:
        ValueError: If the input is a string and contains invalid JSON.
        TypeError: If the input is neither a string nor a dictionary.

    Returns:
        dict: A dictionary representing the parsed JSON data.
    """
    # Check if the input is a string
    if isinstance(json_input, str):
        try:
            # Attempt to parse the JSON string, stripping any leading/trailing whitespace
            return json.loads(json_input.strip())
        except json.JSONDecodeError as e:
            # Raise a ValueError if the string is not valid JSON
            raise ValueError(f"Invalid JSON string provided: {e}")
    # Check if the input is already a dictionary
    elif isinstance(json_input, dict):
        # If it's a dictionary, return it directly
        return json_input
    # If the input is neither a string nor a dictionary, raise a TypeError
    else:
        raise TypeError(
            f"Input must be a JSON string or a dictionary, but got {type(json_input).__name__}."
        )

# 2. Helper function to parse G-code parameters for filtering
def _parse_gcode_params_for_filter(line: str) -> Dict[str, float]:
    """
    Parses a GCode line's parameters (like X, Y, Z, F, E) into a dictionary.
    Helper for _filter_redundant_moves.
    """
    parts = line.strip().split()
    params = {}
    if not parts:
        return params
    for p_str in parts[1:]: # Skip command word (e.g., G1)
        if not p_str or len(p_str) < 2: # Parameter must have a letter and a value
            continue
        key = p_str[0].upper()
        try:
            value = float(p_str[1:])
            params[key] = value
        except ValueError:
            # Ignore if parameter value is not a valid float
            pass
    return params

# 3. Function to filter redundant G-code moves
def filter_redundant_moves(gcode_commands: List[str], tolerance: float = 0.001) -> List[str]:
    """
    Filters out redundant G0/G1 commands that don't change the XYZ position
    and don't set other parameters like F or E.
    """
    if not gcode_commands:
        return []

    filtered_commands = []
    current_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0} 
    initial_pos_is_known = False 

    for command_str in gcode_commands:
        command_str_upper = command_str.strip().upper()
        params = _parse_gcode_params_for_filter(command_str)

        if command_str_upper.startswith(("G0", "G1")):
            target_x = params.get('X', current_pos['X'])
            target_y = params.get('Y', current_pos['Y'])
            target_z = params.get('Z', current_pos['Z'])
            is_xyz_redundant = initial_pos_is_known and (math.isclose(target_x, current_pos['X'], abs_tol=tolerance) and math.isclose(target_y, current_pos['Y'], abs_tol=tolerance) and math.isclose(target_z, current_pos['Z'], abs_tol=tolerance))
            has_feed_or_extrusion_params = 'F' in params or 'E' in params
            if is_xyz_redundant and not has_feed_or_extrusion_params: continue
            filtered_commands.append(command_str)
            current_pos.update({'X': target_x, 'Y': target_y, 'Z': target_z}); initial_pos_is_known = True
        elif command_str_upper.startswith(("G2", "G3", "G28", "G92")):
            filtered_commands.append(command_str)
            if 'X' in params: current_pos['X'] = params.get('X', current_pos['X'])
            if 'Y' in params: current_pos['Y'] = params.get('Y', current_pos['Y'])
            if 'Z' in params: current_pos['Z'] = params.get('Z', current_pos['Z'])
            if command_str_upper.startswith("G28"): current_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
            initial_pos_is_known = True
        else:
            filtered_commands.append(command_str)
    return filtered_commands
