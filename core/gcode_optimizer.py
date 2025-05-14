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
    def parse(cls, line, current_e_value=0.0):
        """
        Parses a single GCode line.
        A more robust parser would handle comments better, various command syntaxes,
        and maintain more state (like last known E for G1 extrusion detection).
        """
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith(';'):
            return cls(raw_line=line_stripped) # Keep comments and empty lines as is

        parts = line_stripped.split(';')[0].strip().split() # Remove comments first, then split
        if not parts: # Line was only a comment
             return cls(raw_line=line_stripped)

        cmd_type = parts[0].upper()
        params = {}
        x, y, z, e_val, f_val = None, None, None, None, None
        is_extruding_move = False

        for part in parts[1:]:
            code = part[0].upper()
            if not part[1:]: # Handle case like "G0 X10 Y" (malformed, but be robust)
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
                # For non-float params or if parsing fails for a specific param
                params[code] = part[1:]


        # Determine if it's an extruding move (simplified)
        # G1, G2, G3 can be extruding moves.
        # A common way to check is if E is present and its value is greater than the previous E.
        # This requires tracking the previous E value.
        if cmd_type in ['G1', 'G2', 'G3'] and e_val is not None:
            if e_val > current_e_value: # Simple check: positive E increment means extrusion
                is_extruding_move = True
            # Note: Retractions (E < current_e_value) are G1 moves but not 'extruding' for path planning.
            # Slicers might also use G1 without E for travel if feedrate is high.

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
        """
        # This is a simplified endpoint calculation. A full GCode interpreter
        # would track the machine state (current_x, current_y, current_z) more rigorously.
        temp_x, temp_y, temp_z = None, None, None

        # Find first coordinate
        for cmd in self.commands:
            if cmd.x is not None: temp_x = cmd.x
            if cmd.y is not None: temp_y = cmd.y
            if cmd.z is not None: temp_z = cmd.z
            if self.start_point_xyz is None and temp_x is not None and temp_y is not None and temp_z is not None:
                self.start_point_xyz = (temp_x, temp_y, temp_z)
            # Update cmd objects with resolved coordinates if they were missing (e.g. G1 Y10 after G0 X5)
            # This part is complex and requires proper state machine for GCode.
            # For now, we assume GCodeCommand.parse fills x,y,z if present in the line.
            # If a command only has Y, its X and Z are modal (from previous command).
            # The GCodeCommand objects should ideally store their *effective* X,Y,Z after parsing.

        # Last known X,Y,Z becomes the end_point
        # Re-iterate to get the final state after all commands in segment
        final_x, final_y, final_z = None, None, None
        # If segment starts with a Z move, that Z should be the layer Z
        if self.commands and self.commands[0].z is not None:
            final_z = self.commands[0].z

        for cmd in self.commands:
            if cmd.x is not None: final_x = cmd.x
            if cmd.y is not None: final_y = cmd.y
            if cmd.z is not None: final_z = cmd.z # Z usually changes per layer, but is const within a 2.5D segment

            if self.start_point_xyz is None and final_x is not None and final_y is not None and final_z is not None:
                 self.start_point_xyz = (final_x, final_y, final_z)


        if final_x is not None and final_y is not None and final_z is not None:
            self.end_point_xyz = (final_x, final_y, final_z)
        
        # If only one command, start and end might be the same if it's a point-like operation
        if self.start_point_xyz and not self.end_point_xyz and len(self.commands) == 1:
            self.end_point_xyz = self.start_point_xyz


    def __repr__(self):
        return (f"PrintSegment(type={self.segment_type}, cmds={len(self.commands)}, "
                f"start={self.start_point_xyz}, end={self.end_point_xyz})")


# --- Helper Functions ---
def parse_gcode_lines(gcode_lines):
    """Parses a list of GCode strings into GCodeCommand objects, tracking extruder state."""
    parsed_commands = []
    current_e = 0.0 # Track last E value
    current_x, current_y, current_z = None, None, None # Track current position

    for line_num, line_str in enumerate(gcode_lines):
        cmd = GCodeCommand.parse(line_str, current_e)

        # Update current position state based on the parsed command
        # This is crucial for commands that only specify some axes (e.g., G1 Y10)
        effective_x = cmd.x if cmd.x is not None else current_x
        effective_y = cmd.y if cmd.y is not None else current_y
        effective_z = cmd.z if cmd.z is not None else current_z
        
        # Update the command object with its effective coordinates
        cmd.x, cmd.y, cmd.z = effective_x, effective_y, effective_z
        
        # Update state for next command
        current_x, current_y, current_z = effective_x, effective_y, effective_z
        if cmd.e is not None:
            current_e = cmd.e
        
        parsed_commands.append(cmd)
    return parsed_commands

def segment_gcode_into_layers(parsed_commands):
    """
    Segments GCode into layers.
    A simple heuristic: a new layer starts with a Z move after some extrusion,
    or specific layer comments like ';LAYER:N'.
    This is a placeholder for more robust layer detection from Phase 1 or slicer comments.
    """
    layers = []
    current_layer_commands = []
    last_significant_z = None # Z value of the current layer being built

    for cmd in parsed_commands:
        is_layer_delimiter_comment = cmd.raw_line.startswith(";LAYER:") or \
                                     cmd.raw_line.startswith(";LAYER_CHANGE") or \
                                     cmd.raw_line.startswith(";Z:") # Common slicer comments

        new_layer_by_z_move = False
        if cmd.command_type in ['G0', 'G1'] and cmd.z is not None:
            if last_significant_z is None or cmd.z > last_significant_z + 1e-3: # Z increased
                if current_layer_commands: # Only if there were commands in previous layer segment
                    new_layer_by_z_move = True
            # Update last_significant_z if this command sets Z
            # This ensures that subsequent commands in the same layer don't trigger a new layer
            # if they also happen to have Z (e.g. G0 X10 Y10 Z0.2 followed by G1 X20 Y10 Z0.2 E1)
            # last_significant_z = cmd.z # This was causing issues. Only update when new layer is FORMED.


        if (is_layer_delimiter_comment or new_layer_by_z_move) and current_layer_commands:
            layers.append(current_layer_commands)
            current_layer_commands = []
            if cmd.z is not None: # If this command triggered the new layer by Z move
                last_significant_z = cmd.z


        current_layer_commands.append(cmd)
        # If this command itself sets a Z that defines the start of a new layer, update last_significant_z
        if new_layer_by_z_move and cmd.z is not None:
             last_significant_z = cmd.z
        elif is_layer_delimiter_comment and cmd.z is not None: # If comment also has Z info
             last_significant_z = cmd.z


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
    """Identifies and eliminates redundant G0 movements from a list of GCodeCommand objects."""
    if not gcode_command_list:
        return []

    final_commands = []
    last_g0_cmd_params = None # Store params of last G0 to compare
    current_x, current_y, current_z = None, None, None # Track printer head position from all moves

    for cmd_idx, cmd in enumerate(gcode_command_list):
        is_redundant = False
        if cmd.command_type == 'G0':
            # Check 1: Exact duplicate of previous G0 (same params, not just raw line)
            # This is tricky if params order changes but effectively same.
            # A simpler check: if this G0 moves to where we already are.

            # Check 2: Moves to current known X, Y, Z without other effect (like changing F)
            # This requires accurate current_x, current_y, current_z tracking.
            target_x = cmd.x if cmd.x is not None else current_x
            target_y = cmd.y if cmd.y is not None else current_y
            target_z = cmd.z if cmd.z is not None else current_z # Z might not be in G0 if it's within layer travel

            # If all specified axes in the G0 match the current position
            moved = False
            if cmd.x is not None and (current_x is None or abs(cmd.x - current_x) > 1e-3): moved = True
            if cmd.y is not None and (current_y is None or abs(cmd.y - current_y) > 1e-3): moved = True
            if cmd.z is not None and (current_z is None or abs(cmd.z - current_z) > 1e-3): moved = True
            
            if not moved:
                # If no positional change, is it just an F-set? If so, not redundant.
                # If it has X,Y,Z and they don't change position, AND no F, it's redundant.
                if cmd.f is None: # Or if cmd.f is same as current feedrate (needs more state)
                    is_redundant = True
                # If it's G0 without X,Y,Z,F (empty G0), it's redundant.
                if cmd.x is None and cmd.y is None and cmd.z is None and cmd.f is None and cmd.command_type == 'G0':
                    is_redundant = True


        if not is_redundant:
            final_commands.append(cmd)
            # Update current position from any G0/G1 command that was kept
            if cmd.command_type in ['G0', 'G1']:
                if cmd.x is not None: current_x = cmd.x
                if cmd.y is not None: current_y = cmd.y
                if cmd.z is not None: current_z = cmd.z
        # else:
            # print(f"Redundant move eliminated: {cmd.raw_line} (current pos: {current_x},{current_y},{current_z})")

    return final_commands

# --- Main Orchestration (Conceptual) ---
def optimize_gcode_travel(input_gcode_lines):
    """
    Main function to apply travel optimization to GCode.
    """
    print(f"Phase 2: AI-Driven Path Optimization - Initial Travel Minimization")
    print(f"Input GCode has {len(input_gcode_lines)} lines.")

    # 1. Parse GCode into GCodeCommand objects with resolved coordinates
    parsed_commands = parse_gcode_lines(input_gcode_lines)
    print(f"Parsed {len(parsed_commands)} GCode commands with coordinate resolution.")

    # 2. Segment by Layer
    gcode_layers = segment_gcode_into_layers(parsed_commands)
    print(f"Segmented into {len(gcode_layers)} layers.")

    final_optimized_gcode_commands = []
    current_nozzle_xyz = (0.0, 0.0, 0.0) # Assume starting at origin or track from GCode preamble

    # Handle GCode preamble (commands before the first layer)
    if gcode_layers:
        first_cmd_of_first_layer = gcode_layers[0][0]
        preamble_end_idx = -1
        for idx, cmd in enumerate(parsed_commands):
            if cmd == first_cmd_of_first_layer:
                preamble_end_idx = idx
                break
        if preamble_end_idx != -1:
            preamble_commands = parsed_commands[:preamble_end_idx]
            final_optimized_gcode_commands.extend(preamble_commands)
            # Update nozzle position from preamble
            for cmd in preamble_commands:
                if cmd.x is not None and cmd.y is not None and cmd.z is not None:
                    current_nozzle_xyz = (cmd.x, cmd.y, cmd.z)
            print(f"Added {len(preamble_commands)} preamble commands. Nozzle at: {current_nozzle_xyz}")


    for i, layer_cmds_list in enumerate(gcode_layers):
        print(f"\nProcessing Layer {i+1} with {len(layer_cmds_list)} commands...")
        if not layer_cmds_list:
            print(f"Layer {i+1} is empty, skipping.")
            continue

        # Determine layer's Z height (most common Z in G0/G1 moves of this layer)
        # A more robust way: from ';LAYER:Z:value' or first G0/G1 Z move.
        layer_z_this_layer = current_nozzle_xyz[2] # Default to previous Z
        z_values_in_layer = [cmd.z for cmd in layer_cmds_list if cmd.z is not None and cmd.command_type in ['G0','G1']]
        if z_values_in_layer:
            # Simplistic: use the first Z found in a G0/G1 as the layer's Z.
            # A better method would be to find the Z of the first actual printing move or a layer comment.
            layer_z_this_layer = z_values_in_layer[0]
        print(f"Layer {i+1} Z determined/assumed as: {layer_z_this_layer}")


        # Group commands in the current layer into PrintSegments
        segments_in_layer = group_layer_commands_into_segments(layer_cmds_list)
        
        extrude_segments = [s for s in segments_in_layer if s.segment_type == "extrude" and s.start_point_xyz and s.end_point_xyz]
        # Keep other segments (travel, M-codes, comments) to re-insert later
        non_extrude_segments_map = {idx: s for idx, s in enumerate(segments_in_layer) if s.segment_type != "extrude"}
        
        print(f"Layer {i+1}: Found {len(extrude_segments)} extrude segments to optimize.")

        if not extrude_segments:
            print(f"Layer {i+1}: No extrude segments. Adding original layer commands.")
            final_optimized_gcode_commands.extend(layer_cmds_list)
            # Update nozzle position from last command in this layer
            for cmd in reversed(layer_cmds_list):
                if cmd.x is not None and cmd.y is not None and cmd.z is not None:
                    current_nozzle_xyz = (cmd.x, cmd.y, cmd.z)
                    break
            continue

        # The nozzle is at `current_nozzle_xyz` before processing this layer's extrusions
        optimized_extrude_order = optimize_extrude_segments_order_nn(extrude_segments, current_nozzle_xyz)
        
        # Regenerate GCode for the printing parts of the layer
        # The `current_nozzle_xyz` is where the nozzle is *before* the first travel to an extrude segment.
        layer_print_gcode = regenerate_gcode_for_layer(optimized_extrude_order, current_nozzle_xyz, layer_z_this_layer)
        
        # This is a simplification: It doesn't re-insert 'other' or original 'travel' segments intelligently.
        # A more robust solution would merge `layer_print_gcode` with `non_extrude_segments_map`
        # based on their original relative ordering or specific rules.
        # For now, we just use the newly generated GCode for the extrude parts.
        # We should prepend any non-extrude, non-travel commands that were at the start of the layer.
        
        initial_non_extrude_cmds_for_layer = []
        for seg_idx, seg in enumerate(segments_in_layer):
            if seg.segment_type == "extrude":
                break # Stop when first extrude segment is found
            initial_non_extrude_cmds_for_layer.extend(seg.commands)
        
        final_optimized_gcode_commands.extend(initial_non_extrude_cmds_for_layer)
        final_optimized_gcode_commands.extend(layer_print_gcode)

        # Update nozzle position from the end of the optimized layer printing
        if layer_print_gcode:
            last_cmd_optimized = layer_print_gcode[-1]
            if last_cmd_optimized.x is not None and last_cmd_optimized.y is not None and last_cmd_optimized.z is not None:
                 current_nozzle_xyz = (last_cmd_optimized.x, last_cmd_optimized.y, last_cmd_optimized.z)
        elif initial_non_extrude_cmds_for_layer: # If only initial commands were added
            last_cmd_initial = initial_non_extrude_cmds_for_layer[-1]
            if last_cmd_initial.x is not None and last_cmd_initial.y is not None and last_cmd_initial.z is not None:
                 current_nozzle_xyz = (last_cmd_initial.x, last_cmd_initial.y, last_cmd_initial.z)

        print(f"Layer {i+1} processing finished. Nozzle at: {current_nozzle_xyz}")

    # Handle GCode postamble (commands after the last layer)
    # This logic is also simplified. Assumes last command of last layer is known.
    if gcode_layers and parsed_commands:
        last_cmd_of_last_layer = gcode_layers[-1][-1]
        postamble_start_idx = -1
        for idx, cmd in enumerate(parsed_commands):
            if cmd == last_cmd_of_last_layer:
                postamble_start_idx = idx + 1
                break
        if postamble_start_idx != -1 and postamble_start_idx < len(parsed_commands):
            postamble_commands = parsed_commands[postamble_start_idx:]
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

    # Expected outcome (conceptual for the sample):
    # - Preamble/Postamble should be preserved.
    # - Within Layer 0: Segment 1.1 -> Segment 1.3 -> Segment 1.2 (if NN decides this order based on start points)
    # - Travel moves (G0) between these reordered segments should be newly generated.
    # - Within Layer 1: Redundant G0 moves should be removed.
    # - M-codes like M106/M107 should ideally be preserved in their correct layer context.
    #   (Current simplified reassembly might need improvement for this).
