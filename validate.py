"""
validate.py — Schema validator for extracted RISC-V architectural parameters.

Loads output.yaml and checks:
  1. Valid YAML syntax
  2. Root key is 'parameters' containing a list
  3. Each parameter has required fields (name, description, type, constraints, source)
  4. 'type' is one of the allowed classification values
  5. 'constraints' is a list (not a flat string)
  6. No fixed architectural constants leaked through (negative-test heuristic)
"""

import sys
import yaml

REQUIRED_FIELDS = {"name", "description", "type", "constraints"}
RECOMMENDED_FIELDS = {"source"}

VALID_TYPES = {
    "implementation-specific",
    "implementation-defined",
    "optional",
    "execution-environment-defined",
}

# Known architectural constants that should NEVER appear as extracted parameters.
# These serve as a negative-test heuristic to catch prompt failures.
KNOWN_CONSTANTS = {
    "csr_encoding_space",
    "csr_address_width",
    "csr_access_mode",
    "csr_privilege_level",
    "csr_lowest_privilege",
    "csr_read_write_bits",
}


def validate(filepath: str = "output.yaml") -> bool:
    """Validate the output YAML file and return True if all checks pass."""
    errors = []
    warnings = []

    # --- Load YAML ----------------------------------------------------------
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError:
        print(f"FAIL: '{filepath}' not found.")
        return False
    except yaml.YAMLError as exc:
        print(f"FAIL: Invalid YAML syntax — {exc}")
        return False

    # --- Root structure -----------------------------------------------------
    if not isinstance(data, dict) or "parameters" not in data:
        print("FAIL: Root must be a dict with key 'parameters'.")
        return False

    params = data["parameters"]
    if not isinstance(params, list):
        print("FAIL: 'parameters' must be a list.")
        return False

    if len(params) == 0:
        warnings.append("No parameters extracted (may be correct for some inputs).")

    # --- Per-parameter checks -----------------------------------------------
    for i, param in enumerate(params):
        label = param.get("name", f"parameter #{i}")

        # Required fields
        missing = REQUIRED_FIELDS - set(param.keys())
        if missing:
            errors.append(f"  [{label}] Missing required fields: {missing}")

        # Recommended fields
        missing_rec = RECOMMENDED_FIELDS - set(param.keys())
        if missing_rec:
            warnings.append(f"  [{label}] Missing recommended fields: {missing_rec}")

        # Type validation
        ptype = param.get("type", "")
        if ptype and ptype not in VALID_TYPES:
            errors.append(
                f"  [{label}] Invalid type '{ptype}'. "
                f"Must be one of: {VALID_TYPES}"
            )

        # Constraints must be a list
        constraints = param.get("constraints")
        if constraints is not None and not isinstance(constraints, list):
            errors.append(
                f"  [{label}] 'constraints' must be a YAML list, "
                f"got {type(constraints).__name__}: {str(constraints)[:80]}"
            )

        # Negative test: catch known constants
        name = param.get("name", "")
        if name.lower() in KNOWN_CONSTANTS:
            errors.append(
                f"  [{label}] This is a fixed architectural constant, "
                f"not a configurable parameter. Prompt filtering failed."
            )

    # --- Report -------------------------------------------------------------
    print(f"Validated {len(params)} parameter(s) in '{filepath}'")
    print()

    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  [!] {w}")
        print()

    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  [X] {e}")
        print()
        print(f"RESULT: FAIL ({len(errors)} error(s))")
        return False

    print("RESULT: PASS -- All checks passed.")
    return True


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "output.yaml"
    ok = validate(filepath)
    sys.exit(0 if ok else 1)
