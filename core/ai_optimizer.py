# core/ai_optimizer.py
# This module focuses on optimizing G-code commands. It includes functions
# for parsing G-code and applying AI-driven optimizations based on material
# and printer properties.

#Imports
from typing import List, Dict, Tuple
import logging # Added for logging
import re # Added for parsing
import math # Added for distance calculation
from core.constants import DEFAULT_FEEDRATE
from materials.materials import get_material_properties # Import material database access

# Setup a logger for this module
logger = logging.getLogger(__name__)

# 1. Function to parse a GCode line into a dictionary of command and parameters.
def parse_gcode_line(line: str) -> Dict:
    """Parses a GCode line into a dictionary of command and parameters."""
    line = line.strip()
    if not line or line.startswith(';'): # Ignore empty lines or comments
        return {}

    # Remove comments from the line before splitting
    if ';' in line:
        line = line.split(';', 1)[0].strip()

    # Remove leading/trailing whitespace and split the line into parts
    parts = line.strip().split()
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

# --- Helper Functions for Path/Geometric Analysis (Potentially moved to a utils module later) ---

def parse_gcode(gcode_lines: List[str]) -> List[Dict]:
    """
    Parses G-code lines into a list of dictionaries, extracting command and parameters.
    This parser also tracks the current position (X, Y, Z, E) and handles G90/G91.
    This is more robust for geometric analysis than parse_gcode_line.

    Args:
        gcode_lines: List of G-code command strings.

    Returns:
        List of dictionaries, each representing a parsed command with position info.
        Example: [{'command': 'G1', 'X': 10.0, 'Y': 20.0, 'F': 1800, 'current_pos': {'X': 10.0, 'Y': 20.0, 'Z': 0.0, 'E': 0.0}}, ...]
    """
    parsed_commands = []
    # Regex to capture command (G/M code) and parameters (like X, Y, Z, E, F, S, P)
    # It handles both integer and float values and optional parameters.
    # It also ignores comments.
    gcode_pattern = re.compile(r'^([GM]\d+)\s*(.*)')
    param_pattern = re.compile(r'([XYZSEFPN])([-+]?\d*\.?\d+)')

    current_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'E': 0.0} # Track current position for relative moves (G91)
    is_relative = False # Track if in relative positioning mode (G91)

    for line_num, line in enumerate(gcode_lines):
        line = line.strip()
        if not line or line.startswith(';'):
            parsed_commands.append({'original': line, 'line_number': line_num + 1}) # Keep comments/empty lines
            continue

        command_match = gcode_pattern.match(line)
        if not command_match:
            # Handle lines that might not fit the G/M pattern but are valid (e.g., T0)
            # Or log a warning for unparseable lines
            logger.debug(f"Line {line_num+1}: Could not parse command part of line: {line}")
            parsed_commands.append({'original': line, 'line_number': line_num + 1})
            continue

        command = command_match.group(1)
        params_string = command_match.group(2)
        params: Dict[str, float] = {}

        for param_match in param_pattern.finditer(params_string):
            param_key = param_match.group(1)
            param_value = float(param_match.group(2))
            params[param_key] = param_value

        parsed_command = {'command': command, 'line_number': line_num + 1, **params}

        # Handle positioning modes
        if command == 'G90': # Absolute positioning
            is_relative = False
        elif command == 'G91': # Relative positioning
            is_relative = True

        # Update current position based on G0/G1 commands
        if command in ['G0', 'G1']:
            if is_relative:
                if 'X' in params: current_pos['X'] += params['X']
                if 'Y' in params: current_pos['Y'] += params['Y']
                if 'Z' in params: current_pos['Z'] += params['Z']
                if 'E' in params: current_pos['E'] += params['E']
            else: # Absolute
                if 'X' in params: current_pos['X'] = params['X']
                if 'Y' in params: current_pos['Y'] = params['Y']
                if 'Z' in params: current_pos['Z'] = params['Z']
                if 'E' in params: current_pos['E'] = params['E']

            # Add current position to the parsed command for easier access later
            parsed_command['current_pos'] = current_pos.copy()
        elif command == 'G28': # Homing resets position
             current_pos = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'E': 0.0}
             parsed_command['current_pos'] = current_pos.copy()
        elif command == 'G92': # Set Position
             if 'X' in params: current_pos['X'] = params['X']
             if 'Y' in params: current_pos['Y'] = params['Y']
             if 'Z' in params: current_pos['Z'] = params['Z']
             if 'E' in params: current_pos['E'] = params['E']
             parsed_command['current_pos'] = current_pos.copy()

        parsed_commands.append(parsed_command)

    return parsed_commands

def calculate_distance(p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> float:
    """Calculates the Euclidean distance between two 3D points."""
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2 + (p2[2] - p1[2])**2)

def calculate_angle_between_segments(p1_start: Tuple[float, float, float], p1_end: Tuple[float, float, float], p2_start: Tuple[float, float, float], p2_end: Tuple[float, float, float]) -> float:
    """
    Calculates the angle in degrees between two consecutive segments (p1_start->p1_end and p2_start->p2_end)
    in the XY plane. Assumes p1_end is the same as p2_start (connected segments).
    Returns the angle between the vectors (0 for U-turn, 180 for straight).
    """
    v1 = (p1_end[0] - p1_start[0], p1_end[1] - p1_start[1])
    v2 = (p2_end[0] - p2_start[0], p2_end[1] - p2_start[1])

    # Calculate dot product
    dot_product = v1[0] * v2[0] + v1[1] * v2[1]

    # Calculate magnitudes
    mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
    mag2 = math.sqrt(v2[0]**2 + v2[1]**2)

    # Avoid division by zero if a segment has zero length
    if mag1 == 0 or mag2 == 0:
        return 180.0 # Treat zero-length segments as straight continuation or non-contributing

    # Calculate cosine of the angle
    cosine_angle = dot_product / (mag1 * mag2)

    # Clamp cosine to [-1, 1] to avoid issues with floating point inaccuracies
    cosine_angle = max(-1.0, min(1.0, cosine_angle))

    return math.degrees(math.acos(cosine_angle))

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
                   material_name: str, # Changed from material_properties dict
                   printer_capabilities: dict) -> List[str]:
    """
    Applies AI-driven optimizations to GCode commands based on material
    and printer capabilities.

    Args:
        gcode_commands: List of raw GCode strings.
        material_name: Name of the material (e.g., "PLA").
        printer_capabilities: Dict of printer capabilities.

    Returns:
        List of optimized GCode strings.
    """
    # Initialize an empty list to store the optimized G-code commands
    optimized_gcode = []

    current_material_props = get_material_properties(material_name)
    if not current_material_props:
        logger.warning(f"Material '{material_name}' not found in database. Using default optimization behaviors.")
        # Fallback to default behavior if material properties are not found
        feedrate_increase_factor = 1.2 # Default factor
    else:
        logger.info(f"Optimizing for material: {current_material_props.get('name', material_name)}")
        viscosity_index = current_material_props.get("viscosity_index", 1.0)

        # Example of using a material property:
        # Adjust feedrate increase factor based on viscosity.
        # This is a very simple model: higher viscosity -> less aggressive speed increase.
        if viscosity_index > 1.1: # e.g., ABS in our example data
            feedrate_increase_factor = 1.1 # Be slightly more conservative
        elif viscosity_index < 0.9: # Hypothetical less viscous material
            feedrate_increase_factor = 1.3 # Be slightly more aggressive
        else: # e.g., PLA
            feedrate_increase_factor = 1.2

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
            # Example optimization: Increase feedrate by the calculated factor, but cap it at the printer's max feedrate
            # Ensure printer_capabilities has 'max_feedrate' or provide a sensible default
            max_feed = printer_capabilities.get("max_feedrate", original_feedrate * 1.5)
            optimized_feedrate = min(original_feedrate * feedrate_increase_factor, max_feed)
            # Update the feedrate in the command dictionary
            params_val["F"] = optimized_feedrate

            # Future Placeholder: Use material_properties to adjust extrusion, cooling, etc.
            # This is where geometric analysis results would be used:
            # identified_features = analyze_geometric_features([line], logger) # Analyze this line or context around it
            # if identified_features:
            #     # Adjust extrusion/speed based on feature type, material, printer caps, etc.
            #     pass


            # Reconstruct the G-code line with the optimized parameters
            optimized_line = reconstruct_gcode_line({"cmd": cmd_val, "params": params_val})
            optimized_gcode.append(optimized_line)
        except Exception as e:
            logger.error(f"Error optimizing G-code line '{original_line}': {e}. Appending original line.")
            optimized_gcode.append(line)

    return optimized_gcode

# 4. Function to apply AI-driven optimizations to G-code commands.
def apply_ai_optimizations(gcode_lines: List[str],
                           material_name: str, # Changed
                           printer_capabilities: dict) -> List[str]:
    """
    Applies AI-driven optimizations to G-code commands.

    Args:
        gcode_lines: List of raw G-code strings.
        material_name: Name of the material (e.g., "PLA").
        printer_capabilities: Dict of printer capabilities.

    Returns:
        List of optimized G-code strings.
    """
    logger.info(f"Applying AI-driven optimizations to G-code for material: {material_name}...")
    # Currently, this just calls optimize_gcode which does basic material-aware feedrate adjustment
    optimized_gcode = optimize_gcode(gcode_lines, material_name, printer_capabilities)
    return optimized_gcode

# Placeholder for geometric feature analysis
def analyze_geometric_features(gcode_lines: List[str], logger_instance: logging.Logger) -> List[Dict]:
    """
    Analyzes G-code lines to identify geometric features relevant for extrusion rate adaptation. (Phase 2.1).
    This is a placeholder for implementing Phase 2, Item 2.1: Feature Geometry Analysis.

    Identifiable features could include:
    - Corners: Sharp changes in print direction.
    - Curves: Sequences of short segments approximating an arc.
    - Infill Sections: Based on G-code comments (e.g., ';TYPE:FILL') or path patterns.
    - Overhangs: Requires Z-axis awareness and comparison with previously printed layers/supports.
                 (More complex, likely a later stage of implementation).
    - Short Segments: Potentially requiring speed/extrusion adjustments.
    - Travel Moves: G0 commands, already handled by travel minimization but relevant for context.

    The analysis would involve:
    1. Robust G-code parsing (command type, parameters like X, Y, Z, E, F, and tracking position).
       The `parse_gcode` function in this module is more suitable for this than `parse_gcode_line`.
    2. Maintaining state (current position, previous position, current layer).
    3. Vector math for angle calculations (corners, curves).
    4. Heuristics or pattern recognition for infill/overhangs.

    Args:
        gcode_lines: List of G-code strings.
        logger_instance: Logger for logging messages.

    Returns:
        A list of dictionaries, where each dictionary represents an identified feature
        and its properties. For example:
        [
            {'type': 'corner', 'line_number': 10, 'coordinates': (x,y,z), 'angle_degrees': 45},
            {'type': 'curve_segment', 'line_start': 15, 'line_end': 25, 'radius_estimate': 5.0},
            {'type': 'infill_block', 'line_start': 30, 'line_end': 100, 'density_estimate': 0.4}
        ]
        Currently, this placeholder returns an empty list.
    """
    logger_instance.info("Starting geometric feature analysis (Phase 2.1 - Corner Detection)...")

    # Example of how you might use the more robust parser:
    parsed_commands = parse_gcode(gcode_lines)

    identified_features: List[Dict] = []

    current_pos = (0.0, 0.0, 0.0) # Track current position (X, Y, Z)
    prev_print_start_pos = None
    prev_print_end_pos = None
    # Threshold for detecting a corner (angle between consecutive print vectors in degrees)
    # A smaller angle means a sharper turn (e.g., 0 degrees for a U-turn, 180 for straight).
    # We are looking for angles significantly less than 180.
    # Let's define a corner as an angle between vectors less than 150 degrees (a turn of 30+ degrees).
    CORNER_DETECTION_THRESHOLD_DEGREES = 150.0 # Angle between vectors (0=U-turn, 180=straight)

    for cmd_dict in parsed_commands:
        cmd = cmd_dict.get('command')
        line_num = cmd_dict.get('line_number')

        # Get the position *before* this command executes
        segment_start_pos = current_pos

        # Update current position based on positioning commands
        if 'current_pos' in cmd_dict:
             pos_dict = cmd_dict['current_pos']
             # Update current_pos to the position *after* this command executes
             current_pos = (pos_dict['X'], pos_dict['Y'], pos_dict['Z'])
             segment_end_pos = current_pos # This is the end position of the current command's move

             # Check if this is a printing move (G1 with extrusion)
             if cmd == 'G1' and cmd_dict.get('E', 0.0) > 0.001:
                 # This is a print segment: segment_start_pos -> segment_end_pos

                 if prev_print_end_pos is not None:
                     # Calculate the angle between the previous and current print segments
                     angle = calculate_angle_between_segments(
                         prev_print_start_pos, prev_print_end_pos,
                         segment_start_pos, segment_end_pos
                     )

                     # Check if the angle indicates a corner (deviation from straight)
                     # Angle between vectors: 180 is straight, 0 is U-turn.
                     # We are looking for angles significantly less than 180.
                     if angle < CORNER_DETECTION_THRESHOLD_DEGREES:
                         identified_features.append({
                             'type': 'corner',
                             'line_number': line_num,
                             'coordinates': segment_start_pos, # The point where the corner occurs (start of the second segment)
                             'angle_degrees': angle
                         })
                         logger_instance.debug(f"Identified corner at line {line_num}, pos {segment_start_pos}, angle {angle:.2f} deg")

                 # Update the previous print segment to the current one
                 prev_print_start_pos = segment_start_pos
                 prev_print_end_pos = segment_end_pos

             elif cmd == 'G0': # Travel move
                 # This is a travel move. It updates the current position,
                 # but it breaks any sequence of print segments for corner detection.
                 # Reset previous print segment tracking.
                 prev_print_start_pos = None # Reset previous print segment tracking
                 prev_print_end_pos = None # Reset previous print segment tracking
                 # logger_instance.debug(f"Detected travel move at line {line_num}. Resetting print segment tracking.") # Too noisy

             # For other positioning commands like G92, G28, they also break print sequences
             elif cmd in ['G92', 'G28']:
                  prev_print_start_pos = None # Reset previous print segment tracking
                  prev_print_end_pos = None
                  # logger_instance.debug(f"Detected positioning command ({cmd}) at line {line_num}. Resetting print segment tracking.") # Too noisy

        # For non-positioning commands, or commands without 'current_pos', current_pos remains unchanged.

    logger_instance.info(
        "Geometric feature analysis (corner detection) complete. "
        "Identified %d corners.",
        len(identified_features)
    )
    return identified_features

# Note: Helper functions for travel minimization (nearest_neighbor_path, two_opt_optimization)
# are also included in this file as they are related to path analysis, although not directly used by the current optimize_gcode.
# They might be refactored or moved to a dedicated travel_optimizer module later.
