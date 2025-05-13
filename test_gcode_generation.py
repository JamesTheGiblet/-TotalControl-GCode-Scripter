# test_gcode_generation.py
# This module contains unit tests for the G-code generation functionalities,
# focusing on individual segment types and transformations.

import unittest
import math

# Import necessary functions/modules
from core.gcode_generator import generate_gcode_segment, apply_transformation
from core.constants import DEFAULT_FEEDRATE, DEFAULT_EXTRUSION_RATE, DEFAULT_RESOLUTION

class TestGCodeGeneration(unittest.TestCase):

    def test_line_generation(self):
        segment = {"type": "line", "start": [0, 0, 0], "end": [10, 10, 5]}
        expected_gcode = [
            f"G1 X10.000 Y10.000 Z5.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        ]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

    def test_arc_generation(self):
        segment = {"type": "arc", "center": [5, 5, 0], "radius": 3, "start_angle": 0, "end_angle": 90, "clockwise": True}
        expected_gcode = [
            f"G2 X5.000 Y8.000 Z0.000 I-3.000 J0.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        ]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

    def test_bezier_generation(self):
        segment = {"type": "bezier", "control_points": [[0,0,0], [2,5,0], [5,5,0], [10,0,0]], "num_points": 1}
        expected_gcode = [
            f"G1 X0.000 Y0.000 Z0.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}",
            f"G1 X10.000 Y0.000 Z0.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        ]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

    def test_spiral_generation(self):
        segment = {"type": "spiral", "center": [5,5,0], "inner_radius": 1, "outer_radius": 5, "turns": 2, "pitch": 1, "num_points": 1}
        expected_gcode = [
            f"G1 X6.000 Y5.000 Z0.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}",
            f"G1 X10.000 Y5.000 Z2.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        ]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

    def test_style_generation(self):
        segment = {"type": "style", "style_type": "organic", "sub_segments": [{"type": "line", "start": [0,0,0], "end": [1,1,1]}]}
        expected_gcode = [
            f"G1 X1.000 Y1.000 Z1.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        ]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

    def test_repeat_generation(self):
        segment = {"type": "repeat", "count": 2, "segment": {"type": "line", "start": [0,0,0], "end": [5,5,0]}}
        line_gcode = f"G1 X5.000 Y5.000 Z0.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        expected_gcode = [line_gcode, line_gcode]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

    def test_structure_generation(self):
        segment = {"type": "structure", "structure_type": "lattice", "base_segment": {"type": "line", "start": [0,0,0], "end": [1,1,1]}, "density": 0.5}
        expected_gcode = [
            f"G1 X0 Y0 Z0 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}",
            f"G1 X10 Y10 Z10 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        ]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

    def test_transform_translation(self):
        segment = {"type": "line", "start": [0,0,0], "end": [10,10,0], "transform": {"offset": [5, 5, 2]}}
        expected_gcode = [
            f"G1 X15.000 Y15.000 Z2.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        ]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

    def test_transform_scaling(self):
        segment = {"type": "line", "start": [0,0,0], "end": [10,10,0], "transform": {"scale": 2}}
        expected_gcode = [
            f"G1 X20.000 Y20.000 Z0.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        ]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

    def test_transform_rotation(self):
        segment = {"type": "line", "start": [0,0,0], "end": [10,0,0], "transform": {"rotate": ["z", 90]}}
        result = generate_gcode_segment(segment)
        self.assertEqual(len(result), 1)
        self.assertTrue("X0.000" in result[0] or "X-0.000" in result[0])
        self.assertTrue("Y10.000" in result[0])
        self.assertTrue(f"Z0.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}" in result[0])

    def test_empty_segment_definition(self):
        segment = {}
        with self.assertRaisesRegex(ValueError, "Unsupported segment type: None"):
            generate_gcode_segment(segment)

    def test_unsupported_segment_type(self):
        segment = {"type": "unsupported_type"}
        with self.assertRaisesRegex(ValueError, "Unsupported segment type: unsupported_type"):
            generate_gcode_segment(segment)

    def test_edge_case_large_path(self):
        segment = {"type": "line", "start": [0,0,0], "end": [1000,1000,500]}
        expected_gcode = [
            f"G1 X1000.000 Y1000.000 Z500.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        ]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

    def test_edge_case_small_path(self):
        segment = {"type": "line", "start": [0,0,0], "end": [0.01, 0.01, 0.005]}
        expected_gcode = [
            f"G1 X0.010 Y0.010 Z0.005 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        ]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

    def test_edge_case_with_negative_coordinates(self):
        segment = {"type": "line", "start": [-10,-10,-2], "end": [-5,-5,-1]}
        expected_gcode = [
            f"G1 X-5.000 Y-5.000 Z-1.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        ]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

    def test_edge_case_zero_length_path(self):
        segment = {"type": "line", "start": [0,0,0], "end": [0,0,0]}
        expected_gcode = [
            f"G1 X0.000 Y0.000 Z0.000 F{DEFAULT_FEEDRATE} E{DEFAULT_EXTRUSION_RATE}"
        ]
        result = generate_gcode_segment(segment)
        self.assertEqual(result, expected_gcode)

if __name__ == "__main__":
    unittest.main()
