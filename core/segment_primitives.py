# core/segment_primitives.py
# This module contains functions to generate G-code for primitive path segments
# like lines, arcs, Bezier curves, and spirals.

import math
from typing import List, Dict
import logging # Added for logging
from core.constants import DEFAULT_FEEDRATE, DEFAULT_EXTRUSION_RATE, DEFAULT_RESOLUTION

# Setup a logger for this module
logger = logging.getLogger(__name__)

# 1. Generate G-code for Line Segment
def generate_gcode_line(segment: dict) -> List[str]:
    """Generates G-code for a line segment."""
    logger.debug(f"Generating G-code for line segment: {str(segment)[:100]}")
    if not isinstance(segment, dict):
        logger.error(f"Line segment data is not a dictionary: {type(segment)}. Skipping.")
        return []

    end_coords = segment.get("end")
    if not isinstance(end_coords, (list, tuple)) or len(end_coords) != 3:
        logger.error(f"Line segment 'end' coordinates are invalid or missing: {end_coords}. Expected list/tuple of 3 numbers. Skipping.")
        return []
    
    try:
        x, y, z = float(end_coords[0]), float(end_coords[1]), float(end_coords[2])
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid coordinate values in line segment 'end': {end_coords}. Error: {e}. Skipping.")
        return []

    gcode = [f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"]
    logger.info(f"Successfully generated line segment G-code: {gcode[0]}")
    return gcode

# 2. Generate G-code for Arc Segment
def generate_gcode_arc(segment: dict) -> List[str]:
    """Generates G-code for an arc segment using I, J, K or R format."""
    logger.debug(f"Generating G-code for arc segment: {str(segment)[:100]}")
    if not isinstance(segment, dict):
        logger.error(f"Arc segment data is not a dictionary: {type(segment)}. Skipping.")
        return []

    try:
        center_coords = segment.get("center", [0.0, 0.0, 0.0])
        if not isinstance(center_coords, (list, tuple)) or len(center_coords) != 3:
            logger.error(f"Arc 'center' is invalid: {center_coords}. Defaulting to [0,0,0] or skipping if critical.")
            # Decide if this is a critical error or if defaults are acceptable
            # For now, let's assume defaults are okay if other params are fine, but log a warning.
            # If this were critical, return []
            center_coords = [0.0, 0.0, 0.0] # Or raise error / return []

        center_x, center_y, center_z = float(center_coords[0]), float(center_coords[1]), float(center_coords[2])
        
        radius = float(segment.get("radius", 0.0))
        if radius <= 0:
            logger.warning(f"Arc radius is non-positive ({radius}). This might lead to invalid G-code. Using as is.")

        start_angle_deg = float(segment.get("start_angle", 0.0))
        end_angle_deg = float(segment.get("end_angle", 0.0))
        clockwise = segment.get("clockwise", True)

        start_angle_rad = math.radians(start_angle_deg)
        end_angle_rad = math.radians(end_angle_deg)
        arc_command = "G2" if clockwise else "G3"

        end_x = center_x + radius * math.cos(end_angle_rad)
        end_y = center_y + radius * math.sin(end_angle_rad)
        # z_coord is typically the Z of the center for planar XY arcs

        # Current position (start of arc) is needed for I, J calculation.
        # This is usually handled by gcode_generator.py ensuring a G0 to the arc start.
        # Here, we calculate I, J relative to the arc's defined start point based on its parameters.
        arc_start_x = center_x + radius * math.cos(start_angle_rad)
        arc_start_y = center_y + radius * math.sin(start_angle_rad)

        i_offset = center_x - arc_start_x
        j_offset = center_y - arc_start_y
        # K_offset would be center_z - arc_start_z if doing 3D arcs. G2/G3 IJK is typically planar.

    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Error parsing arc segment parameters: {e}. Segment data: {str(segment)[:200]}. Skipping.")
        return []

    gcode = [f"{arc_command} X{end_x:.3f} Y{end_y:.3f} Z{center_z:.3f} I{i_offset:.3f} J{j_offset:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"]
    logger.info(f"Successfully generated arc segment G-code: {gcode[0]}")
    return gcode

# 3. Generate G-code for Bezier Curve Segment
def generate_gcode_bezier(segment: dict) -> List[str]:
    """Generates G-code for a Bézier curve segment by linear approximation."""
    logger.debug(f"Generating G-code for Bezier segment: {str(segment)[:100]}")
    if not isinstance(segment, dict):
        logger.error(f"Bezier segment data is not a dictionary: {type(segment)}. Skipping.")
        return []

    control_points_raw = segment.get("control_points")
    if not isinstance(control_points_raw, list):
        logger.error(f"Bezier 'control_points' is not a list or missing: {control_points_raw}. Skipping.")
        return []

    num_points = segment.get("num_points", DEFAULT_RESOLUTION)
    if not isinstance(num_points, int) or num_points <= 0:
        logger.warning(f"Invalid 'num_points' for Bezier: {num_points}. Defaulting to {DEFAULT_RESOLUTION}.")
        num_points = DEFAULT_RESOLUTION

    gcode_commands = []
    control_points = []

    for i, p_raw in enumerate(control_points_raw):
        if not isinstance(p_raw, (list, tuple)) or len(p_raw) != 3:
            logger.error(f"Invalid control point at index {i} for Bezier: {p_raw}. Skipping Bezier generation.")
            return []
        try:
            control_points.append(tuple(float(c) for c in p_raw))
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid coordinate values in control point {i} for Bezier: {p_raw}. Error: {e}. Skipping.")
            return []

    if len(control_points) < 2:
        logger.error("Bezier curve requires at least two control points.")
        raise ValueError("Bezier curve requires at least two control points.")
    
    if len(control_points) == 3: # Quadratic Bezier
        p0, p1, p2 = control_points[0], control_points[1], control_points[2]
        for i in range(num_points + 1):
            t = i / num_points
            x = (1 - t)**2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
            y = (1 - t)**2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
            z = (1 - t)**2 * p0[2] + 2 * (1 - t) * t * p1[2] + t**2 * p2[2]
            gcode_commands.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}")
    elif len(control_points) == 4: # Cubic Bezier
        p0, p1, p2, p3 = control_points[0], control_points[1], control_points[2], control_points[3]
        for i in range(num_points + 1):
            t = i / num_points
            x = (1-t)**3 * p0[0] + 3*(1-t)**2 * t * p1[0] + 3*(1-t) * t**2 * p2[0] + t**3 * p3[0]
            y = (1-t)**3 * p0[1] + 3*(1-t)**2 * t * p1[1] + 3*(1-t) * t**2 * p2[1] + t**3 * p3[1]
            z = (1-t)**3 * p0[2] + 3*(1-t)**2 * t * p1[2] + 3*(1-t) * t**2 * p2[2] + t**3 * p3[2]
            gcode_commands.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}")
    else:
        logger.error("Bezier curve implementation currently supports 3 or 4 control points.")
        raise ValueError("Bezier curve implementation currently supports 3 or 4 control points.")
    
    logger.info(f"Successfully generated {len(gcode_commands)} G-code lines for Bezier segment.")
    return gcode_commands

# 4. Generate G-code for Spiral Segment
def generate_gcode_spiral(segment: dict) -> List[str]:
    """Generates G-code for a spiral segment."""
    logger.debug(f"Generating G-code for spiral segment: {str(segment)[:100]}")
    if not isinstance(segment, dict):
        logger.error(f"Spiral segment data is not a dictionary: {type(segment)}. Skipping.")
        return []

    gcode_commands = []
    try:
        center_coords = segment.get("center", [0.0, 0.0, 0.0])
        if not isinstance(center_coords, (list, tuple)) or len(center_coords) != 3:
            logger.error(f"Spiral 'center' is invalid: {center_coords}. Defaulting to [0,0,0].")
            center_coords = [0.0, 0.0, 0.0]
        
        center_x, center_y, center_z = float(center_coords[0]), float(center_coords[1]), float(center_coords[2])

        inner_radius = float(segment.get("inner_radius", 0.0))
        outer_radius = float(segment.get("outer_radius", 10.0))
        turns = float(segment.get("turns", 10.0))
        pitch = float(segment.get("pitch", 1.0)) # Z change per turn
        num_points = segment.get("num_points", DEFAULT_RESOLUTION)
        if not isinstance(num_points, int) or num_points <= 0:
            logger.warning(f"Invalid 'num_points' for spiral: {num_points}. Defaulting to {DEFAULT_RESOLUTION}.")
            num_points = DEFAULT_RESOLUTION

        if outer_radius < inner_radius:
            logger.warning(f"Outer radius ({outer_radius}) < inner radius ({inner_radius}) for spiral. This may produce unexpected results.")
        if turns <= 0:
            logger.warning(f"Number of turns ({turns}) for spiral is non-positive. This may produce unexpected results.")

        total_angle = turns * 2 * math.pi

        for i in range(num_points + 1):
            t = i / num_points
            current_angle = t * total_angle
            current_radius = inner_radius + (outer_radius - inner_radius) * t
            x = center_x + current_radius * math.cos(current_angle)
            y = center_y + current_radius * math.sin(current_angle)
            current_z_offset = t * turns * pitch
            z = center_z + current_z_offset
            gcode_commands.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}")

    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Error parsing spiral segment parameters: {e}. Segment data: {str(segment)[:200]}. Skipping.")
        return []

    logger.info(f"Successfully generated {len(gcode_commands)} G-code lines for spiral segment.")
    return gcode_commands