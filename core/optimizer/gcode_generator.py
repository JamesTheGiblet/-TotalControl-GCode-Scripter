# gcode_generator.py
from gcode_parser import GCodeCommand # Import the GCodeCommand class

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

if __name__ == "__main__":
    # Example Usage (for testing)
    from gcode_segmenter import PrintSegment
    from gcode_parser import GCodeCommand

    # Create some sample PrintSegments and GCodeCommands
    segment1 = PrintSegment(commands=[
        GCodeCommand(original_line="G1 X10 Y10 Z0.2 F1200 E1.0", command_type='G1', params={'X': 10, 'Y': 10, 'Z': 0.2, 'F': 1200, 'E': 1.0}, x=10, y=10, z=0.2, f=1200, e=1.0, is_extruding=True),
        GCodeCommand(original_line="G1 X20 Y10 E2.0", command_type='G1', params={'X': 20, 'Y': 10, 'E': 2.0}, x=20, y=10, z=0.2, e=2.0, is_extruding=True),
        GCodeCommand(original_line="G1 X20 Y20 E3.0", command_type='G1', params={'X': 20, 'Y': 20, 'E': 3.0}, x=20, y=20, z=0.2, e=3.0, is_extruding=True)
    ], segment_type="extrude")
    segment1.start_point_xyz = (10, 10, 0.2)
    segment1.end_point_xyz = (20, 20, 0.2)

    segment2 = PrintSegment(commands=[
        GCodeCommand(original_line="G1 X50 Y50 Z0.2 F1200 E4.0", command_type='G1', params={'X': 50, 'Y': 50, 'Z': 0.2, 'F': 1200, 'E': 4.0}, x=50, y=50, z=0.2, f=1200, e=4.0, is_extruding=True),
        GCodeCommand(original_line="G1 X60 Y50 E5.0", command_type='G1', params={'X': 60, 'Y': 50, 'E': 5.0}, x=60, y=50, z=0.2, e=5.0, is_extruding=True),
        GCodeCommand(original_line="G1 X60 Y60 E6.0", command_type='G1', params={'X': 60, 'Y': 60, 'E': 6.0}, x=60, y=60, z=0.2, e=6.0, is_extruding=True)
    ], segment_type="extrude")
    segment2.start_point_xyz = (50, 50, 0.2)
    segment2.end_point_xyz = (60, 60, 0.2)

    ordered_segments = [segment1, segment2]
    initial_nozzle_position = (0, 0, 0.2)
    layer_z_value = 0.2

    print("\n--- Regenerate GCode for Layer ---")
    regenerated_commands = regenerate_gcode_for_layer(ordered_segments, initial_nozzle_position, layer_z_value, travel_feed_rate=2000, extrusion_feed_rate=1000)
    for cmd in regenerated_commands:
        print(cmd)

    print("\n--- Eliminate Redundant Travel Moves ---")
    # Create a list of GCodeCommands with a redundant G0
    commands_with_redundancy = [
        GCodeCommand(original_line="G0 X10 Y10 Z5 F3000", command_type='G0', params={'X': 10, 'Y': 10, 'Z': 5, 'F': 3000}, x=10, y=10, z=5, f=3000),
        GCodeCommand(original_line="G1 X20 Y20 Z5 F1200 E1.0", command_type='G1', params={'X': 20, 'Y': 20, 'Z': 5, 'F': 1200, 'E': 1.0}, x=20, y=20, z=5, f=1200, e=1.0, is_extruding=True),
        GCodeCommand(original_line="G0 X20 Y20 Z5", command_type='G0', params={'X': 20, 'Y': 20, 'Z': 5}, x=20, y=20, z=5), # Redundant
        GCodeCommand(original_line="G1 X30 Y30 Z5 F1200 E2.0", command_type='G1', params={'X': 30, 'Y': 30, 'Z': 5, 'F': 1200, 'E': 2.0}, x=30, y=30, z=5, f=1200, e=2.0, is_extruding=True),
        GCodeCommand(original_line="G0 X30 Y30 Z5 F5000", command_type='G0', params={'X': 30, 'Y': 30, 'Z': 5, 'F': 5000}, x=30, y=30, z=5, f=5000),  # Not redundant because of F
        GCodeCommand(original_line="G1 X40 Y40 Z5 F1200 E3.0", command_type='G1', params={'X': 40, 'Y': 40, 'Z': 5, 'F': 1200, 'E': 3.0}, x=40, y=40, z=5, f=1200, e=3.0, is_extruding=True),
    ]

    print("\n--- Commands with Redundancy ---")
    for cmd in commands_with_redundancy:
        print(cmd)
    
    filtered_commands = eliminate_redundant_travel_moves_in_list(commands_with_redundancy)
    print("\n--- Commands after Redundancy Elimination ---")
    for cmd in filtered_commands:
        print(cmd)
    # Note: The above code is for demonstration purposes and may need adjustments based on the actual GCodeCommand class implementation.
#     # Note: The above example is for testing purposes and may not represent a real GCode scenario.