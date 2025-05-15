# strategies.py
# saved in strategies directory
# this file contains the implementation of the deposition sequence optimization strategy
# for G-code generation and optimization.

import logging
import re
from collections import defaultdict
from modules.safety_limits import PrinterProfile # Import PrinterProfile from within the same package - Not directly used in this basic prototype

 # Set up logging for this module
logger = logging.getLogger(__name__)

# Defines the desired order for printing features.
# Feature names should be uppercase and match what's extracted from G-code comments
# (e.g., if G-code has ";TYPE:External Perimeter", it's normalized to "EXTERNAL PERIMETER").
FEATURE_PRINT_ORDER = [
    "SKIRT",
    "BRIM",
    "PERIMETER",
    "EXTERNAL PERIMETER", # Often perimeters are printed outer-to-inner or vice-versa by slicers
    "OVERHANG PERIMETER", # Specific handling for overhangs often comes first or with perimeters
    "FILL",               # Generic infill
    "SOLID INFILL",       # Top/bottom solid layers
    "INTERNAL INFILL",    # General sparse infill
    "BRIDGE",             # Bridge infill
    "SUPPORT",
    "SUPPORT INTERFACE"   # Dense support layers
]

# Regex to identify feature type comments (e.g., ";TYPE:PERIMETER", "; FEATURE:Fill")
# It captures the feature name. Case-insensitive.
FEATURE_COMMENT_RE = re.compile(r";\s*(?:TYPE|FEATURE)\s*:\s*([\w\s.-]+)", re.IGNORECASE)


def apply_deposition_sequence_optimization(gcode_lines, printer_profile: PrinterProfile = None):
    """
    Applies deposition sequence optimization strategies (Phase 2.1.2).
    This is a placeholder for implementing logic like:
    - Overhang handling (extra perimeters, infill first, inside-out perimeters, overlap, infill increase)
    - Small feature/layer cooling (pauses, reordering)
    - Other feature-specific ordering based on adhesion/stress.

    Currently, this function is a placeholder and returns the input lines unchanged.
    Actual implementation requires parsing G-code into structured segments with feature types,
    geometric analysis (overhangs, size), and complex G-code modification/generation.

    Args:
        gcode_lines (list[str]): A list of G-code command strings.
        printer_profile (PrinterProfile, optional): The loaded printer profile containing limits and settings. Defaults to None.

    Returns:
        list[str]: A list of G-code command strings after applying optimization strategies.
    """
    logger.info("Applying basic deposition sequence optimization...")

    prologue = []
    feature_blocks = defaultdict(list) # Stores commands for each feature type
    misc_commands = [] # For commands after all feature blocks or unclassified

    active_feature_type = None
    has_seen_first_feature_comment = False

    for line in gcode_lines:
        match = FEATURE_COMMENT_RE.match(line)
        is_feature_comment_line = False

        if match:
            extracted_type = match.group(1).strip().upper() # Normalize
            active_feature_type = extracted_type
            feature_blocks[active_feature_type].append(line) # Start block with its comment
            has_seen_first_feature_comment = True
            is_feature_comment_line = True
        
        if not is_feature_comment_line:
            if active_feature_type: # Current line belongs to the active_feature_type
                feature_blocks[active_feature_type].append(line)
            elif not has_seen_first_feature_comment: # Still in prologue
                prologue.append(line)
            else: # Has seen feature(s), but this line is not a feature comment and not part of the last active feature.
                misc_commands.append(line)

    if not feature_blocks:
        logger.info("No recognized feature type comments found. Returning original G-code.")
        return list(gcode_lines) # Return a copy

    logger.info(f"Found feature blocks for types: {', '.join(sorted(feature_blocks.keys()))}")
    logger.info(f"Reordering based on defined sequence: {', '.join(FEATURE_PRINT_ORDER)}")

    optimized_gcode = list(prologue)
    processed_feature_log_order = []

    for feature_type_to_print in FEATURE_PRINT_ORDER:
        if feature_type_to_print in feature_blocks:
            logger.debug(f"Adding block for feature type: {feature_type_to_print} ({len(feature_blocks[feature_type_to_print])} lines)")
            optimized_gcode.extend(feature_blocks[feature_type_to_print])
            processed_feature_log_order.append(feature_type_to_print)
            del feature_blocks[feature_type_to_print] # Mark as processed

    remaining_feature_types = sorted(feature_blocks.keys())
    if remaining_feature_types:
        logger.info(f"Adding remaining feature blocks not in explicit print order (alphabetically): {', '.join(remaining_feature_types)}")
        for feature_type in remaining_feature_types:
            logger.debug(f"Adding remaining block for feature type: {feature_type} ({len(feature_blocks[feature_type])} lines)")
            optimized_gcode.extend(feature_blocks[feature_type])
            processed_feature_log_order.append(feature_type)
    
    optimized_gcode.extend(misc_commands)

    if processed_feature_log_order:
        logger.info(f"Final feature order in G-code: {', '.join(processed_feature_log_order)}")
    
    logger.info("Basic deposition sequence optimization finished.")
    return optimized_gcode