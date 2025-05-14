# gcode_segmenter.py
from gcode_parser import GCodeCommand

class PrintSegment:
    """Represents a contiguous block of GCode commands, either for extrusion or travel."""
    def __init__(self, commands, segment_type="extrude"): # type can be "extrude" or "travel" or "other"
        self.commands = commands # List of GCodeCommand objects
        self.segment_type = segment_type
        self.start_point_xyz = None # (x, y, z)
        self.end_point_xyz = None   # (x, y, z)
        self.feature_type = "UNKNOWN" # e.g., "PERIMETER", "INFILL"
        self._calculate_endpoints_and_update_cmds()

    def _calculate_endpoints_and_update_cmds(self):
        """
        Determines the start and end coordinates of the segment.
        This needs to track the current X, Y, Z state through the commands.
        For simplicity, assumes commands provide absolute coordinates or they are resolved by parser.
        Relies on GCodeCommand.x, .y, .z being pre-resolved to absolute coordinates
        by the parse_gcode_lines function.
        """
        # Determine segment feature type - use the type of the first command that has one
        for cmd in self.commands:
            if cmd.feature_type and cmd.feature_type != "UNKNOWN":
                self.feature_type = cmd.feature_type
        if not self.commands:
            return

        # Start point is from the first command's resolved coordinates
        first_cmd = self.commands[0]
        if first_cmd.x is not None and first_cmd.y is not None and first_cmd.z is not None:
            self.start_point_xyz = (first_cmd.x, first_cmd.y, first_cmd.z)
        # else: start_point_xyz remains None if first command has no fully defined coords.
        # This might occur for segments starting with non-positional commands, though
        # group_layer_commands_into_segments typically groups motion commands.

        # End point is from the last command's resolved coordinates
        last_cmd = self.commands[-1]
        if last_cmd.x is not None and last_cmd.y is not None and last_cmd.z is not None:
            self.end_point_xyz = (last_cmd.x, last_cmd.y, last_cmd.z)

        # If a segment is a single point-like operation or a non-moving command sequence
        # where start is known but end isn't explicitly different.
        if self.start_point_xyz and not self.end_point_xyz:
            self.end_point_xyz = self.start_point_xyz


    def __repr__(self):
        return (f"PrintSegment(type={self.segment_type}, cmds={len(self.commands)}, "
                f"start={self.start_point_xyz}, end={self.end_point_xyz}, feature={self.feature_type})")


def segment_gcode_into_layers(parsed_commands):
    """
    Segments GCode into layers.
    A simple heuristic: a new layer starts with a Z move after some extrusion,
    or specific layer comments like ';LAYER:N'.
    This is a placeholder for more robust layer detection from Phase 1 or slicer comments.
    This function expects commands that are part of the printable body (post-preamble, pre-postamble).
    """
    layers = []
    current_layer_commands = []
    last_layer_defining_z = None # Z value that defined the start of the current layer segment

    # Determine if explicit layer comments are used
    has_explicit_layer_comments = any(cmd.original_line.startswith(";LAYER:") for cmd in parsed_commands)

    for cmd in parsed_commands:
        is_new_layer_boundary = False
        if has_explicit_layer_comments:
            if cmd.original_line.startswith(";LAYER:"):
                if current_layer_commands: # New layer starts here
                    is_new_layer_boundary = True
        else: # Fallback to Z-based segmentation
            if cmd.command_type in ['G0', 'G1'] and cmd.z is not None:
                if current_layer_commands: # Only consider new layer if current one has content
                    if last_layer_defining_z is None or cmd.z > last_layer_defining_z + 1e-3:
                        is_new_layer_boundary = True

        if is_new_layer_boundary:
            layers.append(current_layer_commands)
            current_layer_commands = []
            last_layer_defining_z = None # Reset for the new layer

        current_layer_commands.append(cmd)
        # Update last_layer_defining_z if this command sets a Z for the current layer segment
        if cmd.command_type in ['G0', 'G1'] and cmd.z is not None:
            if last_layer_defining_z is None: # First Z for this layer segment
                last_layer_defining_z = cmd.z
            elif has_explicit_layer_comments and cmd.original_line.startswith(";LAYER:"):
                # If it's an explicit layer comment on a Z move, that Z defines the new layer
                last_layer_defining_z = cmd.z

    if current_layer_commands: # Add the last layer
        layers.append(current_layer_commands)
    return layers


def group_layer_commands_into_segments(layer_commands):
    """Groups commands within a single layer into PrintSegments (extrude, travel, other)."""
    segments = []
    current_segment_cmds = []
    current_segment_type = None # "extrude", "travel", or "other"

    for cmd in layer_commands:
        segment_type_for_cmd = "other" # Default for M-codes, T-codes, comments etc.

        if cmd.command_type == 'G0':
            segment_type_for_cmd = "travel"
        elif cmd.command_type in ['G1', 'G2', 'G3']:
            if cmd.is_extruding:
                segment_type_for_cmd = "extrude"
            else: # G1 without positive E change (or G1 E-ve for retraction) is travel-like
                segment_type_for_cmd = "travel"

        if current_segment_type != segment_type_for_cmd and current_segment_cmds:
            # End previous segment
            segments.append(PrintSegment(current_segment_cmds, current_segment_type))
            # print(f"Debug: Created segment type {current_segment_type} with {len(current_segment_cmds)} commands.")
            current_segment_cmds = []

        # For non-motion commands, the segment type is 'other' and they are typically single-command segments.
        # For motion commands (G0, G1, G2, G3), they are grouped until the motion type changes or extrusion state changes.

        current_segment_cmds.append(cmd)
        current_segment_type = segment_type_for_cmd

    if current_segment_cmds: # Add any remaining segment
        segments.append(PrintSegment(current_segment_cmds, current_segment_type))
    return segments

if __name__ == "__main__":
    from gcode_parser import parse_gcode_lines
    sample_gcode = [
        "G0 X10 Y10 Z0.2",
        "G1 X20 Y10 E1.0",
        "; TYPE: INFILL",
        "G1 X20 Y20 E2.0",
        "G0 X50 Y50 Z0.2",
        ";TYPE: PERIMETER",
        "G1 X60 Y50 E3.0",
        ";LAYER:1",
        "G0 X10 Y10 Z0.4",
        "G1 X30 Y10 E4.0",
        "M106 S255",
        "G1 X30 Y30 E5.0",
        "G0 X15 Y15 Z0.4",
        "G1 X25 Y15 E6.0"
    ]
    parsed_commands = parse_gcode_lines(sample_gcode)
    layers = segment_gcode_into_layers(parsed_commands)
    print("\n--- Layers ---")
    for i, layer in enumerate(layers):
        print(f"Layer {i+1}:")
        for cmd in layer:
            print(f"  {cmd}")
        segments = group_layer_commands_into_segments(layer)
        print("  --- Segments ---")
        for seg in segments:
            print(f"    {seg}")
            for cmd in seg.commands:
                print(f"      {cmd}")
    print("\n--- End of Segments ---")
    # This is a test to ensure the segmenter works with the parser.
    # The output will show the layers and their segments.
    # The segments are created based on the commands in each layer.