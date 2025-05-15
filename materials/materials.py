# c:\Users\gilbe\Documents\GitHub\-TotalControl-GCode-Scripter\materials\materials.py

# This module defines material properties for use in G-code optimization.

# Using a dictionary as a simple lookup table for material properties.
# Keys are material names (e.g., "PLA", "ABS").
# Values are dictionaries of properties.

MATERIAL_DATABASE = {
    "PLA": {
        "name": "PLA",
        "density_g_cm3": 1.24,
        "glass_transition_temp_c": 60,
        "recommended_extrusion_temp_c": {
            "min": 190,
            "default": 210,
            "max": 220
        },
        "recommended_bed_temp_c": {
            "min": 50,
            "default": 60,
            "max": 70
        },
        "viscosity_index": 1.0, # Placeholder: Higher means more viscous/resistant to flow
        "cooling_factor": 1.0,  # Placeholder: Higher means needs more cooling
        "max_volumetric_flow_rate_mm3_s": 15, # Example value for a typical 0.4mm nozzle setup
    },
    "ABS": {
        "name": "ABS",
        "density_g_cm3": 1.04,
        "glass_transition_temp_c": 105,
        "recommended_extrusion_temp_c": {
            "min": 220,
            "default": 240,
            "max": 250
        },
        "recommended_bed_temp_c": {
            "min": 90,
            "default": 100,
            "max": 110
        },
        "viscosity_index": 1.2, # Slightly more viscous than PLA in this model
        "cooling_factor": 0.5, # Needs less aggressive cooling than PLA
        "max_volumetric_flow_rate_mm3_s": 12,
    },
    "PETG": {
        "name": "PETG",
        "density_g_cm3": 1.27,
        "glass_transition_temp_c": 80,
        "recommended_extrusion_temp_c": {
            "min": 220,
            "default": 235,
            "max": 250
        },
        "recommended_bed_temp_c": {
            "min": 70,
            "default": 80,
            "max": 90
        },
        "viscosity_index": 1.1,
        "cooling_factor": 0.8,
        "max_volumetric_flow_rate_mm3_s": 14,
    }
}

def get_material_properties(material_name: str) -> dict:
    """
    Retrieves properties for a given material name from the database.
    Returns None if the material is not found.
    """
    return MATERIAL_DATABASE.get(material_name.upper()) # Ensure case-insensitivity for lookup