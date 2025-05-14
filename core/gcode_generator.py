# core/gcode_generator.py
# This module is the core engine for generating G-code from various path segment
# definitions. It handles different segment types (lines, arcs, spirals, etc.),
# transformations, and the overall assembly of G-code commands.

#Imports
import math
import logging # Added for logging
from typing import List, Dict, Union
from modules.ai_pathing import apply_constraint, apply_modifier, generate_gcode_honeycomb, generate_gcode_lattice
from core.utils import parse_json_input, filter_redundant_moves # Added filter_redundant_moves
from core.constants import DEFAULT_EXTRUSION_RATE, DEFAULT_FEEDRATE, DEFAULT_RESOLUTION
from core.transform import apply_transformation
from core.segment_primitives import (
    generate_gcode_line,
    generate_gcode_arc,
    generate_gcode_bezier,
    generate_gcode_spiral
)

# Setup a logger for this module
logger = logging.getLogger(__name__)

# 1. Generate G-code for a Single Segment
def generate_gcode_segment(segment: dict) -> List[str]:
    if not isinstance(segment, dict):
        logger.error(f"Segment data is not a dictionary: {segment}")
        return [] # Returning empty list for robustness if called in a loop

    gcode_commands = []
    segment_type = segment.get("type")
    segment_name_for_log = str(segment.get("name", segment_type if segment_type else "Unknown")) # For logging

    try:
        if segment_type == "line":
            gcode_commands.extend(generate_gcode_line(segment))
        elif segment_type == "arc":
            gcode_commands.extend(generate_gcode_arc(segment))
        elif segment_type == "bezier":
            gcode_commands.extend(generate_gcode_bezier(segment))
        elif segment_type == "spiral":
            gcode_commands.extend(generate_gcode_spiral(segment))
        elif segment_type == "style":
            gcode_commands.extend(generate_gcode_style(segment))
        elif segment_type == "repeat":
            gcode_commands.extend(generate_gcode_repeat(segment))
        elif segment_type == "structure":
            gcode_commands.extend(generate_gcode_structure(segment))
        elif segment_type is None:
            logger.error(f"Segment type is None for segment data: {str(segment)[:100]}. Cannot process.")
            raise ValueError("Segment type is None.")
        else:
            raise ValueError(f"Unsupported segment type: {segment_type}")

        # Apply transformations if defined directly on the segment
        if "transform" in segment:
            transform_params = segment.get("transform")
            if isinstance(transform_params, dict):
                gcode_commands = apply_transformation(gcode_commands, transform_params)
            elif transform_params is not None:
                logger.warning(f"Transform params for segment '{segment_name_for_log}' is not a dict: {transform_params}. Skipping transformation.")
    
    except ValueError as ve: 
        logger.error(f"ValueError processing segment '{segment_name_for_log}': {ve}")
        return [] # Return empty on ValueError to allow processing of other segments.
    except Exception as e:
        logger.error(f"Unexpected error processing segment '{segment_name_for_log}': {e}", exc_info=True)
        return []
    return gcode_commands


# 2. Generate G-code for a Style Segment
def generate_gcode_style(segment: dict) -> List[str]:
    if not isinstance(segment, dict):
        logger.error(f"Style segment data is not a dictionary: {segment}")
        return []

    style_type = segment.get("style_type", "UnknownStyle")
    sub_segments_data = segment.get("sub_segments", [])
    gcode_commands = []

    if not isinstance(sub_segments_data, list):
        logger.error(f"Style segment '{style_type}' has non-list sub_segments: {sub_segments_data}. Skipping.")
        return []
    
    if not sub_segments_data:
        logger.warning(f"Style segment '{style_type}' has no sub_segments.")
        return []

    # Example: 'organic' style might apply a smoothing modifier to its sub-segments
    # or generate them in a specific way.
    # 'geometric' might ensure sharp corners or use specific geometric primitives.

    for i, sub_segment_data in enumerate(sub_segments_data):
        if not isinstance(sub_segment_data, dict):
            logger.warning(f"Sub-segment at index {i} in style '{style_type}' is not a dictionary: {sub_segment_data}. Skipping.")
            continue
        try:
            # generate_gcode_segment is now robust and returns [] on error.
            gcode_commands.extend(generate_gcode_segment(sub_segment_data))
        except Exception as e: # Should be caught by generate_gcode_segment, but as a safeguard
            logger.error(f"Unexpected error processing sub-segment {i} in style '{style_type}': {e}", exc_info=True)
            # Continue with next sub-segment
    
    if not gcode_commands and sub_segments_data:
        logger.warning(f"Style segment '{style_type}' produced no G-code from its sub_segments (they might have all failed or were empty).")

    return gcode_commands


# 3. Generate G-code for a Repeat Segment
def generate_gcode_repeat(segment: dict) -> List[str]:
    if not isinstance(segment, dict):
        logger.error(f"Repeat segment data is not a dictionary: {segment}")
        return []

    gcode_commands = []
    try:
        count_val = segment.get("count", 1)
        if not isinstance(count_val, int) or count_val < 0:
            logger.error(f"Repeat segment has invalid count: {count_val}. Defaulting to 1.")
            count = 1
        else:
            count = count_val

        repeated_segment_data = segment.get("segment")
        if not isinstance(repeated_segment_data, dict):
            logger.error(f"Repeat segment is missing 'segment' data or it's not a dict: {repeated_segment_data}. Cannot repeat.")
            raise ValueError("Repeat segment is missing the 'segment' to repeat or it's not a dictionary.")

        transform_params = segment.get("transform", {})
        if not isinstance(transform_params, dict):
            logger.warning(f"Transform data for repeat segment is not a dict: {transform_params}. Using empty transform.")
            transform_params = {}

        current_origin_offset = [0.0, 0.0, 0.0]

        for i in range(count):
            segment_gcode = generate_gcode_segment(repeated_segment_data) # Robust
            
            try:
                transformed_gcode = apply_transformation(segment_gcode, transform_params, iteration=i, total_iterations=count, base_offset=current_origin_offset)
                gcode_commands.extend(transformed_gcode)
            except Exception as e_transform:
                logger.error(f"Error applying transformation during repeat iteration {i} for segment {repeated_segment_data.get('type', 'N/A')}: {e_transform}", exc_info=True)
                continue # Skip G-code for this iteration if transformation fails

            # Cumulative offset logic
            if transform_params.get("type") == "cumulative_offset":
                offset_per_repeat = transform_params.get("offset_per_repeat")
                if isinstance(offset_per_repeat, list) and len(offset_per_repeat) == 3:
                    try:
                        current_origin_offset[0] += float(offset_per_repeat[0])
                        current_origin_offset[1] += float(offset_per_repeat[1])
                        current_origin_offset[2] += float(offset_per_repeat[2])
                    except (ValueError, TypeError) as e_offset:
                        logger.warning(f"Invalid 'offset_per_repeat' values in transform: {offset_per_repeat}. Cumulative offset may be incorrect. Error: {e_offset}")
                elif offset_per_repeat is not None:
                    logger.warning(f"'offset_per_repeat' in transform is malformed: {offset_per_repeat}. Expected list of 3 numbers. Cumulative offset not applied.")
    
    except ValueError as ve:
        logger.error(f"ValueError in generate_gcode_repeat for segment data {segment.get('type', 'N/A')}: {ve}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in generate_gcode_repeat for segment data {segment.get('type', 'N/A')}: {e}", exc_info=True)
        return []
    return gcode_commands


# 4. Generate G-code for a Structure Segment
def generate_gcode_structure(segment: dict) -> List[str]:
    if not isinstance(segment, dict):
        logger.error(f"Structure segment data is not a dictionary: {segment}")
        return []

    gcode_commands = []
    structure_type = segment.get("structure_type")
    base_segment_data = segment.get("base_segment") 
    density = segment.get("density", 1.0)

    try:
        if not structure_type:
            raise ValueError("Structure segment is missing 'structure_type'.")

        if structure_type in ["lattice", "honeycomb"] and not isinstance(base_segment_data, dict) and base_segment_data is not None:
            logger.warning(f"Structure type '{structure_type}' expected 'base_segment' to be a dict or None, but got: {type(base_segment_data)}. Proceeding cautiously.")

        if structure_type == "lattice":
            gcode_commands.extend(generate_gcode_lattice(base_segment_data, density))
        elif structure_type == "honeycomb":
            gcode_commands.extend(generate_gcode_honeycomb(base_segment_data, density))
        else:
            raise ValueError(f"Unsupported structure type: {structure_type}")
            
    except ValueError as ve:
        logger.error(f"ValueError in generate_gcode_structure for type '{structure_type}': {ve}")
        return []
    except Exception as e:
        logger.error(f"Error generating G-code for structure type '{structure_type}': {e}", exc_info=True)
        return []
    return gcode_commands


# 5. Generate G-code from JSON Input
def generate_gcode_from_json(json_input: Union[str, Dict]) -> List[str]:
    """
    Generate G-code from a JSON input.
    This function interprets the path segments and applies modifiers to generate the final G-code.
    """
    try:
        data = parse_json_input(json_input)
    except (ValueError, TypeError) as e_parse:
        logger.error(f"Failed to parse JSON input: {e_parse}")
        return ["M2 ; End of program - Error parsing JSON input"]

    gcode_output = ["G21 ; Set units to millimeters", "G90 ; Absolute positioning"]
    
    path_info = data.get("path")
    if not isinstance(path_info, dict):
        logger.warning(f"'path' key missing or not a dictionary in JSON input. Proceeding with empty path.")
        path_info = {} 
        
    segments_data = path_info.get("segments", [])
    if not isinstance(segments_data, list):
        logger.warning(f"'segments' in path is not a list: {segments_data}. Treating as empty.")
        segments_data = []
    
    if not segments_data:
        logger.info("Path has no segments. Proceeding to global modifiers/constraints if any.")

    raw_segments_gcode = []
    last_processed_segment_for_global_ops = None # Context for global modifiers/constraints

    # Track the current position to correctly calculate relative moves for arcs (I, J, K)
    # and for modifiers/constraints that depend on the end of the previous segment.
    current_position = [0.0, 0.0, 0.0] # Assume starting at origin unless specified

    for i, segment_dict_raw in enumerate(segments_data):
        if not isinstance(segment_dict_raw, dict):
            logger.warning(f"Segment data at index {i} is not a dictionary: {segment_dict_raw}. Skipping.")
            continue
        
        segment_dict = dict(segment_dict_raw) # Shallow copy
        segment_type = segment_dict.get("type")

        try:
            # Pre-move logic for arcs and explicit line starts
            if segment_type == "arc":
                center_raw = segment_dict.get("center", [0.0, 0.0, 0.0])
                radius_raw = segment_dict.get("radius", 0.0)
                start_angle_deg_raw = segment_dict.get("start_angle", 0.0)

                center = center_raw if isinstance(center_raw, list) and len(center_raw) == 3 and all(isinstance(c, (int, float)) for c in center_raw) else [0.0,0.0,0.0]
                radius = float(radius_raw) if isinstance(radius_raw, (int, float)) else 0.0
                start_angle_deg = float(start_angle_deg_raw) if isinstance(start_angle_deg_raw, (int, float)) else 0.0
                if center_raw != center: logger.warning(f"Arc segment {i} had invalid center {center_raw}, using {center}.")
                if radius_raw != radius: logger.warning(f"Arc segment {i} had invalid radius {radius_raw}, using {radius}.")
                if start_angle_deg_raw != start_angle_deg: logger.warning(f"Arc segment {i} had invalid start_angle {start_angle_deg_raw}, using {start_angle_deg}.")

                start_angle_rad = math.radians(start_angle_deg)
                arc_start_x = center[0] + radius * math.cos(start_angle_rad)
                arc_start_y = center[1] + radius * math.sin(start_angle_rad)
                arc_start_z = center[2] 

                if not (math.isclose(current_position[0], arc_start_x) and \
                        math.isclose(current_position[1], arc_start_y) and \
                        math.isclose(current_position[2], arc_start_z)):
                    gcode_output.append(f"G0 X{arc_start_x:.3f} Y{arc_start_y:.3f} Z{arc_start_z:.3f}")
                    current_position = [arc_start_x, arc_start_y, arc_start_z]
            
            elif segment_type == "line":
                line_start_raw = segment_dict.get("start")
                if isinstance(line_start_raw, list) and len(line_start_raw) == 3 and all(isinstance(c, (int, float)) for c in line_start_raw):
                    line_start = line_start_raw
                    if not (math.isclose(current_position[0], line_start[0]) and \
                            math.isclose(current_position[1], line_start[1]) and \
                            math.isclose(current_position[2], line_start[2])):
                        gcode_output.append(f"G0 X{line_start[0]:.3f} Y{line_start[1]:.3f} Z{line_start[2]:.3f}")
                        current_position = list(line_start)
                elif line_start_raw is not None:
                     logger.warning(f"Line segment {i} has malformed 'start' coordinates: {line_start_raw}. Ignoring explicit start.")

            segment_gcode_list = generate_gcode_segment(segment_dict) # Robust
            raw_segments_gcode.extend(segment_gcode_list)
            
            if segment_gcode_list:
                last_cmd_in_segment = segment_gcode_list[-1]
                try:
                    cmd_parts = last_cmd_in_segment.upper().split()
                    temp_pos = list(current_position) 

                    for part_idx, part_str in enumerate(cmd_parts):
                        if not part_str or len(part_str) < 2 or not part_str[0].isalpha():
                            if part_idx > 0: # Don't warn for the command itself (e.g., G1)
                                logger.debug(f"Skipping malformed G-code part '{part_str}' in '{last_cmd_in_segment}' for position update.")
                            continue
                        
                        key = part_str[0]
                        value_str = part_str[1:]
                        
                        try:
                            value = float(value_str)
                            if key == "X": temp_pos[0] = value
                            elif key == "Y": temp_pos[1] = value
                            elif key == "Z": temp_pos[2] = value
                        except ValueError:
                            logger.warning(f"Could not parse coordinate value '{value_str}' from part '{part_str}' in command '{last_cmd_in_segment}'. Position might be inaccurate.")
                    current_position = temp_pos
                except Exception as e_pos:
                    logger.error(f"Error updating current_position from command '{last_cmd_in_segment}': {e_pos}", exc_info=True)
            
            last_processed_segment_for_global_ops = segment_dict

        except Exception as e_segment_proc:
            logger.error(f"Unexpected error processing segment index {i} ({segment_dict.get('type', 'Unknown')}): {e_segment_proc}", exc_info=True)
            # Continue to the next segment

    gcode_output.extend(raw_segments_gcode)

    # Global modifiers
    try:
        global_modifiers = path_info.get("modifiers", [])
        if not isinstance(global_modifiers, list):
            logger.warning(f"'modifiers' in path is not a list: {global_modifiers}. Skipping modifiers.")
            global_modifiers = []

        for mod_idx, modifier_dict in enumerate(global_modifiers):
            if isinstance(modifier_dict, dict):
                try:
                    gcode_output = apply_modifier(gcode_output, modifier_dict, last_processed_segment_for_global_ops)
                except Exception as e_mod:
                    logger.error(f"Error applying global modifier at index {mod_idx} ({modifier_dict.get('type', 'Unknown')}): {e_mod}", exc_info=True)
            else:
                logger.warning(f"Global modifier at index {mod_idx} is not a dictionary: {modifier_dict}. Skipping.")
    except Exception as e_global_mod_block:
        logger.error(f"Unexpected error during global modifier processing block: {e_global_mod_block}", exc_info=True)

    # Global constraints
    try:
        global_constraints = path_info.get("constraints", [])
        if not isinstance(global_constraints, list):
            logger.warning(f"'constraints' in path is not a list: {global_constraints}. Skipping constraints.")
            global_constraints = []

        for con_idx, constraint_dict in enumerate(global_constraints):
            if isinstance(constraint_dict, dict):
                try:
                    gcode_output = apply_constraint(gcode_output, constraint_dict, last_processed_segment_for_global_ops)
                except Exception as e_con:
                    logger.error(f"Error applying global constraint at index {con_idx} ({constraint_dict.get('type', 'Unknown')}): {e_con}", exc_info=True)
            else:
                logger.warning(f"Global constraint at index {con_idx} is not a dictionary: {constraint_dict}. Skipping.")
    except Exception as e_global_con_block:
        logger.error(f"Unexpected error during global constraint processing block: {e_global_con_block}", exc_info=True)
    
    try:
        gcode_output = filter_redundant_moves(gcode_output)
    except Exception as e_filter:
        logger.error(f"Error during G-code filtering: {e_filter}", exc_info=True)

    gcode_output.append("M2 ; End of program")
    return gcode_output
