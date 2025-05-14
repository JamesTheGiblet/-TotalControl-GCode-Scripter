# gcode_test_files.py
# This file contains various G-code examples for testing the gcode_optimizer.py script.

# Simple G-code: Square print
simple_gcode = [
    ";Simple square print",
    "G21 ; mm",
    "G90 ; Absolute",
    "G0 X10 Y10 Z0.2 F6000",
    "G1 X20 Y10 E1.0 F1200",
    "G1 X20 Y20 E2.0",
    "G1 X10 Y20 E3.0",
    "G1 X10 Y10 E4.0",
    "M84 ; Disable motors"
]

# G-code with non-printing moves and mixed extrusion
mixed_gcode = [
    ";Mixed moves with travel and extrusion",
    "G21 ; mm",
    "G90 ; Absolute",
    "G0 X5 Y5 Z0.2 F6000",
    "G1 X10 Y5 E1.0 F1200",
    "G0 X15 Y10 F6000",  # Travel move
    "G1 X20 Y10 E2.0 F1200",
    "G1 X20 Y20 E3.0",
    "G0 X10 Y20 F6000",  # Travel move
    "G1 X10 Y15 E4.0 F1200",
    "M84"
]

# G-code with multiple layers and features
multi_layer_gcode = [
    ";Multi-layer print with perimeters and infill",
    "G21 ; mm",
    "G90 ; Absolute",
    "M104 S200 T0",
    "M109 S200 T0",
    "G28 ; Home",
    "G1 Z5 F5000",
    ";LAYER:0",
    "M106 S255",
    ";TYPE:PERIMETER",
    "G0 X20 Y20 Z0.2 F6000",
    "G1 X40 Y20 E5.0 F1200",
    "G1 X40 Y40 E10.0",
    "G1 X20 Y40 E15.0",
    "G1 X20 Y20 E20.0",
    ";TYPE:INFILL",
    "G0 X30 Y30 Z0.2 F6000",
    "G1 X35 Y30 E22.0 F1200",
    "G1 X35 Y35 E24.0",
    "G1 X30 Y35 E26.0",
    ";LAYER:1",
    "G0 X25 Y25 Z0.4 F6000",
    "G1 X45 Y25 E30.0 F1200",
    "G1 X45 Y45 E35.0",
    "G1 X25 Y45 E40.0",
    "G1 X25 Y25 E45.0",
    "M107",
    "G1 Z10 F3000",
    "G28 X0 Y0",
    "M84"
]

# G-code with complex curves
complex_curve_gcode = [
    "; G-code with complex curves",
    "G21 ; mm",
    "G90 ; Absolute",
    "G0 Z0.2 F500",
    "G1 X10 Y10 F1000",
    "G2 X20 Y20 I10 J0 F2000", # Clockwise arc
    "G3 X30 Y10 I10 J0 F2000", # Anticlockwise arc
    "G1 X40 Y20 F1000",
    "G2 X50 Y10 I0 J-10 F2000",
    "G1 X60 Y10 F1000",
    "M84"
]


all_test_gcodes = [simple_gcode, mixed_gcode, multi_layer_gcode, complex_curve_gcode]
# Function to print all G-code examples