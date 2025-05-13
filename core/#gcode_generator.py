import json
import math
from typing import List, Dict, Tuple, Union

# GCode Parameters (defaults - these should be configurable)
DEFAULT_FEEDRATE = 1500  # Movement speed in mm/min
DEFAULT_EXTRUSION_RATE = 0.05  # Default extrusion per mm
DEFAULT_RESOLUTION = 50 # Default points per curve

def parse_json_input(json_input: Union[str, dict]) -> dict:
    """
    Parses the JSON input, whether it's a string or a dictionary.

    Args:
        json_input: The JSON input, which can be a string or a dictionary.

    Returns:
        A dictionary representing the JSON data.

    Raises:
        json.JSONDecodeError: If the input is a string and not valid JSON.
    """
    if isinstance(json_input, str):
        try:
            return json.loads(json_input)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    elif isinstance(json_input, dict):
        return json_input
    else:
        raise TypeError("Input must be a JSON string or a dictionary.")

def generate_gcode_segment(segment: dict) -> List[str]:
    """
    Generates GCode commands for a single path segment.  This function
    handles the different segment types (line, arc, bezier) and applies
    modifiers and constraints.

    Args:
        segment: A dictionary representing the path segment.

    Returns:
        A list of GCode commands for the segment.
    """
    gcode_commands = []
    segment_type = segment.get("type")

    if segment_type == "line":
        gcode_commands.extend(generate_gcode_line(segment))
    elif segment_type == "arc":
        gcode_commands.extend(generate_gcode_arc(segment))
    elif segment_type == "bezier":
        gcode_commands.extend(generate_gcode_bezier(segment))
    elif segment_type == "spiral":
        gcode_commands.extend(generate_gcode_spiral(segment))  # added spiral
    elif segment_type == "style": #added style
        gcode_commands.extend(generate_gcode_style(segment))
    elif segment_type == "repeat": #added repeat
        gcode_commands.extend(generate_gcode_repeat(segment))
    elif segment_type == "structure": #added structure
        gcode_commands.extend(generate_gcode_structure(segment))
    else:
        raise ValueError(f"Unsupported segment type: {segment_type}")

    # Apply modifiers (e.g., offset, smooth)
    modifiers = segment.get("modifiers", [])
    for modifier in modifiers:
        gcode_commands = apply_modifier(gcode_commands, modifier)

    # Apply constraints (e.g., connect, tangent) -  Constraints are applied
    #  *after* modifiers.
    constraints = segment.get("constraints", [])
    for constraint in constraints:
        gcode_commands = apply_constraint(gcode_commands, constraint, segment)

    return gcode_commands



def generate_gcode_line(segment: dict) -> List[str]:
    """Generates GCode for a line segment."""
    start = segment.get("start", [0, 0, 0])
    end = segment.get("end", [0, 0, 0])
    return [f"G1 X{end[0]} Y{end[1]} Z{end[2]} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"]



def generate_gcode_arc(segment: dict) -> List[str]:
    """Generates GCode for an arc segment."""
    center = segment.get("center", [0, 0, 0])
    radius = segment.get("radius", 0)
    start_angle = math.radians(segment.get("start_angle", 0))
    end_angle = math.radians(segment.get("end_angle", 0))
    clockwise = segment.get("clockwise", True)

    # Use G2 (clockwise) or G3 (counterclockwise) arc motion
    arc_command = "G2" if clockwise else "G3"
    # Calculate end point of the arc
    end_x = center[0] + radius * math.cos(end_angle)
    end_y = center[1] + radius * math.sin(end_angle)
    return [f"{arc_command} X{end_x:.3f} Y{end_y:.3f} I{center[0] - center[0]:.3f} J{center[1] - center[1]:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"]



def generate_gcode_bezier(segment: dict) -> List[str]:
    """Generates GCode for a Bézier curve segment (quadratic approximation)."""
    control_points = segment.get("control_points", [])
    num_points = segment.get("num_points", DEFAULT_RESOLUTION)
    gcode_commands = []

    if len(control_points) != 3:
        raise ValueError("Bezier curve requires exactly three control points.")

    # Approximate Bézier curve using linear interpolation between control points
    for i in range(num_points):
        t = i / (num_points - 1)
        x = (1 - t) ** 2 * control_points[0][0] + 2 * (1 - t) * t * control_points[1][0] + t ** 2 * control_points[2][0]
        y = (1 - t) ** 2 * control_points[0][1] + 2 * (1 - t) * t * control_points[1][1] + t ** 2 * control_points[2][1]
        z = (1 - t) ** 2 * control_points[0][2] + 2 * (1 - t) * t * control_points[1][2] + t ** 2 * control_points[2][2]
        gcode_commands.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}")
    return gcode_commands

def generate_gcode_spiral(segment:dict) -> List[str]:
    """Generates gcode for a spiral"""
    center_x = segment.get("center", [0,0,0])[0]
    center_y = segment.get("center", [0,0,0])[1]
    center_z = segment.get("center", [0,0,0])[2]
    inner_radius = segment.get("inner_radius", 0)
    outer_radius = segment.get("outer_radius", 10)
    turns = segment.get("turns", 10)
    pitch = segment.get("pitch", 1)
    num_points = segment.get("num_points", DEFAULT_RESOLUTION)

    gcode_commands = []
    for i in range(num_points):
        t = i / (num_points - 1)
        angle = t * turns * 2 * math.pi
        radius = inner_radius + (outer_radius - inner_radius) * t
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        z = center_z + pitch * t
        gcode_commands.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}")
    return gcode_commands

def generate_gcode_style(segment:dict) -> List[str]:
    """This will generate GCode based on higher level style descriptors"""
    style_type = segment.get("style_type")
    sub_segments = segment.get("sub_segments", [])
    gcode_commands = []

    if style_type == "organic":
        for sub_segment in sub_segments:
            if sub_segment["type"] == "spiral":
                gcode_commands.extend(generate_gcode_spiral(sub_segment))
    elif style_type == "geometric":
        for sub_segment in sub_segments:
            if sub_segment["type"] == "line":
                gcode_commands.extend(generate_gcode_line(sub_segment))
    else:
        raise ValueError(f"Unsupported style type: {style_type}")
    return gcode_commands

def generate_gcode_repeat(segment:dict) -> List[str]:
    """Generates GCode by repeating a segment"""
    count = segment.get("count", 1)
    repeated_segment = segment.get("segment")
    transform = segment.get("transform", {})

    gcode_commands = []
    for _ in range(count):
        segment_gcode = generate_gcode_segment(repeated_segment)
        # Apply transformation
        transformed_gcode = apply_transformation(segment_gcode, transform)
        gcode_commands.extend(transformed_gcode)
    return gcode_commands

def generate_gcode_structure(segment:dict) ->List[str]:
    """Generates GCode for a structural pattern"""
    structure_type = segment.get("structure_type")
    base_segment = segment.get("base_segment")
    density = segment.get("density", 1)

    gcode_commands = []
    if structure_type == "lattice":
        #implementation
        pass
    elif structure_type == "honeycomb":
        #implementation
        pass
    else:
        raise ValueError(f"Unsupported structure type: {structure_type}")
    return gcode_commands

import json
import math
from typing import List, Dict, Tuple, Union

# GCode Parameters (defaults - these should be configurable)
DEFAULT_FEEDRATE = 1500  # Movement speed in mm/min
DEFAULT_EXTRUSION_RATE = 0.05  # Default extrusion per mm
DEFAULT_RESOLUTION = 50  # Default points per curve
DEFAULT_SMOOTHING_LEVEL = 1 # default smoothing level
def parse_json_input(json_input: Union[str, dict]) -> dict:
    """
    Parses the JSON input, whether it's a string or a dictionary.

    Args:
        json_input: The JSON input, which can be a string or a dictionary.

    Returns:
        A dictionary representing the JSON data.

    Raises:
        json.JSONDecodeError: If the input is a string and not valid JSON.
    """
    if isinstance(json_input, str):
        try:
            return json.loads(json_input)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    elif isinstance(json_input, dict):
        return json_input
    else:
        raise TypeError("Input must be a JSON string or a dictionary.")

def generate_gcode_segment(segment: dict) -> List[str]:
    """
    Generates GCode commands for a single path segment.  This function
    handles the different segment types (line, arc, bezier) and applies
    modifiers and constraints.

    Args:
        segment: A dictionary representing the path segment.

    Returns:
        A list of GCode commands for the segment.
    """
    gcode_commands = []
    segment_type = segment.get("type")

    if segment_type == "line":
        gcode_commands.extend(generate_gcode_line(segment))
    elif segment_type == "arc":
        gcode_commands.extend(generate_gcode_arc(segment))
    elif segment_type == "bezier":
        gcode_commands.extend(generate_gcode_bezier(segment))
    elif segment_type == "spiral":
        gcode_commands.extend(generate_gcode_spiral(segment))  # added spiral
    elif segment_type == "style":  # added style
        gcode_commands.extend(generate_gcode_style(segment))
    elif segment_type == "repeat":  # added repeat
        gcode_commands.extend(generate_gcode_repeat(segment))
    elif segment_type == "structure":  # added structure
        gcode_commands.extend(generate_gcode_structure(segment))
    else:
        raise ValueError(f"Unsupported segment type: {segment_type}")

    # Apply modifiers (e.g., offset, smooth)
    modifiers = segment.get("modifiers", [])
    for modifier in modifiers:
        gcode_commands = apply_modifier(gcode_commands, modifier, segment) # Pass segment

    # Apply constraints (e.g., connect, tangent) -  Constraints are applied
    #  *after* modifiers.
    constraints = segment.get("constraints", [])
    for constraint in constraints:
        gcode_commands = apply_constraint(gcode_commands, constraint, segment)

    return gcode_commands


def generate_gcode_line(segment: dict) -> List[str]:
    """Generates GCode for a line segment."""
    start = segment.get("start", [0, 0, 0])
    end = segment.get("end", [0, 0, 0])
    return [f"G1 X{end[0]:.3f} Y{end[1]:.3f} Z{end[2]:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"]



def generate_gcode_arc(segment: dict) -> List[str]:
    """Generates GCode for an arc segment."""
    center = segment.get("center", [0, 0, 0])
    radius = segment.get("radius", 0)
    start_angle = math.radians(segment.get("start_angle", 0))
    end_angle = math.radians(segment.get("end_angle", 0))
    clockwise = segment.get("clockwise", True)

    # Use G2 (clockwise) or G3 (counterclockwise) arc motion
    arc_command = "G2" if clockwise else "G3"
    # Calculate end point of the arc
    end_x = center[0] + radius * math.cos(end_angle)
    end_y = center[1] + radius * math.sin(end_angle)
    return [f"{arc_command} X{end_x:.3f} Y{end_y:.3f} I{center[0] - center[0]:.3f} J{center[1] - center[1]:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"]



def generate_gcode_bezier(segment: dict) -> List[str]:
    """Generates GCode for a Bézier curve segment (quadratic approximation)."""
    control_points = segment.get("control_points", [])
    num_points = segment.get("num_points", DEFAULT_RESOLUTION)
    gcode_commands = []

    if len(control_points) != 3:
        raise ValueError("Bezier curve requires exactly three control points.")

    # Approximate Bézier curve using linear interpolation between control points
    for i in range(num_points):
        t = i / (num_points - 1)
        x = (1 - t) ** 2 * control_points[0][0] + 2 * (1 - t) * t * control_points[1][0] + t ** 2 * control_points[2][0]
        y = (1 - t) ** 2 * control_points[0][1] + 2 * (1 - t) * t * control_points[1][1] + t ** 2 * control_points[2][1]
        z = (1 - t) ** 2 * control_points[0][2] + 2 * (1 - t) * t * control_points[1][2] + t ** 2 * control_points[2][2]
        gcode_commands.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}")
    return gcode_commands

def generate_gcode_spiral(segment: dict) -> List[str]:
    """Generates gcode for a spiral"""
    center_x = segment.get("center", [0, 0, 0])[0]
    center_y = segment.get("center", [0, 0, 0])[1]
    center_z = segment.get("center", [0, 0, 0])[2]
    inner_radius = segment.get("inner_radius", 0)
    outer_radius = segment.get("outer_radius", 10)
    turns = segment.get("turns", 10)
    pitch = segment.get("pitch", 1)
    num_points = segment.get("num_points", DEFAULT_RESOLUTION)

    gcode_commands = []
    for i in range(num_points):
        t = i / (num_points - 1)
        angle = t * turns * 2 * math.pi
        radius = inner_radius + (outer_radius - inner_radius) * t
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        z = center_z + pitch * t
        gcode_commands.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}")
    return gcode_commands

def generate_gcode_style(segment: dict) -> List[str]:
    """This will generate GCode based on higher level style descriptors"""
    style_type = segment.get("style_type")
    sub_segments = segment.get("sub_segments", [])
    gcode_commands = []

    if style_type == "organic":
        for sub_segment in sub_segments:
            if sub_segment["type"] == "spiral":
                gcode_commands.extend(generate_gcode_spiral(sub_segment))
    elif style_type == "geometric":
        for sub_segment in sub_segments:
            if sub_segment["type"] == "line":
                gcode_commands.extend(generate_gcode_line(sub_segment))
    else:
        raise ValueError(f"Unsupported style type: {style_type}")
    return gcode_commands

def generate_gcode_repeat(segment: dict) -> List[str]:
    """Generates GCode by repeating a segment"""
    count = segment.get("count", 1)
    repeated_segment = segment.get("segment")
    transform = segment.get("transform", {})

    gcode_commands = []
    for _ in range(count):
        segment_gcode = generate_gcode_segment(repeated_segment)
        # Apply transformation
        transformed_gcode = apply_transformation(segment_gcode, transform)
        gcode_commands.extend(transformed_gcode)
    return gcode_commands

def generate_gcode_structure(segment: dict) -> List[str]:
    """Generates GCode for a structural pattern"""
    structure_type = segment.get("structure_type")
    base_segment = segment.get("base_segment")
    density = segment.get("density", 1)

    gcode_commands = []
    if structure_type == "lattice":
        # implementation
        gcode_commands.extend(generate_gcode_lattice(base_segment, density))
    elif structure_type == "honeycomb":
        # implementation
        gcode_commands.extend(generate_gcode_honeycomb(base_segment, density))
    else:
        raise ValueError(f"Unsupported structure type: {structure_type}")
    return gcode_commands

def generate_gcode_lattice(base_segment:dict, density:float) -> List[str]:
    """Generates gcode for lattice structure"""
    # Placeholder
    return [f"G1 X0 Y0 Z0 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}",
            f"G1 X10 Y10 Z10 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"]

def generate_gcode_honeycomb(base_segment:dict, density:float) -> List[str]:
    """Generates gcode for honeycomb structure"""
    # Placeholder
    return [f"G1 X0 Y0 Z0 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}",
            f"G1 X10 Y10 Z10 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"]

def apply_transformation(gcode_commands: List[str], transform: dict) -> List[str]:
    """Applies a transformation (e.g., rotation, offset) to a list of GCode commands."""
    transformed_commands = []
    for command in gcode_commands:
        parts = command.split()
        x, y, z = None, None, None
        for part in parts:
            if part.startswith("X"):
                x = float(part[1:])
            elif part.startswith("Y"):
                y = float(part[1:])
            elif part.startswith("Z"):
                z = float(part[1:])
        if x is not None and y is not None and z is not None:
            if "rotate" in transform:
                axis = transform["rotate"]
                angle = math.radians(transform["rotate"][1])
                if axis == "z":
                    new_x = x * math.cos(angle) - y * math.sin(angle)
                    new_y = x * math.sin(angle) + y * math.cos(angle)
                    x = new_x
                    y = new_y
                elif axis == "x":
                    new_y = y * math.cos(angle) - z * math.sin(angle)
                    new_z = y * math.sin(angle) + z * math.cos(angle)
                    y = new_y
                    z = new_z
                elif axis == "y":
                    new_x = x * math.cos(angle) + z * math.sin(angle)
                    new_z = -x * math.sin(angle) + z * math.cos(angle)
                    x = new_x
                    z = new_z

            elif "scale" in transform:
                scale_x = transform["scale"][0]
                scale_y = transform["scale"][1]
                scale_z = transform["scale"][2]
                x *= scale_x
                y *= scale_y
                z *= scale_z
            elif "offset" in transform:
                offset_x = transform["offset"][0]
                offset_y = transform["offset"][1]
                offset_z = transform["offset"][2]
                x += offset_x
                y += offset_y
                z += offset_z
        transformed_commands.append(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}")
    else:
        transformed_commands.append(command)
    return transformed_commands


def apply_modifier(gcode_commands: List[str], modifier: dict, segment:dict) -> List[str]:
    """Applies a modifier to the GCode commands (e.g., offset, smoothing)."""
    if modifier["type"] == "offset":
        distance = modifier["distance"]
        return apply_offset(gcode_commands, distance, segment)
    elif modifier["type"] == "smooth":
        level = modifier["level"]
        return apply_smoothing(gcode_commands, level, segment)
    return gcode_commands #returns the original, the implementation will modify

def apply_offset(gcode_commands:List[str], distance:float, segment:dict) -> List[str]:
    """Applies an offset to the path"""
    # Placeholder
    return gcode_commands

def apply_smoothing(gcode_commands:List[str], level:int, segment:dict) -> List[str]:
    """Applies smoothing to the path"""
    # Placeholder
    return gcode_commands

def apply_constraint(gcode_commands: List[str], constraint: dict, segment:dict) -> List[str]:
    """Applies a constraint to the GCode commands (e.g., connect, tangent)."""
    if constraint["type"] == "connect" and constraint.get("previous_segment", False):
        # Get the end point of the previous segment and modify the start point of the first command
        pass # To be implemented
    elif constraint["type"] == "tangent":
        direction = constraint["direction"]
        # apply the tangent
        pass # To be implemented
    return gcode_commands



def generate_gcode_from_json(json_input: Union[str, dict]) -> List[str]:
    """
    Converts JSON-based path descriptors into modular GCode sequences.

    Parameters:
        json_input: JSON string or dictionary containing path descriptors.

    Returns:
        A list of formatted GCode commands.
    """
    json_data = parse_json_input(json_input)
    gcode_output = ["G21 ; Set units to millimeters", "G90 ; Absolute positioning"]

    for segment in json_data.get("path", {}).get("segments", []):
        gcode_commands = generate_gcode_segment(segment)
        gcode_output.extend(gcode_commands)

    # Apply modifiers and constraints to the entire path.
    modifiers = json_data.get("path", {}).get("modifiers", [])
    for modifier in modifiers:
        gcode_output = apply_modifier(gcode_output, modifier, json_data.get("path", {}))

    constraints = json_data.get("path", {}).get("constraints", [])
    for constraint in constraints:
        gcode_output = apply_constraint(gcode_output, constraint, json_data.get("path", {}))

    gcode_output.append("M2 ; End of program")
    return gcode_output



def optimize_gcode(gcode_commands: List[str], material_properties: dict, printer_capabilities: dict) -> List[str]:
    """
    Optimizes GCode commands for printing, including extrusion rate, speed,
    and acceleration, using AI.

    Args:
        gcode_commands: A list of GCode commands.
        material_properties: A dictionary containing the properties of the
            printing material (e.g., viscosity, glass transition temperature).
        printer_capabilities: A dictionary containing the capabilities of the
            3D printer (e.g., max acceleration, jerk).

    Returns:
        A list of optimized GCode commands.
    """
    # Placeholder:  This is where the main AI logic will go.
    # 1.  Parse GCode commands.
    # 2.  Analyze path geometry.
    # 3.  Use AI (e.g., a trained neural network) to predict optimal
    #      parameters.
    # 4.  Generate new GCode commands with the optimized parameters.
    # 5.  Return the optimized GCode.

    optimized_gcode = []
    for command in gcode_commands:
        parts = command.split()
        if parts[0].startswith("G1"):
             # Example of modifying feedrate
             optimized_gcode.append(f"{parts[0]} X{parts[1]} Y{parts[2]} Z{parts[3]} F{DEFAULT_FEEDRATE * 1.2} E{parts[5]}")  # Increase Feedrate by 20%
        else:
             optimized_gcode.append(command)
    return optimized_gcode
    # return gcode_commands  # Placeholder: Return original for now.


# Example JSON input
json_example = {
    "path": {
        "segments": [
            {"type": "line", "start": [0, 0, 0], "end": [100, 0, 0]},
            {"type": "arc", "center": [100, 50, 0], "radius": 50, "start_angle": 0, "end_angle": 90, "clockwise": True},
            {"type": "bezier", "control_points": [[150, 50, 0], [200, 100, 50], [250, 50, 0]], "num_points": 20},
            {"type": "spiral", "center": [0, 0, 0], "inner_radius": 10, "outer_radius": 50, "turns": 5, "pitch": 2},
            {"type": "style", "style_type": "organic", "sub_segments": [{"type": "spiral", "center": [0, 0, 0], "inner_radius": 10, "outer_radius": 50, "turns": 5, "pitch": 2}]},
            {"type": "repeat", "count": 3, "transform": {"rotate": ["z", 120]}, "segment": {"type": "line", "start": [0, 0, 0], "end": [50, 0, 0]}},
            {"type": "structure", "structure_type": "lattice", "density": 0.6, "base_segment": {"type": "line", "start": [0, 0, 0], "end": [10, 10, 10]}}
        ],
        "modifiers": [
            {"type": "offset", "distance": 5},
            {"type": "smooth", "level": 2}
        ],
        "constraints": [
            {"type": "connect", "previous_segment": True},
            {"type": "tangent", "direction": [1, 0, 0]}
        ]
    }
}

# Example material properties (these would come from a database or user input)
material_properties = {
    "name": "PLA",
    "density": 1.24,  # g/cm^3
    "viscosity": 100,  # Pa*s (example value)
    "thermal_conductivity": 0.13,  # W/mK
    "glass_transition_temp": 60,  # C
    "max_flow_rate": 10,  # mm^3/s (example)
}

# Example printer capabilities (these would come from printer configuration)
printer_capabilities = {
    "max_acceleration": 500,  # mm/s^2
    "max_jerk": 10,  # mm/s^3
    "max_speed_x": 200,  # mm/s
    "max_speed_y": 200,
    "max_speed_z": 50,
    "max_ext_speed": 50, #mm/s
    "nozzle_diameter": 0.4,  # mm
}

# Generate GCode
gcode_result = generate_gcode_from_json(json_example)
print("Raw GCode:\n", "\n".join(gcode_result))

# Optimize GCode
optimized_gcode = optimize_gcode(gcode_result, material_properties, printer_capabilities)
print("\nOptimized GCode:\n", "\n".join(optimized_gcode))
