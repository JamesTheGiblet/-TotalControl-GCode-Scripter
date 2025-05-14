# gcode_optimizer.py
# This file contains the G-code optimization logic for the AI-driven path optimization phase.
# It includes parsing G-code commands, segmenting them into layers, optimizing the order of extrusion segments,
# and generating the final optimized G-code output.

# --- GCode Optimization Module ---

# Import the modules we created
from gcode_parser import parse_gcode_lines, GCodeCommand
from gcode_segmenter import segment_gcode_into_layers, group_layer_commands_into_segments
from path_optimization import optimize_extrude_segments_order_nn, apply_2opt_to_segment_order
from gcode_generator import regenerate_gcode_for_layer, eliminate_redundant_travel_moves_in_list

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
    # Note: The above code is a conceptual representation and may require adjustments based on actual G-code structure.
# The above code is a conceptual representation and may require adjustments based on actual G-code structure.