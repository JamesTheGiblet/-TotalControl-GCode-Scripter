# core/transform.py
# This module provides transformation operations for G-code commands.

import math
from typing import List

# 1. Apply Transformation to G-code Commands
def apply_transformation(gcode_commands: List[str], transform_params: dict, iteration: int = 0, total_iterations: int = 1, base_offset: List[float] = None) -> List[str]:
    """
    Applies transformations (rotate, scale, offset) to G-code commands.
    `base_offset` can be used for cumulative offsets in repeat scenarios.
    `iteration` and `total_iterations` can be used for dynamic transformations.
    """
    if base_offset is None:
        base_offset = [0.0, 0.0, 0.0]

    transformed_commands = []

    # Extract transformation details
    rotation_details = transform_params.get("rotate") # e.g., ["z", 120]
    scale_details = transform_params.get("scale")     # e.g., [1, 1, 1] or a single float for uniform
    offset_details = transform_params.get("offset")   # e.g., [dx, dy, dz]

    for command_index, command in enumerate(gcode_commands):
        # Only transform G0, G1, G2, G3 commands with coordinates
        if not (command.startswith("G0") or command.startswith("G1") or \
                command.startswith("G2") or command.startswith("G3")):
            transformed_commands.append(command)
            continue

        parts = command.split()
        cmd_type = parts[0]
        new_parts = [cmd_type]
        
        coords = {'X': None, 'Y': None, 'Z': None, 'I': None, 'J': None, 'K': None}
        other_params = []

        for part in parts[1:]:
            found_coord = False
            for axis in coords.keys():
                if part.startswith(axis):
                    try:
                        coords[axis] = float(part[len(axis):])
                        found_coord = True
                        break
                    except ValueError: # Handle cases like "G1 X" without a number (should not happen in valid G-code)
                        print(f"Warning: Malformed coordinate '{part}' in command '{command}'")
                        other_params.append(part) # Keep it as is
                        found_coord = True
                        break
            if not found_coord:
                other_params.append(part)
        
        # Apply base offset first (e.g. for repeated items that are stacked)
        if coords['X'] is not None: coords['X'] += base_offset[0]
        if coords['Y'] is not None: coords['Y'] += base_offset[1]
        if coords['Z'] is not None: coords['Z'] += base_offset[2]
        # I, J, K are relative offsets for arcs, they also need to be transformed if the arc center moves with base_offset
        # However, G2/G3 IJK are relative to the *start point* of the arc.
        # If the start point is moved by base_offset, and the center is also moved by base_offset,
        # then IJK (center - start) remain unchanged by a pure translation (base_offset).
        # Rotation and scaling of IJK vectors are more complex.

        # Current point (X,Y,Z)
        point = [coords['X'], coords['Y'], coords['Z']]
        # Arc center relative offsets (I,J,K) - treat as vectors if present
        ijk_vector = [coords['I'], coords['J'], coords['K']] if cmd_type in ["G2", "G3"] else None

        # 1. Scaling (around origin [0,0,0] or a defined pivot)
        # Assuming scaling is around the local origin of the segment before any offsets.
        if scale_details:
            sx, sy, sz = 1, 1, 1
            if isinstance(scale_details, list) and len(scale_details) == 3:
                sx, sy, sz = scale_details[0], scale_details[1], scale_details[2]
            elif isinstance(scale_details, (int, float)):
                sx = sy = sz = float(scale_details)
            
            if point[0] is not None: point[0] *= sx
            if point[1] is not None: point[1] *= sy
            if point[2] is not None: point[2] *= sz
            if ijk_vector: # Scale IJK vectors
                if ijk_vector[0] is not None: ijk_vector[0] *= sx
                if ijk_vector[1] is not None: ijk_vector[1] *= sy
                if ijk_vector[2] is not None: ijk_vector[2] *= sz # K for 3D arcs

        # 2. Rotation (around origin [0,0,0] or a defined pivot)
        # Assuming rotation is around the local origin of the segment.
        if rotation_details and all(c is not None for c in point): # Need X,Y,Z for rotation
            axis_char, angle_deg = rotation_details[0], float(rotation_details[1])
            angle_rad = math.radians(angle_deg)
            
            x, y, z = point[0], point[1], point[2]
            if axis_char.lower() == 'x':
                y_new = y * math.cos(angle_rad) - z * math.sin(angle_rad)
                z_new = y * math.sin(angle_rad) + z * math.cos(angle_rad)
                point[1], point[2] = y_new, z_new
                if ijk_vector and ijk_vector[1] is not None and ijk_vector[2] is not None:
                    iy, iz = ijk_vector[1], ijk_vector[2]
                    ijk_vector[1] = iy * math.cos(angle_rad) - iz * math.sin(angle_rad)
                    ijk_vector[2] = iy * math.sin(angle_rad) + iz * math.cos(angle_rad)
            elif axis_char.lower() == 'y':
                x_new = x * math.cos(angle_rad) + z * math.sin(angle_rad)
                z_new = -x * math.sin(angle_rad) + z * math.cos(angle_rad)
                point[0], point[2] = x_new, z_new
                if ijk_vector and ijk_vector[0] is not None and ijk_vector[2] is not None:
                    ix, iz = ijk_vector[0], ijk_vector[2]
                    ijk_vector[0] = ix * math.cos(angle_rad) + iz * math.sin(angle_rad)
                    ijk_vector[2] = -ix * math.sin(angle_rad) + iz * math.cos(angle_rad)
            elif axis_char.lower() == 'z':
                x_new = x * math.cos(angle_rad) - y * math.sin(angle_rad)
                y_new = x * math.sin(angle_rad) + y * math.cos(angle_rad)
                point[0], point[1] = x_new, y_new
                if ijk_vector and ijk_vector[0] is not None and ijk_vector[1] is not None:
                    ix, iy = ijk_vector[0], ijk_vector[1]
                    ijk_vector[0] = ix * math.cos(angle_rad) - iy * math.sin(angle_rad)
                    ijk_vector[1] = ix * math.sin(angle_rad) + iy * math.cos(angle_rad)

        # 3. Offset (applied after scaling and rotation)
        if offset_details:
            dx, dy, dz = offset_details[0], offset_details[1], offset_details[2]
            if point[0] is not None: point[0] += dx
            if point[1] is not None: point[1] += dy
            if point[2] is not None: point[2] += dz

        # Reconstruct the coordinate part of the command
        if point[0] is not None: new_parts.append(f"X{point[0]:.3f}")
        if point[1] is not None: new_parts.append(f"Y{point[1]:.3f}")
        if point[2] is not None: new_parts.append(f"Z{point[2]:.3f}")
        
        if ijk_vector:
            if ijk_vector[0] is not None: new_parts.append(f"I{ijk_vector[0]:.3f}")
            if ijk_vector[1] is not None: new_parts.append(f"J{ijk_vector[1]:.3f}")
            if ijk_vector[2] is not None: new_parts.append(f"K{ijk_vector[2]:.3f}")

        new_parts.extend(other_params)
        transformed_commands.append(" ".join(new_parts))

    return transformed_commands