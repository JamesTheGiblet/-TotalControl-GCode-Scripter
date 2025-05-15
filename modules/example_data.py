# modules/example_data.py
# This file contains example data structures used for demonstrating
# the G-code generation and optimization pipeline.

# Example JSON input for G-code generation
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

# Example material properties
material_properties = {
    "name": "PLA",
    "density": 1.24,
    "viscosity": 100,
    "thermal_conductivity": 0.13,
    "glass_transition_temp": 60,
    "max_flow_rate": 10,
}

# Example printer capabilities
printer_capabilities = {
    "max_acceleration": 500,
    "max_jerk": 10,
    "max_speed_x": 200,
    "max_speed_y": 200,
    "max_speed_z": 50,
    "max_ext_speed": 50,
    "nozzle_diameter": 0.4,
}