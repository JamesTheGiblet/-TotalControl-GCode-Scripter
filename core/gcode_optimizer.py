# gcode_optimizer.py
# This file contains the G-code optimization logic for the AI-driven path optimization phase.
# It includes parsing G-code commands, segmenting them into layers, optimizing the order of extrusion segments,
# and generating the final optimized G-code output.

# --- GCode Optimization Module ---
import math

# --- Data Structures ---
class GCodeCommand:
    def __init__(self, raw_line, command_type=None, params=None, is_extruding=False, x=None, y=None, z=None, e=None, f=None):
        self.raw_line = raw_line.strip()
        self.command_type = command_type # e.g., 'G0', 'G1', 'M104'
        self.params = params if params is not None else {} # e.g., {'X': 10.0, 'Y': 5.0}
        self.is_extruding = is_extruding # True if this command is part of an extrusion move
        # Store key coordinates for easy access and state tracking
        self.x = x
        self.y = y
        self.z = z
        self.e = e # Extruder position
        self.f = f # Feedrate

    def __repr__(self):
        return f"GCodeCommand({self.raw_line})"

    @classmethod
    def parse(cls, line, current_e_value=0.0, last_motion_e=0.0):
        """
        Parses a single GCode line, tracking extruder state based on the
        E parameter and comparing it to the E value of the last motion command.
        """
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith(';'):
            return cls(raw_line=line_stripped)

        parts = line_stripped.split(';')[0].strip().split()
        if not parts:
            return cls(raw_line=line_stripped)

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
                is_extruding_move = True

        return cls(raw_line=line_stripped, command_type=cmd_type, params=params,
                   is_extruding=is_extruding_move, x=x, y=y, z=z, e=e_val, f=f_val)


class PrintSegment:
    """Represents a contiguous block of GCode commands, either for extrusion or travel."""
    def __init__(self, commands, segment_type="extrude"): # type can be "extrude" or "travel" or "other"
        self.commands = commands # List of GCodeCommand objects
        self.segment_type = segment_type
        self.start_point_xyz = None # (x, y, z)
        self.end_point_xyz = None   # (x, y, z)
        self._calculate_endpoints_and_update_cmds()

    def _calculate_endpoints_and_update_cmds(self):
        """
        Determines the start and end coordinates of the segment.
        This needs to track the current X, Y, Z state through the commands.
        For simplicity, assumes commands provide absolute coordinates or they are resolved by parser.
        Relies on GCodeCommand.x, .y, .z being pre-resolved to absolute coordinates
        by the parse_gcode_lines function.
        """
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
    """Parses a list of GCode strings into GCodeCommand objects, tracking extruder state."""
    parsed_commands = []
    current_e = 0.0  # Track last E value
    current_x, current_y, current_z = None, None, None  # Track current position
    last_motion_e = 0.0 # Track E value of the last G0/G1/G2/G3

    for line_num, line_str in enumerate(gcode_lines):
        cmd = GCodeCommand.parse(line_str, current_e, last_motion_e)

        effective_x = cmd.x if cmd.x is not None else current_x
        effective_y = cmd.y if cmd.y is not None else current_y
        effective_z = cmd.z if cmd.z is not None else current_z

        cmd.x, cmd.y, cmd.z = effective_x, effective_y, effective_z

        current_x, current_y, current_z = effective_x, effective_y, effective_z
        if cmd.e is not None:
            current_e = cmd.e
            if cmd.command_type in ['G0', 'G1', 'G2', 'G3']:
                last_motion_e = cmd.e

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
    has_explicit_layer_comments = any(cmd.raw_line.startswith(";LAYER:") for cmd in parsed_commands)

    for cmd in parsed_commands:
        is_new_layer_boundary = False
        if has_explicit_layer_comments:
            if cmd.raw_line.startswith(";LAYER:"):
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
            elif has_explicit_layer_comments and cmd.raw_line.startswith(";LAYER:"):
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
            current_segment_cmds = []

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


def regenerate_gcode_for_layer(ordered_extrude_segments, initial_nozzle_xyz, layer_z, travel_feed_rate=3000):
    """
    Generates GCode commands for a layer from ordered extrude segments,
    inserting G0 travel moves.
    Args:
        ordered_extrude_segments: List of PrintSegment (extrude type) in desired order.
        initial_nozzle_xyz: The (x,y,z) of the nozzle before the first travel move of this sequence.
        layer_z: The Z height for this layer (used for travel moves).
        travel_feed_rate: Feed rate for G0 travel moves.
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
            travel_params_dict = {'F': travel_feed_rate, 'X': round(target_x, 3), 'Y': round(target_y, 3), 'Z': round(layer_z, 3)}
            
            g0_line_parts = ["G0"]
            if 'F' in travel_params_dict: g0_line_parts.append(f"F{travel_params_dict['F']}")
            if 'X' in travel_params_dict: g0_line_parts.append(f"X{travel_params_dict['X']}")
            if 'Y' in travel_params_dict: g0_line_parts.append(f"Y{travel_params_dict['Y']}")
            if 'Z' in travel_params_dict: g0_line_parts.append(f"Z{travel_params_dict['Z']}") # Ensure Z is in travel
            raw_g0_line = " ".join(g0_line_parts)

            travel_cmd = GCodeCommand.parse(raw_g0_line) # Parse to get all fields
            travel_cmd.x, travel_cmd.y, travel_cmd.z = target_x, target_y, layer_z # Ensure these are set
            optimized_gcode_cmds.append(travel_cmd)
            current_xyz = (target_x, target_y, layer_z)

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
                
                is_same_target_location = True
                if cmd.x is not None and (last_motion_command.x is None or abs(cmd.x - last_motion_command.x) > 1e-5): is_same_target_location = False
                if cmd.y is not None and (last_motion_command.y is None or abs(cmd.y - last_motion_command.y) > 1e-5): is_same_target_location = False
                if cmd.z is not None and (last_motion_command.z is None or abs(cmd.z - last_motion_command.z) > 1e-5): is_same_target_location = False
                
                if is_same_target_location and cmd.f is None:
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
    print(f"Phase 2: AI-Driven Path Optimization - Initial Travel Minimization")
    print(f"Input GCode has {len(input_gcode_lines)} lines.")

    # 1. Parse all GCode lines
    all_parsed_commands = parse_gcode_lines(input_gcode_lines)
    print(f"Parsed {len(all_parsed_commands)} GCode commands with coordinate resolution.")

    # 2. Identify Preamble, Body, and Postamble
    preamble_commands = []
    body_commands = []
    postamble_commands = []
    
    first_layer_marker_idx = -1
    # Find first ";LAYER:" comment or first G0/G1 to a typical print Z after initial setup
    # This is a heuristic and might need adjustment based on G-code conventions
    for i, cmd in enumerate(all_parsed_commands):
        if cmd.raw_line.startswith(";LAYER:"):
            first_layer_marker_idx = i
            break
        # Add more heuristics if needed, e.g., first G0 X Y Z after G28 and M109
    
    if first_layer_marker_idx == -1: # No explicit layer markers, assume all is body (simplification)
        print("Warning: No explicit ';LAYER:' comments found. Treating all commands as body after initial G28/lift if any.")
        # Attempt to find end of preamble by looking for first significant XY move at low Z
        g28_found = any(c.command_type == 'G28' for c in all_parsed_commands)
        for i, cmd in enumerate(all_parsed_commands):
            if g28_found and cmd.command_type in ['G0','G1'] and cmd.x is not None and cmd.y is not None and cmd.z is not None and cmd.z < 5.0 : # Arbitrary low Z
                first_layer_marker_idx = i
                break
        if first_layer_marker_idx == -1 : first_layer_marker_idx = 0


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

    preamble_commands = all_parsed_commands[:first_layer_marker_idx]
    body_commands = all_parsed_commands[first_layer_marker_idx : last_layer_related_cmd_idx + 1]
    postamble_commands = all_parsed_commands[last_layer_related_cmd_idx + 1 :]

    print(f"Identified Preamble: {len(preamble_commands)} cmds, Body: {len(body_commands)} cmds, Postamble: {len(postamble_commands)} cmds.")

    final_optimized_gcode_commands = []
    final_optimized_gcode_commands.extend(preamble_commands)

    current_nozzle_xyz = (0.0, 0.0, 0.0) # Assume starting at origin or track from GCode preamble
    for cmd in preamble_commands: # Update nozzle position from preamble
        if cmd.x is not None and cmd.y is not None and cmd.z is not None: # If G0/G1 sets position
            current_nozzle_xyz = (cmd.x, cmd.y, cmd.z)

    # 3. Segment Body into Layers
    gcode_layers = segment_gcode_into_layers(body_commands)
    print(f"Segmented body into {len(gcode_layers)} layers.")

    for i, layer_cmds_list in enumerate(gcode_layers):
        print(f"\nProcessing Layer {i+1} with {len(layer_cmds_list)} commands...")
        if not layer_cmds_list:
            print(f"Layer {i+1} is empty, skipping.")
            continue

        # Determine layer's Z height (most common Z in G0/G1 moves of this layer)
        # Heuristic: use Z from first G0/G1 command in the layer, or carry over.
        layer_z_this_layer = current_nozzle_xyz[2] # Default to previous Z
        z_values_in_layer = [cmd.z for cmd in layer_cmds_list if cmd.z is not None and cmd.command_type in ['G0','G1']]
        if z_values_in_layer:
            # Simplistic: use the first Z found in a G0/G1 as the layer's Z.
            # A better method would be to find the Z of the first actual printing move or a layer comment.
            layer_z_this_layer = z_values_in_layer[0]
        print(f"Layer {i+1} Z determined/assumed as: {layer_z_this_layer}")

        # Group commands in the current layer into PrintSegments
        segments_in_layer = group_layer_commands_into_segments(layer_cmds_list)
        
        extrude_segments_this_layer = [s for s in segments_in_layer if s.segment_type == "extrude" and s.start_point_xyz and s.end_point_xyz]
        
        if not extrude_segments_this_layer:
            print(f"Layer {i+1}: No extrude segments to optimize. Adding original layer commands.")
            final_optimized_gcode_commands.extend(layer_cmds_list)
            # Update nozzle position from last command in this layer
            if layer_cmds_list:
                last_cmd_in_layer = layer_cmds_list[-1]
                if last_cmd_in_layer.x is not None and last_cmd_in_layer.y is not None and last_cmd_in_layer.z is not None:
                    current_nozzle_xyz = (last_cmd_in_layer.x, last_cmd_in_layer.y, last_cmd_in_layer.z)
        else:
            print(f"Layer {i+1}: Found {len(extrude_segments_this_layer)} extrude segments to optimize.")
            
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

                optimized_extrude_order = optimize_extrude_segments_order_nn(extrude_segments_this_layer, nozzle_pos_before_opt_block)
                regenerated_extrude_block_cmds = regenerate_gcode_for_layer(optimized_extrude_order, nozzle_pos_before_opt_block, layer_z_this_layer)

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

    # 5. Eliminate Redundant Moves (globally)
    final_gcode_after_redundancy_elim = eliminate_redundant_travel_moves_in_list(final_optimized_gcode_commands)
    print(f"\nApplied redundant move elimination. Original cmd count: {len(final_optimized_gcode_commands)}, New count: {len(final_gcode_after_redundancy_elim)}")

    # Convert back to raw GCode lines for output
    output_gcode_lines = [cmd.raw_line for cmd in final_gcode_after_redundancy_elim if cmd.raw_line] # Ensure no empty lines from parsing

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
        "G1 Z5 F5000 ; Lift Z",
        ";LAYER_COUNT:2",
        ";LAYER:0",
        "M106 S255 ; Fan On",
        "G0 F6000 X10 Y10 Z0.2 ; Travel to start of layer 1, part 1",
        "G1 F1200 X20 Y10 E1.0 ; Extrude segment 1.1",
        "G1 X20 Y20 E2.0",
        "G1 X10 Y20 E3.0",
        "G0 F6000 X50 Y50 Z0.2 ; Travel to segment 1.2 (far)",
        "G1 F1200 X60 Y50 E4.0 ; Extrude segment 1.2",
        "G1 X60 Y60 E5.0",
        "G1 X50 Y60 E6.0",
        "G0 F6000 X10.5 Y20.5 Z0.2 ; Travel to segment 1.3 (near original 1.1 end)",
        "G1 F1200 X20.5 Y20.5 E7.0 ; Extrude segment 1.3",
        "G1 X20.5 Y10.5 E8.0",
        "G1 X10.5 Y10.5 E9.0",
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

