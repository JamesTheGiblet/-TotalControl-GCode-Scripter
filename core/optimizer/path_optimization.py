# path_optimization.py
import math
from gcode_segmenter import PrintSegment # Import the PrintSegment class

# --- Helper Functions ---

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

def apply_2opt_to_segment_order(ordered_segments, initial_nozzle_xyz, max_iterations_no_improvement=100):
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

if __name__ == "__main__":
    # Example Usage (for testing)
    from gcode_segmenter import PrintSegment
    
    # Create some sample PrintSegments
    segment1 = PrintSegment(commands=[])
    segment1.start_point_xyz = (10, 10, 0)
    segment1.end_point_xyz = (20, 10, 0)
    segment1.segment_type = "extrude"

    segment2 = PrintSegment(commands=[])
    segment2.start_point_xyz = (20, 20, 0)
    segment2.end_point_xyz = (10, 20, 0)
    segment2.segment_type = "extrude"
    
    segment3 = PrintSegment(commands=[])
    segment3.start_point_xyz = (50, 50, 0)
    segment3.end_point_xyz = (60, 50, 0)
    segment3.segment_type = "extrude"

    segment4 = PrintSegment(commands=[])
    segment4.start_point_xyz = (60, 60, 0)
    segment4.end_point_xyz = (50, 60, 0)
    segment4.segment_type = "extrude"

    segments = [segment1, segment2, segment3, segment4]
    initial_pos = (0, 0, 0)

    print("\n--- Original Segment Order ---")
    for seg in segments:
        print(seg)

    print("\n--- Nearest Neighbor Optimization ---")
    nn_ordered_segments = optimize_extrude_segments_order_nn(segments, initial_pos)
    for seg in nn_ordered_segments:
        print(seg)
    
    print(f"\nTotal travel distance (NN): {calculate_total_travel_for_order(nn_ordered_segments, initial_pos):.2f}")
    
    print("\n--- 2-opt Optimization ---")
    two_opt_ordered_segments = apply_2opt_to_segment_order(segments, initial_pos)
    for seg in two_opt_ordered_segments:
        print(seg)

    print(f"\nTotal travel distance (2-opt): {calculate_total_travel_for_order(two_opt_ordered_segments, initial_pos):.2f}")

    print("\n--- 2-opt on NN Result ---")
    two_opt_nn_ordered_segments = apply_2opt_to_segment_order(nn_ordered_segments, initial_pos)
    for seg in two_opt_nn_ordered_segments:
        print(seg)
    print(f"\nTotal travel distance (2-opt on NN): {calculate_total_travel_for_order(two_opt_nn_ordered_segments, initial_pos):.2f}")
    # Note: The above example is for testing purposes and may not represent a real GCode scenario.
    # In a real-world scenario, the segments would be created from parsed GCode commands.