# modules/ai_pathing.py
# This module contains functions related to AI-driven path generation,
# modifications, and constraint applications for G-code.

#Imports
from typing import List, Dict
import logging # Added for logging
import numpy as np
from core.constants import DEFAULT_EXTRUSION_RATE, DEFAULT_FEEDRATE, DEFAULT_SMOOTHING_LEVEL

# Setup a logger for this module
logger = logging.getLogger(__name__)

# 1. Generate G-code for Lattice Structure
def generate_gcode_lattice(base_segment: dict, density: float) -> List[str]:
    """Generates G-code for a lattice structure (placeholder)."""
    logger.debug(f"Generating lattice G-code. Base segment: {str(base_segment)[:100]}, Density: {density}")
    if not isinstance(base_segment, dict):
        logger.warning(f"Lattice 'base_segment' is not a dictionary: {type(base_segment)}. Using placeholder behavior.")
        # Allow placeholder to function, but log it.
    if not isinstance(density, (int, float)):
        logger.warning(f"Lattice 'density' is not a number: {type(density)}. Using placeholder behavior.")
        # Allow placeholder to function.

    # Placeholder implementation
    gcode = [
        f"G1 X0 Y0 Z0 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}",
        f"G1 X10 Y10 Z10 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
    ]
    logger.info(f"Successfully generated {len(gcode)} lines for placeholder lattice structure.")
    return gcode


# 2. Generate G-code for Honeycomb Structure
def generate_gcode_honeycomb(base_segment: dict, density: float) -> List[str]:
    """Generates G-code for a honeycomb structure (placeholder)."""
    logger.debug(f"Generating honeycomb G-code. Base segment: {str(base_segment)[:100]}, Density: {density}")
    if not isinstance(base_segment, dict):
        logger.warning(f"Honeycomb 'base_segment' is not a dictionary: {type(base_segment)}. Using placeholder behavior.")
    if not isinstance(density, (int, float)):
        logger.warning(f"Honeycomb 'density' is not a number: {type(density)}. Using placeholder behavior.")

    # Placeholder implementation
    gcode = [
        f"G1 X0 Y0 Z0 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}",
        f"G1 X10 Y10 Z10 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
    ]
    logger.info(f"Successfully generated {len(gcode)} lines for placeholder honeycomb structure.")
    return gcode


# 3. Apply Modifier to G-code
def apply_modifier(gcode: List[str], modifier: Dict, segment: Dict) -> List[str]:
    """
    Apply a modifier to the generated G-code.
    Currently supports 'offset' and 'smooth' modifiers, but more can be added as needed.
    """
    logger.debug(f"Applying modifier: {str(modifier)[:100]}. Segment context: {str(segment)[:100] if segment else 'None'}")
    if not isinstance(gcode, list):
        logger.error(f"Input 'gcode' to apply_modifier is not a list: {type(gcode)}. Returning as is.")
        return gcode

    # Check if modifier is a dictionary before proceeding
    if isinstance(modifier, dict):
        if modifier.get("type") == "offset":
            # Example of applying an offset modifier to the segment
            distance = modifier.get("distance", 0)
            gcode.append(f"G1 Offset modifier: {distance}")
        elif modifier.get("type") == "smooth":
            # Example of applying a smooth modifier
            level = modifier.get("level", 1)
            gcode.append(f"G1 Smooth modifier: level {level}")
        else:
            logger.warning(f"Unrecognized modifier type: {modifier.get('type')}")
    else:
        logger.error(f"Modifier is not a dictionary: {modifier}. No modifier applied.")
    
    logger.debug(f"Finished applying modifier. G-code length now: {len(gcode)}")
    return gcode


# 4. Apply Offset to Path
def apply_offset(gcode_commands: List[str], distance: float, segment: dict) -> List[str]:
    """Applies an offset to the path based on normal vectors."""
    points = []
    logger.debug(f"Applying offset. Distance: {distance}. Segment context: {str(segment)[:100] if segment else 'None'}")

    if not isinstance(gcode_commands, list):
        logger.error(f"Input 'gcode_commands' to apply_offset is not a list: {type(gcode_commands)}. Returning as is.")
        return gcode_commands
    if not isinstance(distance, (int, float)):
        logger.error(f"Offset 'distance' is not a number: {type(distance)}. Cannot apply offset.")
        return gcode_commands

    # Extract X, Y, Z coordinates from G-code commands
    for command in gcode_commands:
        x = y = z = None
        try:
            for part in command.split():
                if part.startswith("X"):
                    x = float(part[1:])
                elif part.startswith("Y"):
                    y = float(part[1:])
                elif part.startswith("Z"):
                    z = float(part[1:])
            if x is not None and y is not None and z is not None: # Ensure all three were found and parsed
                points.append((x, y, z))
        except ValueError as e:
            logger.warning(f"Could not parse coordinates from G-code command '{command}' for offset: {e}. Skipping command for point extraction.")
            continue

    if not points:
        logger.warning("No points extracted from G-code commands for offset calculation. Returning original commands.")
        return gcode_commands
    if len(points) < 2: # Need at least 2 points to define segments for normals
        logger.warning(f"Not enough points ({len(points)}) to calculate offset normals. Returning original commands.")
        return gcode_commands
    # Calculate offset points
    offset_points = []
    for i in range(len(points)):
        # Define the current point (p2) and its neighbors (p1, p3) for normal calculation
        p1 = points[i - 1] # Previous point (wraps around for the first point)
        p2 = points[i]     # Current point
        p3 = points[(i + 1) % len(points)] # Next point (wraps around for the last point)

        # Direction vectors
        dx1, dy1 = p2[0] - p1[0], p2[1] - p1[1]
        dx2, dy2 = p3[0] - p2[0], p3[1] - p2[1]

        # Normals to the segments (assuming 2D offset in XY plane)
        nx1, ny1 = -dy1, dx1 # Normal to segment (p1,p2)
        nx2, ny2 = -dy2, dx2 # Normal to segment (p2,p3)

        # Normalize the normal vectors
        len1 = np.hypot(nx1, ny1)
        len2 = np.hypot(nx2, ny2)
        if len1 > 0:
            nx1 /= len1
            ny1 /= len1
        if len2 > 0:
            nx2 /= len2
            ny2 /= len2

        # Calculate the offset point.
        # If segments are collinear, the offset is simply along the common normal.
        if np.isclose(nx1, nx2) and np.isclose(ny1, ny2):
            ox = p2[0] + nx1 * distance
            oy = p2[1] + ny1 * distance
        else:
            # For non-collinear segments, calculate the intersection of the offset lines.
            # This involves solving a system of linear equations for the intersection point.
            k1 = p1[0] * ny1 - p1[1] * nx1
            k2 = p2[0] * ny2 - p2[1] * nx2
            det = nx1 * ny2 - ny1 * nx2
            if det != 0:
                ox = (ny2 * k1 - ny1 * k2) / det + distance * (nx2 - nx1) / det
                oy = (nx1 * k2 - nx2 * k1) / det + distance * (ny2 - ny1) / det
            else: # Should ideally not happen if not collinear, but as a fallback
                ox = p2[0] + nx1 * distance
                oy = p2[1] + ny1 * distance
        offset_points.append((ox, oy, p2[2])) # Keep original Z

    new_gcode = [
        f"G1 X{ox:.3f} Y{oy:.3f} Z{oz:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        for ox, oy, oz in offset_points
    ]
    logger.info(f"Successfully applied offset. Generated {len(new_gcode)} offset G-code commands.")
    return new_gcode


# 5. Apply Smoothing to Path
def apply_smoothing(gcode_commands: List[str], level: int, segment: dict) -> List[str]:
    """Applies smoothing to the G-code path using weighted averaging."""
    if level <= 0:
        return gcode_commands
    
    logger.debug(f"Applying smoothing. Level: {level}. Segment context: {str(segment)[:100] if segment else 'None'}")
    if not isinstance(gcode_commands, list):
        logger.error(f"Input 'gcode_commands' to apply_smoothing is not a list: {type(gcode_commands)}. Returning as is.")
        return gcode_commands
    if not isinstance(level, int):
        logger.error(f"Smoothing 'level' is not an integer: {type(level)}. Cannot apply smoothing.")
        return gcode_commands
        
    points = []
    # Extract X, Y, Z coordinates from G-code commands
    for command in gcode_commands:
        x = y = z = None
        try:
            for part in command.split():
                if part.startswith("X"):
                    x = float(part[1:])
                elif part.startswith("Y"):
                    y = float(part[1:])
                elif part.startswith("Z"):
                    z = float(part[1:])
            if x is not None and y is not None and z is not None:
                points.append((x, y, z))
        except ValueError as e:
            logger.warning(f"Could not parse coordinates from G-code command '{command}' for smoothing: {e}. Skipping command for point extraction.")
            continue

    if not points:
        logger.warning("No points extracted from G-code commands for smoothing. Returning original commands.")
        return gcode_commands
    if len(points) < 3: # Smoothing needs at least 3 points for meaningful neighbor calculations
        logger.warning(f"Not enough points ({len(points)}) for smoothing. Returning original commands.")
        return gcode_commands
    def smooth_pass(points: List[tuple]) -> List[tuple]:
        """
        Performs a single smoothing pass using a weighted average of a point
        and its immediate neighbors. (p[i-1] + 2*p[i] + p[i+1]) / 4.
        """
        return [
            (
                (points[i - 1][0] + 2 * points[i][0] + points[(i + 1) % len(points)][0]) / 4,
                (points[i - 1][1] + 2 * points[i][1] + points[(i + 1) % len(points)][1]) / 4,
                (points[i - 1][2] + 2 * points[i][2] + points[(i + 1) % len(points)][2]) / 4
            )
            for i in range(len(points))
        ]

    for _ in range(min(level, 2)):  # Limit to 2 smoothing passes for performance
                                    # and to prevent excessive shrinking/distortion.

        points = smooth_pass(points)
    
    new_gcode = [
        f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        for x, y, z in points
    ]
    logger.info(f"Successfully applied smoothing. Generated {len(new_gcode)} smoothed G-code commands.")
    return new_gcode


# 6. Apply Constraint to G-code
def apply_constraint(gcode_commands: List[str], constraint: dict, segment: dict) -> List[str]:
    """Applies constraints such as connection or tangents between segments."""
    logger.debug(f"Applying constraint: {str(constraint)[:100]}. Segment context: {str(segment)[:100] if segment else 'None'}")

    if not isinstance(gcode_commands, list):
        logger.error(f"Input 'gcode_commands' to apply_constraint is not a list: {type(gcode_commands)}. Returning as is.")
        return gcode_commands
    if not isinstance(constraint, dict):
        logger.error(f"'constraint' is not a dictionary: {type(constraint)}. Cannot apply constraint.")
        return gcode_commands
    if not isinstance(segment, dict) and constraint.get("type") == "connect": # Segment context needed for connect
        logger.error(f"'segment' context is not a dictionary and is required for 'connect' constraint. Cannot apply constraint.")
        return gcode_commands

    constraint_type = constraint.get("type")
    if constraint_type == "connect" and constraint.get("previous_segment", False):
        previous_end = segment.get("previous_end_point") # segment should be a dict here
        if isinstance(previous_end, (list, tuple)) and len(previous_end) == 3:
            if gcode_commands: # Ensure there's a command to modify
                try:
                    x, y, z = float(previous_end[0]), float(previous_end[1]), float(previous_end[2])
                    gcode_commands[0] = f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
                    logger.info(f"Applied 'connect' constraint. First command updated to start at {previous_end}.")
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid 'previous_end_point' coordinates {previous_end} for 'connect' constraint: {e}")
            else:
                logger.warning("Cannot apply 'connect' constraint: gcode_commands list is empty.")
        elif previous_end is not None: # It exists but is malformed
            logger.warning(f"'connect' constraint: 'previous_end_point' in segment is malformed: {previous_end}. Constraint not applied.")
    elif constraint_type == "tangent":
        logger.info("Placeholder for 'tangent' constraint. Not yet implemented.")
        # direction = constraint.get("direction")
    elif constraint_type:
        logger.warning(f"Unknown constraint type: '{constraint_type}'. Constraint not applied.")
    
    logger.debug(f"Finished applying constraint. G-code length: {len(gcode_commands)}")
    return gcode_commands 
