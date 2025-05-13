# modules/ai_pathing.py
# This module contains functions related to AI-driven path generation,
# modifications, and constraint applications for G-code.

#Imports
from typing import List, Dict
import numpy as np
from core.constants import DEFAULT_EXTRUSION_RATE, DEFAULT_FEEDRATE, DEFAULT_SMOOTHING_LEVEL

# 1. Generate G-code for Lattice Structure
def generate_gcode_lattice(base_segment: dict, density: float) -> List[str]:
    """Generates G-code for a lattice structure (placeholder)."""
    return [
        f"G1 X0 Y0 Z0 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}",
        f"G1 X10 Y10 Z10 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
    ]


# 2. Generate G-code for Honeycomb Structure
def generate_gcode_honeycomb(base_segment: dict, density: float) -> List[str]:
    """Generates G-code for a honeycomb structure (placeholder)."""
    return [
        f"G1 X0 Y0 Z0 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}",
        f"G1 X10 Y10 Z10 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
    ]


# 3. Apply Modifier to G-code
def apply_modifier(gcode, modifier, segment):
    """
    Apply a modifier to the generated G-code.
    Currently supports 'offset' and 'smooth' modifiers, but more can be added as needed.
    """
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
            print(f"Warning: Unrecognized modifier type: {modifier.get('type')}")
    else:
        print(f"Error: Modifier is not a dictionary: {modifier}")
    
    return gcode


# 4. Apply Offset to Path
def apply_offset(gcode_commands: List[str], distance: float, segment: dict) -> List[str]:
    """Applies an offset to the path based on normal vectors."""
    points = []
    # Extract X, Y, Z coordinates from G-code commands
    for command in gcode_commands:
        x = y = z = None
        for part in command.split():
            if part.startswith("X"):
                x = float(part[1:])
            elif part.startswith("Y"):
                y = float(part[1:])
            elif part.startswith("Z"):
                z = float(part[1:])
        if x is not None and y is not None and z is not None:
            points.append((x, y, z))

    if not points:
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
        offset_points.append((ox, oy, p2[2]))

    return [
        f"G1 X{ox:.3f} Y{oy:.3f} Z{oz:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        for ox, oy, oz in offset_points
    ]


# 5. Apply Smoothing to Path
def apply_smoothing(gcode_commands: List[str], level: int, segment: dict) -> List[str]:
    """Applies smoothing to the G-code path using weighted averaging."""
    if level <= 0:
        return gcode_commands

    points = []
    # Extract X, Y, Z coordinates from G-code commands
    for command in gcode_commands:
        x = y = z = None
        for part in command.split():
            if part.startswith("X"):
                x = float(part[1:])
            elif part.startswith("Y"):
                y = float(part[1:])
            elif part.startswith("Z"):
                z = float(part[1:])
        if x is not None and y is not None and z is not None:
            points.append((x, y, z))

    if not points:
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

    return [
        f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        for x, y, z in points
    ]


# 6. Apply Constraint to G-code
def apply_constraint(gcode_commands: List[str], constraint: dict, segment: dict) -> List[str]:
    """Applies constraints such as connection or tangents between segments."""
    if constraint["type"] == "connect" and constraint.get("previous_segment", False):
        previous_end = segment.get("previous_end_point")
        if previous_end and gcode_commands:
            # Modify the first command of the current segment to start from the previous segment's end point.
            x, y, z = previous_end
            gcode_commands[0] = (
                f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
            )
    elif constraint["type"] == "tangent":
        # Tangent constraint placeholder
        direction = constraint.get("direction")
        # Not yet implemented
        pass
    return gcode_commands 
