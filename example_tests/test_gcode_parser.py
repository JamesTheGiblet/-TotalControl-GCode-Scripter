import logging
import pytest

logger = logging.getLogger(__name__)

# Function under test (from TotalControl project)
def parse_gcode_line(line: str) -> dict:
    """Parses a simple G-code line."""
    logger.info(f"Attempting to parse G-code line: '{line}'")
    if not line.strip():
        logger.warning("Received empty G-code line.")
        raise ValueError("Empty G-code line")
    
    parts = line.upper().split()
    command = parts[0]
    params = {}

    for part in parts[1:]:
        if not part:
            continue
        try:
            params[part[0]] = float(part[1:])
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing parameter '{part}' in line '{line}': {e}")
            raise ValueError(f"Invalid parameter format: {part}")

    logger.debug(f"Parsed command: {command}, params: {params}")
    return {"command": command, "params": params}

# --- TESTS ---

def test_parse_g1_move(test_logger):
    line = "G1 X10 Y20.5 F3000"
    test_logger.info(f"Testing G1 move: '{line}'")
    expected = {"command": "G1", "params": {"X": 10.0, "Y": 20.5, "F": 3000.0}}
    result = parse_gcode_line(line)
    assert result == expected
    test_logger.info("✅ test_parse_g1_move passed")

def test_parse_empty_line(test_logger):
    test_logger.info("Testing empty G-code line")
    with pytest.raises(ValueError, match="Empty G-code line"):
        parse_gcode_line("   ")
    test_logger.info("✅ test_parse_empty_line passed")

def test_parse_invalid_param(test_logger):
    line = "G1 X10 YINVALID"
    test_logger.info(f"Testing invalid parameter: '{line}'")
    with pytest.raises(ValueError, match="Invalid parameter format: YINVALID"):
        parse_gcode_line(line)
    test_logger.info("✅ test_parse_invalid_param passed")

def test_parse_g0_move(test_logger):
    line = "G0 X5 Y10"
    test_logger.info(f"Testing G0 move: '{line}'")
    expected = {"command": "G0", "params": {"X": 5.0, "Y": 10.0}}
    result = parse_gcode_line(line)
    assert result == expected
    test_logger.info("✅ test_parse_g0_move passed")

# Optional: catch malformed or partial commands
@pytest.mark.parametrize("bad_line", [
    "G1 X",         # Missing value
    "G2 R",         # Missing number
    "M104 Sabc",    # Invalid float
    "T0 ; Comment", # Valid prefix but invalid if semicolon not handled
], ids=["missing_value", "radius_missing", "bad_float", "comment_conflict"])

def test_invalid_lines(bad_line, test_logger):
    test_logger.info(f"Testing malformed line: '{bad_line}'")
    with pytest.raises(ValueError):
        parse_gcode_line(bad_line)
    test_logger.info(f"✅ test_invalid_lines passed for: '{bad_line}'")
    # This test is expected to fail if the function does not handle the case
    # properly. Adjust the function to handle these cases if necessary.