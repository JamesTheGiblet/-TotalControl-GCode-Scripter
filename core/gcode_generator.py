# core/gcode_generator.py
# This module is the core engine for generating G-code from various path segment
# definitions. It handles different segment types (lines, arcs, spirals, etc.),
# transformations, and the overall assembly of G-code commands.

#Imports
import math
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

# 1. Generate G-code for a Single Segment
def generate_gcode_segment(segment: dict) -> List[str]:
    gcode_commands = []
    segment_type = segment.get("type")

    if segment_type == "line":
        gcode_commands.extend(generate_gcode_line(segment))
    elif segment_type == "arc":
        gcode_commands.extend(generate_gcode_arc(segment))
    elif segment_type == "bezier":
        gcode_commands.extend(generate_gcode_bezier(segment)) # generate_gcode_bezier is now imported
    elif segment_type == "spiral":
        gcode_commands.extend(generate_gcode_spiral(segment))
    elif segment_type == "style":
        gcode_commands.extend(generate_gcode_style(segment))
    elif segment_type == "repeat":
        gcode_commands.extend(generate_gcode_repeat(segment))
    elif segment_type == "structure":
        gcode_commands.extend(generate_gcode_structure(segment))
    else:
        raise ValueError(f"Unsupported segment type: {segment_type}")

    # Apply transformations if defined directly on the segment
    if "transform" in segment and isinstance(segment["transform"], dict):
        # Note: The apply_transformation function expects base_offset for repeat scenarios.
        # For direct segment transformation, base_offset is None or [0,0,0].
        gcode_commands = apply_transformation(gcode_commands, segment["transform"])

    return gcode_commands


# 2. Generate G-code for a Style Segment
def generate_gcode_style(segment: dict) -> List[str]:
    style_type = segment.get("style_type")
    sub_segments = segment.get("sub_segments", [])
    gcode_commands = []

    if not sub_segments:
        print(f"Warning: Style segment '{style_type}' has no sub_segments.")
        return []

    # Example: 'organic' style might apply a smoothing modifier to its sub-segments
    # or generate them in a specific way.
    # 'geometric' might ensure sharp corners or use specific geometric primitives.
    # This function currently just processes sub_segments as defined.
    # A more advanced 'style' could transform or generate sub_segments based on 'style_type'.

    for sub_segment_data in sub_segments:
        # Potentially modify sub_segment_data based on style_type before generating G-code
        # e.g., if style_type == "organic", maybe increase resolution for spirals
        # if sub_segment_data["type"] == "spiral" and style_type == "organic":
        #     sub_segment_data["num_points"] = sub_segment_data.get("num_points", DEFAULT_RESOLUTION) * 2
        gcode_commands.extend(generate_gcode_segment(sub_segment_data))
    
    if not gcode_commands and sub_segments:
        print(f"Warning: Style segment '{style_type}' produced no G-code from its sub_segments.")

    return gcode_commands


# 3. Generate G-code for a Repeat Segment
def generate_gcode_repeat(segment: dict) -> List[str]:
    count = segment.get("count", 1)
    repeated_segment_data = segment.get("segment")
    transform = segment.get("transform", {}) # e.g., {"rotate": ["z", 120], "offset": [10,0,0]}

    if not repeated_segment_data:
        raise ValueError("Repeat segment is missing the 'segment' to repeat.")

    gcode_commands = []
    current_origin_offset = [0,0,0] # Tracks cumulative offset for relative transformations

    for i in range(count):
        # Generate G-code for the base segment
        # Important: If transformations are meant to be cumulative or relative to the *end* of the last repetition,
        # the logic for applying transformations and managing the "current position" needs to be robust.
        # For now, assume transformation is applied to the segment as if it starts at its own local origin,
        # then the whole transformed block is added.
        
        segment_gcode = generate_gcode_segment(repeated_segment_data)
        
        # Apply transformation for this iteration
        # The `apply_transformation` function needs to handle the G-code strings.
        # If the transformation includes an offset, it should ideally be applied relative
        # to the end of the previous segment or a defined stacking behavior.
        # The current `apply_transformation` modifies coordinates in G1 commands.
        
        # Create a specific transform for this iteration if it's dynamic (e.g., cumulative rotation)
        # For simple repetition with the same transform, this is fine.
        # If transform has an offset, it's applied. If rotation, it's around origin unless segment is shifted.
        
        transformed_gcode = apply_transformation(segment_gcode, transform, iteration=i, total_iterations=count, base_offset=current_origin_offset)
        gcode_commands.extend(transformed_gcode)

        # Update current_origin_offset if transformations are meant to be cumulative
        # This part is complex and depends on how "repeat" is intended to work with transformations.
        # For example, if each repeat is offset from the previous one:
        if transform.get("type") == "cumulative_offset" and "offset_per_repeat" in transform:
            offset_per = transform["offset_per_repeat"]
            current_origin_offset[0] += offset_per[0]
            current_origin_offset[1] += offset_per[1]
            current_origin_offset[2] += offset_per[2]
        # Or if rotation is around the end point of the last segment of the previous repetition.
        # This requires more state tracking. The current `apply_transformation` is stateless.

    return gcode_commands


# 4. Generate G-code for a Structure Segment
def generate_gcode_structure(segment: dict) -> List[str]:
    structure_type = segment.get("structure_type")
    base_segment_data = segment.get("base_segment") # This might define the unit cell or region
    density = segment.get("density", 1.0) # Affects spacing or thickness
    # Other params: bounds, cell_size, etc.
    
    gcode_commands = []

    if not base_segment_data:
        # Some structures might not need a base_segment if they fill a predefined volume
        # or are purely generative based on other parameters (e.g., a bounding box).
        print(f"Warning: Structure segment '{structure_type}' may need 'base_segment' or other defining parameters.")

    if structure_type == "lattice":
        # Placeholder for AI-driven or procedural lattice generation
        # This would likely involve more complex logic than just processing a single base_segment.
        # It might tile a unit cell, generate struts and nodes, etc.
        # `base_segment_data` could define the bounding box or a unit cell.
        # `density` could control strut thickness or cell spacing.
        gcode_commands.extend(generate_gcode_lattice(base_segment_data, density)) # Assuming this function exists and is correctly imported
    elif structure_type == "honeycomb":
        # Similar to lattice, placeholder for specific honeycomb generation logic.
        gcode_commands.extend(generate_gcode_honeycomb(base_segment_data, density)) # Assuming this function exists
    else:
        raise ValueError(f"Unsupported structure type: {structure_type}")
    return gcode_commands


# 5. Generate G-code from JSON Input
def generate_gcode_from_json(json_input: Union[str, Dict]) -> List[str]:
    """
    Generate G-code from a JSON input.
    This function interprets the path segments and applies modifiers to generate the final G-code.
    """
    data = parse_json_input(json_input)

    gcode_output = ["G21 ; Set units to millimeters", "G90 ; Absolute positioning"]
    # Consider adding G28 (home) or M82 (absolute extrusion) if appropriate for the target printer setup.

    path_info = data.get("path", {})
    if not path_info:
        print("Warning: JSON input does not contain 'path' information.")
        return gcode_output + ["M2 ; End of program"]
        
    segments_data = path_info.get("segments", [])
    if not segments_data:
        print("Warning: Path has no segments.")
        # return gcode_output + ["M2 ; End of program"] # Decided to proceed to modifiers/constraints even with no segments

    raw_segments_gcode = []
    last_processed_segment_for_global_ops = None # Context for global modifiers/constraints

    # Track the current position to correctly calculate relative moves for arcs (I, J, K)
    # and for modifiers/constraints that depend on the end of the previous segment.
    current_position = [0.0, 0.0, 0.0] # Assume starting at origin unless specified

    for segment_dict in segments_data:
        segment_type = segment_dict.get("type")
        
        # Before generating arc G-code, ensure current_position is at the arc's start point.
        # The `generate_gcode_arc` function calculates I, J relative to the arc's start.
        # If the JSON defines an arc with "start_angle", "center", "radius", we need to
        # calculate that start point and potentially issue a G0/G1 to get there.
        if segment_type == "arc":
            center = segment_dict.get("center", [0,0,0])
            radius = segment_dict.get("radius", 0)
            start_angle_rad = math.radians(segment_dict.get("start_angle", 0))
            arc_start_x = center[0] + radius * math.cos(start_angle_rad)
            arc_start_y = center[1] + radius * math.sin(start_angle_rad)
            arc_start_z = center[2] # Assuming arc is planar in XY, Z from center

            # If current position is not already at arc_start_x, arc_start_y, arc_start_z, move there.
            # Using a small tolerance for floating point comparison.
            if not (math.isclose(current_position[0], arc_start_x) and \
                    math.isclose(current_position[1], arc_start_y) and \
                    math.isclose(current_position[2], arc_start_z)):
                # Add a travel move (G0) or a cutting move (G1) to the start of the arc
                # For now, assume G1, but this could be configurable (e.g. "rapid_move_to_arc_start": true)
                # This G1 command should also have feedrate and extrusion if it's a cutting move.
                # If it's just a positioning move, G0 is better.
                # Let's assume G0 for positioning to start of arc.
                gcode_output.append(f"G0 X{arc_start_x:.3f} Y{arc_start_y:.3f} Z{arc_start_z:.3f}")
                current_position = [arc_start_x, arc_start_y, arc_start_z]
        
        # For line segments, the "start" is often implicit from the end of the previous segment.
        # If "start" is explicitly provided and differs from current_position, a G0 move might be needed.
        elif segment_type == "line" and "start" in segment_dict:
            line_start = segment_dict["start"]
            if not (math.isclose(current_position[0], line_start[0]) and \
                    math.isclose(current_position[1], line_start[1]) and \
                    math.isclose(current_position[2], line_start[2])):
                gcode_output.append(f"G0 X{line_start[0]:.3f} Y{line_start[1]:.3f} Z{line_start[2]:.3f}")
                current_position = list(line_start)


        segment_gcode_list = generate_gcode_segment(segment_dict)
        raw_segments_gcode.extend(segment_gcode_list)
        
        # Update current_position based on the last command of the generated segment
        if segment_gcode_list:
            last_cmd_in_segment = segment_gcode_list[-1]
            # extract_last_point needs to be robust if X,Y,Z are not all present
            # or if the command is not a G1/G2/G3 move.
            # For G1/G2/G3, X,Y,Z define the end point.
            # If a coordinate is missing, it's assumed to be unchanged.
            # This logic needs careful handling.
            
            # A simple way: parse the last command for X, Y, Z.
            # If a coordinate is not in the command, it means it didn't change from the previous point *within that command's context*.
            # However, `current_position` should always reflect the absolute current tool head position.
            
            # Let's refine `extract_last_point` or how we use it.
            # `extract_last_point` returns (x,y,z) where missing values are None.
            # We need to update `current_position` based on this.
            
            # Example: if current_position = [10,20,5] and last_cmd is "G1 X15 Y25" (Z missing)
            # then new current_position should be [15,25,5].
            
            cmd_parts = last_cmd_in_segment.upper().split()
            next_x, next_y, next_z = current_position[0], current_position[1], current_position[2] # Start with current
            
            for part in cmd_parts:
                if part.startswith("X"): next_x = float(part[1:])
                elif part.startswith("Y"): next_y = float(part[1:])
                elif part.startswith("Z"): next_z = float(part[1:])
            current_position = [next_x, next_y, next_z]

        last_processed_segment_for_global_ops = segment_dict

    gcode_output.extend(raw_segments_gcode)

    # Apply global modifiers (applied to the whole path generated so far)
    # The 'segment' argument passed here is `last_processed_segment_for_global_ops`.
    # This might not be ideal if modifiers are truly global and not tied to the last segment.
    # `apply_modifier` in `ai_pathing.py` currently just appends a comment string.
    # If it were to modify existing G-code, it would need the `gcode_output` list.
    global_modifiers = path_info.get("modifiers", [])
    if isinstance(global_modifiers, list):
        for modifier_dict in global_modifiers:
            if isinstance(modifier_dict, dict):
                # The `apply_modifier` function from `ai_pathing` has signature:
                # apply_modifier(gcode, modifier, segment)
                # It returns the modified gcode list.
                gcode_output = apply_modifier(gcode_output, modifier_dict, last_processed_segment_for_global_ops)
            else:
                print(f"Warning: Global modifier is not a dictionary: {modifier_dict}")

    # Apply global constraints
    global_constraints = path_info.get("constraints", [])
    if isinstance(global_constraints, list):
        for constraint_dict in global_constraints:
            if isinstance(constraint_dict, dict):
                # The `apply_constraint` function from `ai_pathing` has signature:
                # apply_constraint(gcode_commands: List[str], constraint: dict, segment: dict) -> List[str]
                gcode_output = apply_constraint(gcode_output, constraint_dict, last_processed_segment_for_global_ops)
            else:
                print(f"Warning: Global constraint is not a dictionary: {constraint_dict}")
    
    # Filter redundant G0/G1 moves before finalizing
    gcode_output = filter_redundant_moves(gcode_output) # Now imported from utils

    gcode_output.append("M2 ; End of program")
    return gcode_output
