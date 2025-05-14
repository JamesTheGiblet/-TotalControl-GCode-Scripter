# gcode_optimizer.py
# This file contains the G-code optimization logic for the AI-driven path optimization phase.
# It includes parsing G-code commands, segmenting them into layers, optimizing the order of extrusion segments,
# and generating the final optimized G-code output.

# --- GCode Optimization Module ---

# Standard library imports
import sys
import os

# Import the modules we created
from gcode_parser import parse_gcode_lines, GCodeCommand
from gcode_segmenter import segment_gcode_into_layers, group_layer_commands_into_segments, PrintSegment
from path_optimization import optimize_extrude_segments_order_nn, apply_2opt_to_segment_order, calculate_total_travel_for_order
from gcode_generator import regenerate_gcode_for_layer, eliminate_redundant_travel_moves_in_list

# --- Main Orchestration ---
def optimize_gcode_travel(input_gcode_lines):
    """
    Main function to apply travel optimization to GCode.  This function orchestrates the
    entire G-code optimization process, calling functions from other modules.
    """
    print(f"\n--- Phase 2: AI-Driven Path Optimization - Initial Travel Minimization ---")
    print(f"Input GCode has {len(input_gcode_lines)} lines.")

    # 1. Parse all GCode lines: Convert raw G-code text into a list of GCodeCommand objects.
    all_parsed_commands = parse_gcode_lines(input_gcode_lines)
    print(f"Parsed {len(all_parsed_commands)} GCode commands with coordinate resolution.")

    # 2. Identify Preamble, Body, and Postamble:  Divide the G-code into sections that define the print.
    preamble_commands = []  # Commands before the main printing moves (e.g., setup, homing).
    body_commands = []    # The main printing moves (extrusion and travel).
    postamble_commands = []  # Commands after the printing is finished (e.g., cooling, motor off).
    
    first_body_cmd_idx = -1
    first_layer_marker_idx = -1  # Initialize first_layer_marker_idx
    # Find first ";LAYER:" comment or first G0/G1 to a typical print Z after initial setup
    # This is a heuristic and might need adjustment based on G-code conventions.  The goal is to
    # find the start of the actual printing process, after any initial setup.
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
    # Heuristic: postamble starts after last G1 E, or with M107, G28, M84 etc.  The goal is to find the
    # end of the printing moves and the start of the post-print actions.
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

    final_optimized_gcode_commands = []  # List to store the final optimized G-code commands.
    final_optimized_gcode_commands.extend(preamble_commands) # Add the preamble commands to the output.

    current_nozzle_xyz = (0.0, 0.0, 0.0) # Assume starting at origin if no position in preamble
    for cmd in preamble_commands: # Update nozzle position from preamble
        if cmd.x is not None and cmd.y is not None and cmd.z is not None: # If G0/G1 sets position
            current_nozzle_xyz = (cmd.x, cmd.y, cmd.z)

    # 3. Segment Body into Layers:  Divide the main printing commands into layers.
    gcode_layers = segment_gcode_into_layers(body_commands)
    print(f"Segmented body into {len(gcode_layers)} layers.")

    # 4. Process each layer individually.
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

        # Determine layer's Z height
        layer_z_this_layer = None
        for cmd in layer_cmds_list:
            if cmd.command_type in ['G0', 'G1'] and cmd.z is not None:
                layer_z_this_layer = cmd.z
                break
        if layer_z_this_layer is None:
            layer_z_this_layer = current_nozzle_xyz[2]
        print(f"Layer {i+1} Z determined as: {layer_z_this_layer}")


        # 4. Group commands in the current layer into PrintSegments
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
            else:
                non_optimizable_commands.extend(segment.commands)


        # Add non-optimizable commands first
        final_optimized_gcode_commands.extend(non_optimizable_commands)
        if non_optimizable_commands:
            last_non_opt_cmd = non_optimizable_commands[-1]
            if last_non_opt_cmd.x is not None and last_non_opt_cmd.y is not None and last_non_opt_cmd.z is not None:
                current_nozzle_xyz = (last_non_opt_cmd.x, last_non_opt_cmd.y, last_non_opt_cmd.z)

        # Process optimizable segments grouped by feature type in the defined order
        for feature_type in FEATURE_PRINT_ORDER:
            segments_to_optimize = optimizable_segments_map.get(feature_type, [])
            if segments_to_optimize:
                print(f"Layer {i+1}: Optimizing {len(segments_to_optimize)} segments of type '{feature_type}'. Nozzle before block: {current_nozzle_xyz}")

                nozzle_pos_before_this_feature_block = current_nozzle_xyz

                # Calculate initial travel distance
                initial_distance = calculate_total_travel_for_order(segments_to_optimize, nozzle_pos_before_this_feature_block)
                
                # Apply Nearest Neighbor + 2-opt optimization
                optimized_nn_order = optimize_extrude_segments_order_nn(segments_to_optimize, nozzle_pos_before_this_feature_block)
                print(f"Layer {i+1}, {feature_type}: Applying 2-opt refinement to {len(optimized_nn_order)} segments.")
                optimized_final_order = apply_2opt_to_segment_order(optimized_nn_order, nozzle_pos_before_this_feature_block, max_iterations_no_improvement=100)

                # Calculate travel distance after optimization
                optimized_distance = calculate_total_travel_for_order(optimized_final_order, nozzle_pos_before_this_feature_block)
                
                print(f"Layer {i+1}, {feature_type}: Initial travel distance: {initial_distance:.2f}, optimized distance: {optimized_distance:.2f}")


                # Regenerate G-code for the optimized block, including travel moves
                regenerated_feature_block_cmds = regenerate_gcode_for_layer(optimized_final_order, nozzle_pos_before_this_feature_block, layer_z_this_layer)
                final_optimized_gcode_commands.extend(regenerated_feature_block_cmds)

                # Update current_nozzle_xyz from the very end of this feature block
                if regenerated_feature_block_cmds:
                    last_cmd_in_block = regenerated_feature_block_cmds[-1]
                    if last_cmd_in_block.x is not None and last_cmd_in_block.y is not None and last_cmd_in_block.z is not None:
                        current_nozzle_xyz = (last_cmd_in_block.x, last_cmd_in_block.y, last_cmd_in_block.z)

        print(f"Layer {i+1} processing finished. Nozzle at: {current_nozzle_xyz}")

    final_optimized_gcode_commands.extend(postamble_commands) # Add the postamble commands to the output.

    # 5. Eliminate Redundant Moves (globally, after reassembly)
    final_gcode_after_redundancy_elim = eliminate_redundant_travel_moves_in_list(final_optimized_gcode_commands)
    print(f"\nApplied redundant move elimination. Original cmd count: {len(final_optimized_gcode_commands)}, New count: {len(final_gcode_after_redundancy_elim)}")

    # Convert back to raw GCode lines for output
    output_gcode_lines = [cmd.original_line for cmd in final_gcode_after_redundancy_elim if cmd.original_line] # Ensure no empty lines from parsing

    print(f"Optimization complete. Output GCode has {len(output_gcode_lines)} lines.")
    return output_gcode_lines



# --- Example Usage (Conceptual) ---
if __name__ == "__main__":
    # To allow running this script directly and finding the example_tests module,
    # we need to add the project root directory to sys.path.
    # This assumes that 'example_tests' is a directory at the project root,
    # and this script ('gcode_optimizer.py') is located in 'core/optimizer/'.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from example_tests.gcode_test_files import all_test_gcodes  # Import for example usage

    for i, test_gcode in enumerate(all_test_gcodes):
        print(f"\n--- Running optimization on Test G-code {i+1} ---")
        optimized_gcode = optimize_gcode_travel(test_gcode)

        print("\n--- Original GCode ---")
        for line_num, line in enumerate(test_gcode):
            print(f"{line_num+1:03d}: {line}")

        print("\n--- Optimized GCode (Conceptual) ---")
        for line_num, line in enumerate(optimized_gcode):
            print(f"{line_num+1:03d}: {line}")
        print("\n--- End of Test G-code ---")
        print("\n--- End of Optimization ---")