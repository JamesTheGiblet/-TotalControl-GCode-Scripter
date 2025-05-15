# safety_limits.py
# This module provides a class to apply safety limits to GCode commands based on a printer profile.
# It includes parsing GCode commands, clamping parameters based on limits, and reconstructing the GCode line.

import json
import re
import os

# Simple regex to parse GCode commands and parameters
# Matches command (G/M followed by number), then parameters (Letter followed by number)
GCODE_COMMAND_RE = re.compile(r'^([GM]\d+)\s*(.*)')
GCODE_PARAM_RE = re.compile(r'([A-Z])([-+]?\d*\.?\d+)')

class PrinterProfile:
    """Loads and holds safety limits for a specific printer."""
    def __init__(self, profile_path):
        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"Printer profile not found at {profile_path}")
        with open(profile_path, 'r') as f:
            self.limits = json.load(f)
        print(f"Loaded printer profile: {self.limits.get('name', 'Unknown Printer')}")

    def get_limit(self, key_path, default=None):
        """Safely retrieve a nested limit value using dot notation."""
        keys = key_path.split('.')
        value = self.limits
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default


class SafetyLimiter:
    """Applies safety limits to GCode commands based on a printer profile."""
    def __init__(self, profile: PrinterProfile):
        self.profile = profile

    def parse_gcode_line(self, line: str):
        """Parses a single GCode line into command and parameters."""
        line = line.strip()
        if not line or line.startswith(';'):
            return None, {}  # Ignore comments and empty lines

        # Remove comments before parsing command and params
        line_without_comment = re.split(r';', line, maxsplit=1)[0].strip()

        match = GCODE_COMMAND_RE.match(line_without_comment)
        if not match:
            return None, {}  # Not a standard G/M command

        command = match.group(1).upper()
        params_str = match.group(2)
        params = {}
        for param_match in GCODE_PARAM_RE.finditer(params_str):
            key = param_match.group(1).upper()
            value = float(param_match.group(2))  # Assume numeric parameters for now
            params[key] = value

        return command, params

    def clamp_parameters(self, command: str, params: dict):
        """Clamps parameters of specific GCode commands against profile limits."""
        original_params = params.copy()
        clamped_params = params.copy()
        modified = False

        if command in ['G0', 'G1']:  # Linear Move
            max_xy_print_feedrate = self.profile.get_limit('max_feedrate_mm_per_min.xy_print')
            max_xy_travel_feedrate = self.profile.get_limit('max_feedrate_mm_per_min.xy_travel')
            max_z_feedrate = self.profile.get_limit('max_feedrate_mm_per_min.z')

            # Check Feedrate (F parameter)
            if 'F' in clamped_params:
                requested_f = clamped_params['F']
                current_clamped_f = requested_f

                is_xy_move = 'X' in clamped_params or 'Y' in clamped_params
                is_z_move = 'Z' in clamped_params and not is_xy_move  # Z only if no XY
                is_extruding = 'E' in clamped_params and clamped_params['E'] != 0

                if is_xy_move:
                    if is_extruding and max_xy_print_feedrate is not None:
                        if current_clamped_f > max_xy_print_feedrate:
                            current_clamped_f = max_xy_print_feedrate
                            print(f"Warning: Clamped G1/G0 XY print feedrate from {requested_f} to {current_clamped_f} mm/min.")
                            modified = True
                    elif not is_extruding and max_xy_travel_feedrate is not None:
                        if current_clamped_f > max_xy_travel_feedrate:
                            current_clamped_f = max_xy_travel_feedrate
                            print(f"Warning: Clamped G1/G0 XY travel feedrate from {requested_f} to {current_clamped_f} mm/min.")
                            modified = True
                elif is_z_move and max_z_feedrate is not None:
                    if current_clamped_f > max_z_feedrate:
                        current_clamped_f = max_z_feedrate
                        print(f"Warning: Clamped G1/G0 Z feedrate from {requested_f} to {current_clamped_f} mm/min.")
                        modified = True

                clamped_params['F'] = current_clamped_f

            # Check Build Volume (X, Y, Z parameters)
            build_volume = self.profile.get_limit('build_volume_mm')
            if build_volume:
                for axis in ['X', 'Y', 'Z']:
                    if axis in clamped_params:
                        requested_pos = clamped_params[axis]
                        min_limit = build_volume.get(f'{axis.lower()}_min')
                        max_limit = build_volume.get(f'{axis.lower()}_max')

                        if min_limit is not None and requested_pos < min_limit:
                            clamped_params[axis] = min_limit
                            print(f"Warning: Clamped G1/G0 {axis} position from {requested_pos} to min limit {min_limit}.")
                            modified = True
                        elif max_limit is not None and requested_pos > max_limit:
                            clamped_params[axis] = max_limit
                            print(f"Warning: Clamped G1/G0 {axis} position from {requested_pos} to max limit {max_limit}.")
                            modified = True

        elif command == 'M204':  # Set Acceleration
            max_print_accel = self.profile.get_limit('max_acceleration_mm_per_s2.print')
            max_travel_accel = self.profile.get_limit('max_acceleration_mm_per_s2.travel')

            if 'P' in clamped_params and max_print_accel is not None:
                requested_p = clamped_params['P']
                if requested_p > max_print_accel:
                    clamped_params['P'] = max_print_accel
                    print(f"Warning: Clamped M204 P (print acceleration) from {requested_p} to {max_print_accel} mm/s^2.")
                    modified = True

            if 'T' in clamped_params and max_travel_accel is not None:
                requested_t = clamped_params['T']
                if requested_t > max_travel_accel:
                    clamped_params['T'] = max_travel_accel
                    print(f"Warning: Clamped M204 T (travel acceleration) from {requested_t} to {max_travel_accel} mm/s^2.")
                    modified = True

        elif command == 'M205':  # Set Jerk (or Junction Deviation)
            max_xy_jerk = self.profile.get_limit('max_jerk_mm_per_s.xy')
            max_z_jerk = self.profile.get_limit('max_jerk_mm_per_s.z')
            max_e_jerk = self.profile.get_limit('max_jerk_mm_per_s.e')

            if 'X' in clamped_params and max_xy_jerk is not None:
                requested_x = clamped_params['X']
                if requested_x > max_xy_jerk:
                    clamped_params['X'] = max_xy_jerk
                    print(f"Warning: Clamped M205 X (jerk) from {requested_x} to {max_xy_jerk} mm/s.")
                    modified = True
            if 'Y' in clamped_params and max_xy_jerk is not None:
                requested_y = clamped_params['Y']
                if requested_y > max_xy_jerk:
                    clamped_params['Y'] = max_xy_jerk
                    print(f"Warning: Clamped M205 Y (jerk) from {requested_y} to {max_xy_jerk} mm/s.")
                    modified = True
            if 'Z' in clamped_params and max_z_jerk is not None:
                requested_z = clamped_params['Z']
                if requested_z > max_z_jerk:
                    clamped_params['Z'] = max_z_jerk
                    print(f"Warning: Clamped M205 Z (jerk) from {requested_z} to {max_z_jerk} mm/s.")
                    modified = True
            if 'E' in clamped_params and max_e_jerk is not None:
                requested_e = clamped_params['E']
                if requested_e > max_e_jerk:
                    clamped_params['E'] = max_e_jerk
                    print(f"Warning: Clamped M205 E (jerk) from {requested_e} to {max_e_jerk} mm/s.")
                    modified = True

        elif command in ['M104', 'M109']:  # Set Hotend Temperature (M109 waits)
            max_temp = self.profile.get_limit('temperature_celsius.hotend_max')
            min_temp = self.profile.get_limit('temperature_celsius.hotend_min')

            if 'S' in clamped_params and max_temp is not None:
                requested_s = clamped_params['S']
                if requested_s > max_temp:
                    clamped_params['S'] = max_temp
                    print(f"Warning: Clamped {command} hotend temperature from {requested_s} to max {max_temp} °C.")
                    modified = True
                elif min_temp is not None and requested_s < min_temp:
                    clamped_params['S'] = min_temp
                    print(f"Warning: Raised {command} hotend temperature from {requested_s} to min {min_temp} °C.")
                    modified = True

        # You can add more commands and safety limits here as needed.

        return clamped_params, modified

    def reconstruct_gcode_line(self, command: str, params: dict, original_line: str):
        """Rebuilds a GCode line from the command and parameters, preserving comments."""
        # Extract any comment from original line
        comment_match = re.search(r'(;.*)$', original_line)
        comment = comment_match.group(1) if comment_match else ''

        # Construct parameter string sorted alphabetically by key for consistency
        param_str = ' '.join(f"{k}{format(v, '.4g')}" for k, v in sorted(params.items()))

        return f"{command} {param_str}".strip() + f" {comment}".rstrip()

    def apply_safety_limits(self, gcode_line: str):
        """Parse, clamp, and reconstruct a single GCode line."""
        command, params = self.parse_gcode_line(gcode_line)
        if command is None:
            # Line is comment or empty or unrecognized, return as-is
            return gcode_line

        clamped_params, modified = self.clamp_parameters(command, params)

        if not modified:
            return gcode_line

        return self.reconstruct_gcode_line(command, clamped_params, gcode_line)


# Example usage
if __name__ == "__main__":
    profile_path = "printer_profile.json"  # Path to your printer profile JSON

    try:
        profile = PrinterProfile(profile_path)
    except FileNotFoundError:
        print(f"Error: Profile file '{profile_path}' not found.")
        exit(1)

    limiter = SafetyLimiter(profile)

    # Example GCode lines
    lines = [
        "G1 X220 Y220 Z15 F12000 ; Move beyond max",
        "M104 S300 ; Too hot",
        "M109 S160 ; Below min temp",
        "G0 X-10 Y-5 F25000 ; Below min pos and too fast",
        "G1 E10 F5000 ; Extrude with high feedrate",
    ]

    for line in lines:
        safe_line = limiter.apply_safety_limits(line)
        print(f"Original: {line}")
        print(f"Safe    : {safe_line}\n")
# This example assumes you have a valid printer profile JSON file at the specified path.
# The JSON file should contain the necessary limits for the printer.