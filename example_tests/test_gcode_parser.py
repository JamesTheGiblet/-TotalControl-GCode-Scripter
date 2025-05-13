# example_tests/test_gcode_parser.py
import logging
import pytest

logger = logging.getLogger(__name__)

# Imagine this is a function from your TotalControl project
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
        if not part: continue
        try:
            params[part[0]] = float(part[1:])
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing parameter '{part}' in line '{line}': {e}")
            raise ValueError(f"Invalid parameter format: {part}")
    
    logger.debug(f"Parsed command: {command}, params: {params}")
    return {"command": command, "params": params}

def test_parse_g1_move():
    """Test parsing a G1 movement command."""
    line = "G1 X10 Y20.5 F3000"
    logger.info(f"Starting test_parse_g1_move with line: '{line}'")
    expected = {"command": "G1", "params": {"X": 10.0, "Y": 20.5, "F": 3000.0}}
    result = parse_gcode_line(line)
    assert result == expected
    logger.info("test_parse_g1_move PASSED")

def test_parse_empty_line():
    """Test parsing an empty line, expecting an error."""
    logger.info("Starting test_parse_empty_line")
    with pytest.raises(ValueError, match="Empty G-code line"):
        parse_gcode_line("   ")
    logger.info("test_parse_empty_line PASSED (ValueError correctly raised)")

def test_parse_invalid_param():
    """Test parsing a line with an invalid parameter."""
    line = "G1 X10 YINVALID"
    logger.info(f"Starting test_parse_invalid_param with line: '{line}'")
    with pytest.raises(ValueError, match="Invalid parameter format: YINVALID"):
        parse_gcode_line(line)
    logger.info("test_parse_invalid_param PASSED (ValueError correctly raised for invalid param)")

def test_parse_g0_move():
    """Test parsing a G0 movement command."""
    line = "G0 X5 Y10"
    logger.info(f"Starting test_parse_g0_move with line: '{line}'")
    expected = {"command": "G0", "params": {"X": 5.0, "Y": 10.0}}
    result = parse_gcode_line(line)
    assert result == expected
    logger.info("test_parse_g0_move PASSED")
