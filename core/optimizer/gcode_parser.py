# gcode_parser.py
import re

class GCodeCommand:
    def __init__(self, original_line, command_type=None, params=None, comment=None,
                 line_number=0, x=None, y=None, z=None, e=None, f=None, feature_type=None, is_extruding=False):
        self.original_line = original_line.strip()
        self.command_type = command_type  # e.g., 'G0', 'G1', 'M104'
        self.params = params if params is not None else {} # e.g., {'X': 10.0, 'Y': 5.0}
        self.is_extruding = False # Initialize with a default value or pass it as a parameter
        # Store key coordinates for easy access and state tracking
        self.x = x
        self.y = y
        self.z = z
        self.e = e # Extruder position
        self.f = f # Feedrate
        self.feature_type = feature_type # e.g., "PERIMETER", "INFILL", "SUPPORT", "UNKNOWN"
        self.is_extruding = is_extruding
        self.line_number = line_number # Ensure line_number is stored
        self.comment = comment # Ensure comment is stored

    def __repr__(self):
        return f"GCodeCommand({self.command_type}, {self.params}, L:{self.line_number}, XYZ:({self.x},{self.y},{self.z}), E:{self.e}, F:{self.f}, Type:{self.feature_type})"

    @classmethod
    def parse(cls, line, current_e_value=0.0, last_motion_e=0.0, current_feature_type="UNKNOWN"):
        """
        Parses a single GCode line, tracking extruder state based on the
        E parameter and comparing it to the E value of the last motion command.
        Also attempts to extract feature type from comments like '; TYPE: ...'.
        """
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith(';'):
            return cls(original_line=line_stripped)

        parts = line_stripped.split(';')[0].strip().split()
        if not parts:
            return cls(original_line=line_stripped)

        cmd_type = parts[0].upper()
        params = {}
        x, y, z, e_val, f_val = None, None, None, None, None
        is_extruding_move = False

        for part in parts[1:]:
            code = part[0].upper()
            if not part[1:]:
                continue
            try:
                value = float(part[1:])
                params[code] = value
                if code == 'X': x = value
                elif code == 'Y': y = value
                elif code == 'Z': z = value
                elif code == 'E': e_val = value
                elif code == 'F': f_val = value
            except ValueError:
                params[code] = part[1:]

        # An extruding move for deposition purposes is a G1/G2/G3 command where E increases.
        if cmd_type in ['G1', 'G2', 'G3'] and e_val is not None:
            if e_val > last_motion_e + 1e-5:  # e_val must be strictly greater for deposition
                # Note: This simple check doesn't handle retractions (E decreases) correctly
                # as non-extruding moves. A more robust check might be needed.
                is_extruding_move = True

        # Extract comment part
        comment = ""
        if ';' in line_stripped:
                comment = line_stripped.split(';', 1)[1].strip()

        # Pass the current_feature_type determined by the caller (parse_gcode_lines)
        # Only associate feature type with motion commands for now, or maybe all commands?
        # Let's associate it with motion commands as that's where it's most relevant for segmentation.
        feature_type_for_cmd = current_feature_type if cmd_type in ['G0', 'G1', 'G2', 'G3'] else None

        # Pass all relevant parsed/determined values to the constructor
        # line_number will use its default (0) here; parse_gcode_lines can update it if needed.
        return cls(original_line=line_stripped, command_type=cmd_type, params=params, comment=comment,
                   x=x, y=y, z=z, e=e_val, f=f_val, feature_type=feature_type_for_cmd, is_extruding=is_extruding_move)

def parse_gcode_lines(gcode_lines):
    """
    Parses a list of GCode strings into GCodeCommand objects, tracking extruder state
    and resolving absolute coordinates based on previous commands.
    Also tracks feature type from comments.
    """
    parsed_commands = []
    current_e = 0.0  # Track last E value
    current_x, current_y, current_z = None, None, None  # Track current position
    last_motion_e = 0.0 # Track E value of the last G0/G1/G2/G3
    current_feature_type = "UNKNOWN" # Track current feature type from comments

    for line_num, line_str in enumerate(gcode_lines):
        # Check for feature type comments (case-insensitive) before parsing the command itself
        type_match = re.search(r";\s*TYPE\s*:\s*(\w+)", line_str, re.IGNORECASE)
        if type_match:
            current_feature_type = type_match.group(1).upper()

        cmd = GCodeCommand.parse(line_str, current_e, last_motion_e, current_feature_type)
        cmd.line_number = line_num + 1 # Store line number

        effective_x = cmd.x if cmd.x is not None else current_x
        effective_y = cmd.y if cmd.y is not None else current_y
        effective_z = cmd.z if cmd.z is not None else current_z

        cmd.x, cmd.y, cmd.z = effective_x, effective_y, effective_z

        current_x, current_y, current_z = effective_x, effective_y, effective_z
        if cmd.e is not None:
            current_e = cmd.e
            if cmd.command_type in ['G0', 'G1', 'G2', 'G3']:
                last_motion_e = cmd.e

        # The feature_type is already set on the command object by GCodeCommand.parse if found in the line.
        parsed_commands.append(cmd)
    return parsed_commands

if __name__ == "__main__":
    sample_gcode = [
        "G0 X10 Y10 Z0.2",
        "G1 X20 Y10 E1.0",
        "; TYPE: INFILL",
        "G1 X20 Y20 E2.0",
        "G0 X50 Y50 Z0.2",
        ";TYPE: PERIMETER",
        "G1 X60 Y50 E3.0"
    ]
    parsed_commands = parse_gcode_lines(sample_gcode)
    for cmd in parsed_commands:
        print(cmd)
    # Example usage
    # parsed_commands = parse_gcode_lines(sample_gcode)