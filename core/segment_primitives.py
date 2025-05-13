# core/segment_primitives.py
# This module contains functions to generate G-code for primitive path segments
# like lines, arcs, Bezier curves, and spirals.

import math
from typing import List, Dict
from core.constants import DEFAULT_FEEDRATE, DEFAULT_EXTRUSION_RATE, DEFAULT_RESOLUTION

# 1. Generate G-code for Line Segment
def generate_gcode_line(segment: dict) -> List[str]:
    """Generates G-code for a line segment."""
    # start = segment.get("start", [0, 0, 0]) # Start is often implicit
    end = segment.get("end", [0, 0, 0])
    return [f"G1 X{end[0]:.3f} Y{end[1]:.3f} Z{end[2]:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"]

# 2. Generate G-code for Arc Segment
def generate_gcode_arc(segment: dict) -> List[str]:
    """Generates G-code for an arc segment using I, J, K or R format."""
    center = segment.get("center", [0, 0, 0])
    radius = segment.get("radius", 0)
    start_angle = math.radians(segment.get("start_angle", 0))
    end_angle = math.radians(segment.get("end_angle", 0))
    clockwise = segment.get("clockwise", True)
    arc_command = "G2" if clockwise else "G3"

    end_x = center[0] + radius * math.cos(end_angle)
    end_y = center[1] + radius * math.sin(end_angle)
    z_coord = center[2] # Assuming arc is planar in XY and Z is constant from center

    start_x = center[0] + radius * math.cos(start_angle)
    start_y = center[1] + radius * math.sin(start_angle)

    i_offset = center[0] - start_x
    j_offset = center[1] - start_y
    # K_offset would be center[2] - start_z if doing 3D arcs, but G2/G3 with IJK is typically planar.

    return [f"{arc_command} X{end_x:.3f} Y{end_y:.3f} Z{z_coord:.3f} I{i_offset:.3f} J{j_offset:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"]

# 3. Generate G-code for Bezier Curve Segment
def generate_gcode_bezier(segment: dict) -> List[str]:
    """Generates G-code for a Bézier curve segment by linear approximation."""
    control_points = segment.get("control_points", [])
    num_points = segment.get("num_points", DEFAULT_RESOLUTION)
    gcode_commands = []

    if len(control_points) < 2:
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
        raise ValueError("Bezier curve implementation currently supports 3 or 4 control points.")
    return gcode_commands

# 4. Generate G-code for Spiral Segment
def generate_gcode_spiral(segment: dict) -> List[str]:
    """Generates G-code for a spiral segment."""
    center = segment.get("center", [0, 0, 0])
    inner_radius = segment.get("inner_radius", 0)
    outer_radius = segment.get("outer_radius", 10)
    turns = segment.get("turns", 10)
    pitch = segment.get("pitch", 1) # Z change per turn
    num_points = segment.get("num_points", DEFAULT_RESOLUTION)
    gcode_commands = []
    total_angle = turns * 2 * math.pi

    for i in range(num_points + 1):
        t = i / num_points
        current_angle = t * total_angle
        current_radius = inner_radius + (outer_radius - inner_radius) * t
        x = center[0] + current_radius * math.cos(current_angle)
        y = center[1] + current_radius * math.sin(current_angle)
        current_z_offset = t * turns * pitch
        z = center[2] + current_z_offset
        gcode_commands.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}")
    return gcode_commands