# gcode_optimizer.py
# This file contains the G-code optimization logic for the AI-driven path optimization phase.
# It includes parsing G-code commands, segmenting them into layers, optimizing the order of extrusion segments,
# and generating the final optimized G-code output.

# --- GCode Optimization Module ---
import math
import re
# --- Data Structures ---
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
                f"start={self.start_point_xyz}, end={self.end_point_xyz})")


# --- Helper Functions ---
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


def euclidean_distance(p1_xyz, p2_xyz):
    """Calculate Euclidean distance between two 3D points (x,y,z)."""
    if p1_xyz is None or p2_xyz is None: return float('inf')
    # For travel planning within a layer, Z is often constant, so 2D distance is fine.
    # However, PrintSegment stores start/end_point_xyz, so use 3D.
    return math.sqrt((p1_xyz[0] - p2_xyz[0])**2 + \
                     (p1_xyz[1] - p2_xyz[1])**2 + \
                     (p1_xyz[2] - p2_xyz[2])**2)

def xy_distance(p1_xyz, p2_xyz):
    """Calculate Euclidean distance between two points in XY plane."""
    if p1_xyz is None or p2_xyz is None: return float('inf')
    return math.sqrt((p1_xyz[0] - p2_xyz[0])**2 + (p1_xyz[1] - p2_xyz[1])**2)


# --- Optimization Algorithms ---

def calculate_total_travel_for_order(segments_order, initial_nozzle_xyz):
    """
    Calculates the total XY travel distance for a given order of extrusion segments.
    Args:
        segments_order: A list of PrintSegment objects.
        initial_nozzle_xyz: The (x,y,z) where the nozzle is before starting this sequence.
    Returns:
        Total XY travel distance.
    """
    if not segments_order:
        return 0.0
    
    total_dist = 0.0
    current_pos = initial_nozzle_xyz

    for segment in segments_order:
        if segment.start_point_xyz:
            total_dist += xy_distance(current_pos, segment.start_point_xyz)
            if segment.end_point_xyz:
                current_pos = segment.end_point_xyz
            else:
                # This case should ideally not be reached if segments are pre-filtered
                print(f"Warning: Segment {segment} has no end_point_xyz during travel calculation.")
                return float('inf') # Invalid path
        else:
            # This case should ideally not be reached
            print(f"Warning: Segment {segment} has no start_point_xyz during travel calculation.")
            return float('inf') # Invalid path
    return total_dist

def apply_2opt_to_segment_order(ordered_segments, initial_nozzle_xyz, max_iterations_no_improvement=50):
    """Applies the 2-opt heuristic to improve the order of extrude segments."""
    if len(ordered_segments) < 2: # 2-opt needs at least 2 segments to swap.
        return ordered_segments

    current_best_order = list(ordered_segments)
    current_best_distance = calculate_total_travel_for_order(current_best_order, initial_nozzle_xyz)
    
    num_segments = len(current_best_order)
    stale_iterations = 0

    while stale_iterations < max_iterations_no_improvement:
        improved_in_pass = False
        for i in range(num_segments - 1):
            for k in range(i + 1, num_segments):
                new_order = list(current_best_order) # Work on a copy
                segment_to_reverse = new_order[i : k+1]
                segment_to_reverse.reverse()
                new_order[i : k+1] = segment_to_reverse
                
                new_distance = calculate_total_travel_for_order(new_order, initial_nozzle_xyz)

                if new_distance < current_best_distance - 1e-5: # Use a small tolerance for improvement
                    current_best_order = new_order
                    current_best_distance = new_distance
                    improved_in_pass = True
                    # print(f"2-opt improvement: new_distance={current_best_distance:.2f} with swap ({i}, {k})") # Debug
        
        if improved_in_pass:
            stale_iterations = 0 # Reset counter if improvement was made
        else:
            stale_iterations += 1 # Increment if no improvement in this full pass

    # print(f"2-opt finished. Final distance: {current_best_distance:.2f}")
    return current_best_order

def optimize_extrude_segments_order_nn(extrude_segments, current_nozzle_xyz):
    """
    Reorders extrude_segments using a nearest-neighbor heuristic.
    Args:
        extrude_segments: A list of PrintSegment objects of type "extrude".
        current_nozzle_xyz: The (x,y,z) where the nozzle is before starting this sequence.
    Returns:
        A new list of PrintSegment objects in the optimized order.
    """
    if not extrude_segments:
        return []

    num_segments = len(extrude_segments)
    ordered_segments = []
    # Create a mutable list of segments to choose from, with their original indices if needed
    remaining_segments_with_indices = list(enumerate(extrude_segments))

    # current_pos_xyz is the nozzle's current position
    current_pos_xyz = current_nozzle_xyz

    for _ in range(num_segments):
        if not remaining_segments_with_indices: break

        best_segment_info = None
        min_dist_to_start = float('inf')

        for i, (original_idx, segment) in enumerate(remaining_segments_with_indices):
            if segment.start_point_xyz:
                # Using XY distance for in-layer travel planning
                dist = xy_distance(current_pos_xyz, segment.start_point_xyz)
                if dist < min_dist_to_start:
                    min_dist_to_start = dist
                    best_segment_info = (i, segment) # Store (index_in_remaining, segment_object)
            else:
                print(f"Warning: Extrude segment {original_idx} has no start_point_xyz, skipping in NN.")


        if best_segment_info:
            idx_in_remaining, chosen_segment = best_segment_info
            ordered_segments.append(chosen_segment)
            if chosen_segment.end_point_xyz:
                 current_pos_xyz = chosen_segment.end_point_xyz # Update nozzle position
            else: # Should not happen if segments are well-defined
                print(f"Warning: Chosen segment has no end_point_xyz: {chosen_segment}")
                break # Or handle error
            remaining_segments_with_indices.pop(idx_in_remaining)
        else:
            # No suitable next segment found (e.g., all remaining have no start_point_xyz)
            print("Warning: No suitable next segment found in NN optimization.")
            break

    return ordered_segments


def regenerate_gcode_for_layer(ordered_extrude_segments, initial_nozzle_xyz, layer_z, travel_feed_rate=3000, extrusion_feed_rate=1200):
    """
    Generates GCode commands for a layer from ordered extrude segments,
    inserting G0 travel moves.
    Args:
        ordered_extrude_segments: List of PrintSegment (extrude type) in desired order.
        initial_nozzle_xyz: The (x,y,z) of the nozzle before the first travel move of this sequence.
        layer_z: The Z height for this layer (used for travel moves).
        travel_feed_rate: Feed rate for G0 travel moves.
        extrusion_feed_rate: Default feed rate for G1 extrusion moves if not specified in segment.

    Returns:
        A list of GCodeCommand objects for the optimized layer's printing part.
    """
    optimized_gcode_cmds = []
    current_xyz = initial_nozzle_xyz

    for segment_idx, segment in enumerate(ordered_extrude_segments):
        if not segment.start_point_xyz:
            print(f"Warning: Skipping segment {segment_idx} due to missing start_point_xyz.")
            continue

        target_x, target_y, _ = segment.start_point_xyz # Z for travel will be layer_Z
        
        # 1. Create G0 travel move to the start of the extrude segment
        # Check if travel is needed (i.e., nozzle is not already at segment.start_point_xyz)
        needs_travel = True
        if current_xyz:
            if abs(current_xyz[0] - target_x) < 1e-3 and \
               abs(current_xyz[1] - target_y) < 1e-3 and \
               abs(current_xyz[2] - layer_z) < 1e-3: # Also check Z
                needs_travel = False
        
        if needs_travel:
            travel_params_dict = {'F': travel_feed_rate, 'X': target_x, 'Y': target_y, 'Z': layer_z}
            
            g0_line_parts = ["G0"]
            if 'F' in travel_params_dict: g0_line_parts.append(f"F{travel_params_dict['F']}")
            if 'X' in travel_params_dict: g0_line_parts.append(f"X{travel_params_dict['X']}")
            if 'Y' in travel_params_dict: g0_line_parts.append(f"Y{travel_params_dict['Y']}")
            if 'Z' in travel_params_dict: g0_line_parts.append(f"Z{travel_params_dict['Z']}") # Ensure Z is in travel
            raw_g0_line = " ".join(g0_line_parts)

            # Manually create GCodeCommand for travel as parse expects full GCode line context
            travel_cmd = GCodeCommand(original_line=raw_g0_line, command_type='G0', params=travel_params_dict,
                                      x=target_x, y=target_y, z=layer_z, f=travel_feed_rate, is_extruding=False)
            
            # travel_cmd = GCodeCommand.parse(raw_g0_line) # Parse to get all fields - this won't work correctly without full context            travel_cmd.x, travel_cmd.y, travel_cmd.z = target_x, target_y, layer_z # Ensure these are set
            optimized_gcode_cmds.append(travel_cmd)
            current_xyz = (target_x, target_y, layer_z)
            # print(f"Debug: Added travel G0 to ({target_x:.3f}, {target_y:.3f}, {layer_z:.3f})")

        # 2. Add the extrusion commands from the segment
        for cmd in segment.commands:
            optimized_gcode_cmds.append(cmd)
            # Update current_xyz based on the last command of the segment
            if cmd.x is not None and cmd.y is not None and cmd.z is not None: # If cmd updates position
                current_xyz = (cmd.x, cmd.y, cmd.z)
            elif segment.end_point_xyz: # Fallback to segment's defined end if cmd doesn't have full XYZ
                current_xyz = segment.end_point_xyz


    return optimized_gcode_cmds


def eliminate_redundant_travel_moves_in_list(gcode_command_list):
    """Identifies and eliminates consecutive redundant G0 movements."""
    if not gcode_command_list:
        return []

    final_commands = []
    last_motion_command = None

    for cmd in gcode_command_list:
        is_redundant = False        
        if cmd.command_type == 'G0':
            # A G0 is redundant if it moves to the same X,Y,Z as the last motion command's target
            # AND it doesn't set a new feedrate (F).
            # The cmd.x, cmd.y, cmd.z are the resolved absolute coordinates for this G0.
            # last_motion_command.x, .y, .z are the resolved absolute target coordinates of the previous motion command.
            if last_motion_command and last_motion_command.command_type in ['G0', 'G1', 'G2', 'G3']:
                # Check if all specified coordinates in the current G0 match the last motion command's target
                # and that the current G0 doesn't introduce a feedrate change.
                
                # Assume not moved unless a specified coordinate differs
                moved_x = cmd.x is not None and (last_motion_command.x is None or abs(cmd.x - last_motion_command.x) > 1e-5)
                moved_y = cmd.y is not None and (last_motion_command.y is None or abs(cmd.y - last_motion_command.y) > 1e-5)
                moved_z = cmd.z is not None and (last_motion_command.z is None or abs(cmd.z - last_motion_command.z) > 1e-5)

                # If any axis is specified in G0 and it's different, it's a move.
                # If an axis is NOT specified in G0, it implies no change for that axis from the G0's perspective.
                # Redundancy means: for all axes specified in G0, they match the last target, AND no new F.
                
                # Check if the target of the current G0 is the same as the target of the last motion command
                # This requires comparing cmd.x, cmd.y, cmd.z (the target of the current G0)
                # with last_motion_command.x, last_motion_command.y, last_motion_command.z (the target of the last motion command)
                # We need to handle cases where coordinates are None (not specified in the command).
                # A G0 is redundant if its target X, Y, Z are the same as the previous motion command's target X, Y, Z.
                if last_motion_command.x is not None and cmd.x is not None and abs(cmd.x - last_motion_command.x) < 1e-5 and \
                   last_motion_command.y is not None and cmd.y is not None and abs(cmd.y - last_motion_command.y) < 1e-5 and \
                   last_motion_command.z is not None and cmd.z is not None and abs(cmd.z - last_motion_command.z) < 1e-5:
                    is_redundant = True
                
                # Also, an empty G0 (no X,Y,Z,F) is redundant
                if cmd.x is None and cmd.y is None and cmd.z is None and cmd.f is None:
                    is_redundant = True

        if not is_redundant:
            final_commands.append(cmd)
            last_motion_command = cmd if cmd.command_type in ['G0', 'G1', 'G2', 'G3'] else last_motion_command

    return final_commands

# --- Main Orchestration (Conceptual) ---
def optimize_gcode_travel(input_gcode_lines):
    """
    Main function to apply travel optimization to GCode.
    """
    print(f"\n--- Phase 2: AI-Driven Path Optimization - Initial Travel Minimization ---")
    print(f"Input GCode has {len(input_gcode_lines)} lines.")

    # 1. Parse all GCode lines
    all_parsed_commands = parse_gcode_lines(input_gcode_lines)
    print(f"Parsed {len(all_parsed_commands)} GCode commands with coordinate resolution.")

    # 2. Identify Preamble, Body, and Postamble
    preamble_commands = []
    body_commands = []
    postamble_commands = []
    
    first_body_cmd_idx = -1
    # Find first ";LAYER:" comment or first G0/G1 to a typical print Z after initial setup
    # This is a heuristic and might need adjustment based on G-code conventions
    for i, cmd in enumerate(all_parsed_commands):
        if cmd.original_line.startswith(";LAYER:"):
            first_layer_marker_idx = i
            break
        # Add more heuristics if needed, e.g., first G0 X Y Z after G28 and M109
    
    if first_layer_marker_idx == -1: # No explicit layer markers, assume all is body (simplification)
        print("Warning: No explicit ';LAYER:' comments found. Treating all commands as body after initial G28/lift if any.")
        # Attempt to find end of preamble by looking for first significant XY move at low Z
        g28_found = any(c.command_type == 'G28' for c in all_parsed_commands) # Check if G28 is present
        for i, cmd in enumerate(all_parsed_commands):
            if g28_found and cmd.command_type in ['G0','G1'] and cmd.x is not None and cmd.y is not None and cmd.z is not None and cmd.z < 5.0 : # Arbitrary low Z
                first_body_cmd_idx = i
                break
        if first_body_cmd_idx == -1 : first_body_cmd_idx = 0 # If no heuristic works, assume body starts at index 0
    else: first_body_cmd_idx = first_layer_marker_idx # If layer marker found, body starts there


    last_layer_related_cmd_idx = len(all_parsed_commands) -1
    # Find last command related to printing (e.g., last G1 E, or last command of last layer comment block)
    # Heuristic: postamble starts after last G1 E, or with M107, G28, M84 etc.
    for i in range(len(all_parsed_commands) - 1, first_layer_marker_idx -1, -1):
        cmd = all_parsed_commands[i]
        if cmd.command_type == 'G1' and cmd.is_extruding:
            last_layer_related_cmd_idx = i
            # Extend to include subsequent non-extruding moves or M-codes of that layer (e.g. M107)
            for j in range(i + 1, len(all_parsed_commands)):
                next_cmd = all_parsed_commands[j]
                if next_cmd.command_type in ['G28', 'M2', 'M84'] or \
                   (next_cmd.command_type == 'G1' and next_cmd.z is not None and next_cmd.x is None and next_cmd.y is None and next_cmd.e is None): # Final Z lift
                    break # This is postamble
                last_layer_related_cmd_idx = j
            break

    preamble_commands = all_parsed_commands[:first_body_cmd_idx]
    body_commands = all_parsed_commands[first_body_cmd_idx : last_layer_related_cmd_idx + 1]
    postamble_commands = all_parsed_commands[last_layer_related_cmd_idx + 1 :]

    print(f"Identified Preamble: {len(preamble_commands)} cmds, Body: {len(body_commands)} cmds, Postamble: {len(postamble_commands)} cmds.")

    final_optimized_gcode_commands = []
    final_optimized_gcode_commands.extend(preamble_commands)

    current_nozzle_xyz = (0.0, 0.0, 0.0) # Assume starting at origin if no position in preamble
    for cmd in preamble_commands: # Update nozzle position from preamble
        if cmd.x is not None and cmd.y is not None and cmd.z is not None: # If G0/G1 sets position
            current_nozzle_xyz = (cmd.x, cmd.y, cmd.z)

    # 3. Segment Body into Layers
    gcode_layers = segment_gcode_into_layers(body_commands)
    print(f"Segmented body into {len(gcode_layers)} layers.")

    for i, layer_cmds_list in enumerate(gcode_layers):
        # Define the desired order of feature types for printing.
        # Standard slicers often use: Perimeters -> Infill -> Skin/TopSolid -> Support
        # We can make this configurable later.
        # Common types: PERIMETER, WALL-OUTER, WALL-INNER, FILL, SKIN, TOP-SOLID-FILL, BRIDGE, SUPPORT
        # Let's use a simplified order for now.
        FEATURE_PRINT_ORDER = ["PERIMETER", "WALL-OUTER", "WALL-INNER", "FILL", "SKIN", "BRIDGE", "SUPPORT", "UNKNOWN"]

        print(f"\nProcessing Layer {i+1} (original cmd count: {len(layer_cmds_list)})...")
        if not layer_cmds_list:
            print(f"Layer {i+1} is empty, skipping.")
            continue

        # Determine layer's Z height (most common Z in G0/G1 moves of this layer)
        # Heuristic: use Z from first G0/G1 command in the layer, or carry over.
        layer_z_this_layer = current_nozzle_xyz[2] # Default to previous Z
        # Find the first Z value in a motion command within this layer
        z_values_in_layer = [cmd.z for cmd in layer_cmds_list if cmd.z is not None and cmd.command_type in ['G0', 'G1', 'G2', 'G3']]
        if z_values_in_layer:
            # Use the first Z value encountered as the layer's Z height for travel moves
            layer_z_this_layer = z_values_in_layer[0]
        print(f"Layer {i+1} Z determined/assumed as: {layer_z_this_layer}")

        # Group commands in the current layer into PrintSegments
        segments_in_layer = group_layer_commands_into_segments(layer_cmds_list)
        
        print(f"Layer {i+1}: Grouped into {len(segments_in_layer)} segments.")

        # Separate segments into optimizable (extrude with valid endpoints) and non-optimizable
        optimizable_segments_map = {ft: [] for ft in FEATURE_PRINT_ORDER}
        non_optimizable_commands = [] # Commands from segments that won't be reordered

        for segment in segments_in_layer:
            is_extrude_block = any(cmd.is_extruding for cmd in segment.commands) # Use is_extruding flag
            is_valid_extrude_segment = is_extrude_block and segment.start_point_xyz and segment.end_point_xyz

            if is_valid_extrude_segment and segment.feature_type in optimizable_segments_map:
                optimizable_segments_map[segment.feature_type].append(segment)
                # print(f"Debug: Layer {i+1}: Added segment (type={segment.segment_type}, feature={segment.feature_type}, cmds={len(segment.commands)}) to optimizable map.")
            else:
                non_optimizable_commands.extend(segment.commands)
                # print(f"Debug: Layer {i+1}: Added segment (type={segment.segment_type}, feature={segment.feature_type}, cmds={len(segment.commands)}) to non-optimizable.")

        # Add non-optimizable commands first
        final_optimized_gcode_commands.extend(non_optimizable_commands)
        if non_optimizable_commands:
            last_non_opt_cmd = non_optimizable_commands[-1]
            if last_non_opt_cmd.x is not None and last_non_opt_cmd.y is not None and last_non_opt_cmd.z is not None:
                current_nozzle_xyz = (last_non_opt_cmd.x, last_non_opt_cmd.y, last_non_opt_cmd.z)
            # print(f"Debug: Layer {i+1}: Added {len(non_optimizable_commands)} non-optimizable commands. Nozzle at: {current_nozzle_xyz}")

        # Process optimizable segments grouped by feature type in the defined order
        for feature_type in FEATURE_PRINT_ORDER:
            segments_to_optimize = optimizable_segments_map.get(feature_type, [])
            if segments_to_optimize:
                print(f"Layer {i+1}: Optimizing {len(segments_to_optimize)} segments of type '{feature_type}'. Nozzle before block: {current_nozzle_xyz}")

                nozzle_pos_before_this_feature_block = current_nozzle_xyz

                # Apply Nearest Neighbor + 2-opt optimization
                optimized_nn_order = optimize_extrude_segments_order_nn(segments_to_optimize, nozzle_pos_before_this_feature_block)
                # print(f"Layer {i+1}, {feature_type}: Applying 2-opt refinement to {len(optimized_nn_order)} segments.")
                optimized_final_order = apply_2opt_to_segment_order(optimized_nn_order, nozzle_pos_before_this_feature_block)

                # Regenerate G-code for the optimized block, including travel moves
                regenerated_feature_block_cmds = regenerate_gcode_for_layer(optimized_final_order, nozzle_pos_before_this_feature_block, layer_z_this_layer)
                final_optimized_gcode_commands.extend(regenerated_feature_block_cmds)

                # Update current_nozzle_xyz from the very end of this feature block
                if regenerated_feature_block_cmds:
                    last_cmd_in_block = regenerated_feature_block_cmds[-1]
                    if last_cmd_in_block.x is not None and last_cmd_in_block.y is not None and last_cmd_in_block.z is not None:
                        current_nozzle_xyz = (last_cmd_in_block.x, last_cmd_in_block.y, last_cmd_in_block.z)
                    # print(f"Debug: Layer {i+1}, {feature_type}: Finished. Nozzle at: {current_nozzle_xyz}")
            
            # Reassembly: Leading non-extrude -> Optimized extrude block -> Trailing non-extrude
            leading_cmds = []
            optimized_block_input_segments = []
            trailing_cmds = []
            
            processing_phase = "leading" # leading, extrude_block, trailing
            
            # Determine nozzle position before the optimizable block
            nozzle_pos_before_opt_block = current_nozzle_xyz 
            # Iterate through original segments to build leading_cmds and update nozzle_pos_before_opt_block
            temp_pos_tracker = current_nozzle_xyz
            first_extrude_idx_in_layer = -1
            last_extrude_idx_in_layer = -1

            for seg_idx, seg in enumerate(segments_in_layer):
                if seg.segment_type == "extrude":
                    if first_extrude_idx_in_layer == -1:
                        first_extrude_idx_in_layer = seg_idx
                    last_extrude_idx_in_layer = seg_idx
            
            if first_extrude_idx_in_layer != -1:
                for seg_idx in range(first_extrude_idx_in_layer):
                    leading_cmds.extend(segments_in_layer[seg_idx].commands)
                    if segments_in_layer[seg_idx].end_point_xyz:
                        temp_pos_tracker = segments_in_layer[seg_idx].end_point_xyz
                nozzle_pos_before_opt_block = temp_pos_tracker

                optimized_nn_order = optimize_extrude_segments_order_nn(segments_to_optimize, nozzle_pos_before_opt_block)
                print(f"Layer {i+1}: Applying 2-opt refinement to {len(optimized_nn_order)} segments.")
                optimized_final_order = apply_2opt_to_segment_order(optimized_nn_order, nozzle_pos_before_opt_block)

                regenerated_extrude_block_cmds = regenerate_gcode_for_layer(optimized_final_order, nozzle_pos_before_opt_block, layer_z_this_layer)

                for seg_idx in range(last_extrude_idx_in_layer + 1, len(segments_in_layer)):
                    trailing_cmds.extend(segments_in_layer[seg_idx].commands)

                final_optimized_gcode_commands.extend(leading_cmds)
                final_optimized_gcode_commands.extend(regenerated_extrude_block_cmds)
                final_optimized_gcode_commands.extend(trailing_cmds)

                # Update current_nozzle_xyz from the very end of this reassembled layer
                if trailing_cmds:
                    last_cmd = trailing_cmds[-1]
                    if last_cmd.x is not None and last_cmd.y is not None and last_cmd.z is not None:
                        current_nozzle_xyz = (last_cmd.x, last_cmd.y, last_cmd.z)
                elif regenerated_extrude_block_cmds:
                    last_cmd = regenerated_extrude_block_cmds[-1]
                    if last_cmd.x is not None and last_cmd.y is not None and last_cmd.z is not None:
                        current_nozzle_xyz = (last_cmd.x, last_cmd.y, last_cmd.z)
                elif leading_cmds:
                    last_cmd = leading_cmds[-1]
                    if last_cmd.x is not None and last_cmd.y is not None and last_cmd.z is not None:
                        current_nozzle_xyz = (last_cmd.x, last_cmd.y, last_cmd.z)
                # else current_nozzle_xyz remains from before this layer if layer was all funny
            else: # Should not happen if extrude_segments_this_layer is populated
                final_optimized_gcode_commands.extend(layer_cmds_list) # Fallback
                if layer_cmds_list and layer_cmds_list[-1].x is not None and layer_cmds_list[-1].y is not None and layer_cmds_list[-1].z is not None:
                    current_nozzle_xyz = (layer_cmds_list[-1].x, layer_cmds_list[-1].y, layer_cmds_list[-1].z)

        print(f"Layer {i+1} processing finished. Nozzle at: {current_nozzle_xyz}")

    final_optimized_gcode_commands.extend(postamble_commands)
    print(f"Added {len(postamble_commands)} postamble commands.")

    # 5. Eliminate Redundant Moves (globally, after reassembly)
    final_gcode_after_redundancy_elim = eliminate_redundant_travel_moves_in_list(final_optimized_gcode_commands)
    print(f"\nApplied redundant move elimination. Original cmd count: {len(final_optimized_gcode_commands)}, New count: {len(final_gcode_after_redundancy_elim)}")

    # Convert back to raw GCode lines for output
    output_gcode_lines = [cmd.original_line for cmd in final_gcode_after_redundancy_elim if cmd.original_line] # Ensure no empty lines from parsing

    print(f"Optimization complete. Output GCode has {len(output_gcode_lines)} lines.")
    return output_gcode_lines


# --- Example Usage (Conceptual) ---
if __name__ == "__main__":
    sample_gcode_input = [
        ";Generated by TotalControl Phase 1 (Conceptual)",
        "G21 ; mm",
        "G90 ; Absolute",
        "M82 ; Absolute E",
        "M104 S200 T0 ; Set extruder temp",
        "M109 S200 T0 ; Wait for extruder temp",
        "G28 ; Home all axes",
        "G1 Z5 F5000 ; Lift Z after homing",
        ";LAYER_COUNT:2",
        ";LAYER:0",
        "M106 S255 ; Fan On",
        ";TYPE:PERIMETER",
        "G0 F6000 X10 Y10 Z0.2 ; Travel to start of layer 1, part 1",
        "G1 F1200 X20 Y10 E1.0 ; Extrude segment 1.1",
        "G1 X20 Y20 E2.0",
        "G1 X10 Y20 E3.0",
        ";TYPE:INFILL",
        "G0 F6000 X50 Y50 Z0.2 ; Travel to segment 1.2 (far)",
        ";TYPE:INFILL", # Type comment can be on any line, ideally before the first command of the feature
        "G1 F1200 X60 Y50 E4.0 ; Extrude segment 1.2",
        "G1 X60 Y60 E5.0",
        "G1 X50 Y60 E6.0",
        "G0 F6000 X10.5 Y20.5 Z0.2 ; Travel to segment 1.3 (near original 1.1 end)",
        "G1 F1200 X20.5 Y20.5 E7.0 ; Extrude segment 1.3",
        "G1 X20.5 Y10.5 E8.0",
        "G1 X10.5 Y10.5 E9.0",
        ";TYPE:PERIMETER", # Another perimeter segment
        ";LAYER:1",
        "G0 F6000 X10 Y10 Z0.4 ; Travel to start of layer 2",
        "G1 F1200 X30 Y10 E10.0 ; Extrude segment 2.1",
        "G1 X30 Y30 E11.0",
        "G1 X10 Y30 E12.0",
        "G0 X10 Y10 Z0.4 ; Redundant travel (to same spot)",
        "G0 X10 Y10 Z0.4 ; Another redundant travel",
        "M107 ; Fan off",
        "G1 Z10 F3000 ; Lift Z further",
        "G28 X0 Y0 ; Home X Y axes",
        "M84 ; Disable motors"
    ]

    optimized_gcode = optimize_gcode_travel(sample_gcode_input)

    print("\n--- Original GCode ---")
    for line_num, line in enumerate(sample_gcode_input):
        print(f"{line_num+1:03d}: {line}")

    print("\n--- Optimized GCode (Conceptual) ---")
    for line_num, line in enumerate(optimized_gcode):
        print(f"{line_num+1:03d}: {line}")