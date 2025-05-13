# core/input_handler.py
# This module is responsible for handling various input descriptors (like Bézier, Voronoi)
# and converting them into initial G-code representations.

#Imports
from typing import List, Dict, Any

# 1. Function to generate GCode from Bézier curve descriptors
def generate_bezier_gcode(control_points: List[tuple]) -> List[str]:
    """
    Generates G-code for a Bézier curve by creating G1 commands for each control point.
    Note: This is a simplified representation; a true Bézier curve generation
    would involve interpolating points along the curve.

    Args:
        control_points: A list of tuples, where each tuple represents (X, Y, Z)
                        coordinates of a control point.

    Raises:
        TypeError: If control_points is not a list or its elements are not tuples.
        ValueError: If any control point does not have exactly 3 coordinates.

    Returns:
        A list of G-code command strings.
    """
    # Check if control_points is a list
    if not isinstance(control_points, list):
        raise TypeError("Bézier control_points must be a list.")

    # Start with a comment indicating the type and number of control points
    gcode = [f"; Bézier Curve with {len(control_points)} control points"]
    # Iterate through each control point
    for i, point in enumerate(control_points):
        # Validate that each point is a tuple and has 3 coordinates
        if not isinstance(point, tuple):
            raise TypeError(f"Control point at index {i} must be a tuple, got {type(point).__name__}.")
        if len(point) != 3:
            raise ValueError(
                f"Control point at index {i} must have 3 coordinates (X, Y, Z), got {len(point)}."
            )
        # Append a G1 command for the current control point
        gcode.append(f"G1 X{point[0]} Y{point[1]} Z{point[2]} F1500")
    return gcode

# 2. Function to generate GCode from Voronoi path descriptors
def generate_voronoi_gcode(points: List[tuple]) -> List[str]:
    """
    Generates G-code for a Voronoi path by creating G1 commands for each point.
    Note: This is a simplified representation; true Voronoi generation is more complex.

    Args:
        points: A list of tuples, where each tuple represents (X, Y, Z)
                coordinates of a point in the Voronoi path.

    Raises:
        TypeError: If points is not a list or its elements are not tuples.
        ValueError: If any point does not have exactly 3 coordinates.

    Returns:
        A list of G-code command strings.
    """
    # Check if points is a list
    if not isinstance(points, list):
        raise TypeError("Voronoi points must be a list.")

    # Start with a comment indicating the type and number of points
    gcode = [f"; Voronoi Path with {len(points)} points"]
    # Iterate through each point
    for i, point in enumerate(points):
        # Validate that each point is a tuple and has 3 coordinates
        if not isinstance(point, tuple):
            raise TypeError(f"Voronoi point at index {i} must be a tuple, got {type(point).__name__}.")
        if len(point) != 3:
            raise ValueError(
                f"Voronoi point at index {i} must have 3 coordinates (X, Y, Z), got {len(point)}."
            )
        # Append a G1 command for the current point
        gcode.append(f"G1 X{point[0]} Y{point[1]} Z{point[2]} F1500")
    return gcode

# 3. Main function to handle different input descriptors and generate GCode
def generate_gcode_from_input(descriptor: Dict[str, Any]) -> List[str]:
    """
    Handles different input descriptors (e.g., for Bézier curves, Voronoi paths)
    and dispatches to the appropriate G-code generation function.

    Args:
        descriptor: A dictionary containing the type of shape and its specific
                    parameters (e.g., "control_points" for Bézier).
                    Expected keys: "type", and then type-specific keys like
                    "control_points" or "points".

    Raises:
        TypeError: If the descriptor is not a dictionary.
        KeyError: If the required "type" key or type-specific keys
                  (e.g., "control_points") are missing from the descriptor.

    Returns:
        A list of G-code command strings.
    """
    # Ensure the input descriptor is a dictionary
    if not isinstance(descriptor, dict):
        raise TypeError(f"Input descriptor must be a dictionary, got {type(descriptor).__name__}.")

    # Ensure the 'type' key exists in the descriptor
    if "type" not in descriptor:
        raise KeyError("Input descriptor is missing the required 'type' key.")

    gcode = []
    # Get the shape type from the descriptor
    shape_type = descriptor["type"]
    
    # Dispatch to the appropriate generator based on shape_type
    if shape_type == "bezier":
        # Check for required 'control_points' key for Bézier type
        if "control_points" not in descriptor:
            raise KeyError("Bézier descriptor is missing 'control_points'.")
        gcode = generate_bezier_gcode(descriptor["control_points"])
    elif shape_type == "voronoi":
        # Check for required 'points' key for Voronoi type
        if "points" not in descriptor:
            raise KeyError("Voronoi descriptor is missing 'points'.")
        gcode = generate_voronoi_gcode(descriptor["points"])
    else:
        # If the shape type is unknown, add a comment indicating this
        gcode.append(f"; Unknown shape type: {shape_type}")
    
    return gcode
