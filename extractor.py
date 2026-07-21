"""
AI-Assisted RISC-V Architectural Parameter Extractor

Reads RISC-V specification snippets from input.txt, sends them to an LLM
with a carefully engineered system prompt, validates the response, and
saves extracted parameters as structured YAML.

Supports Google Gemini (free tier) and OpenAI as LLM backends.
"""

import logging
import os
import sys

import yaml
from dotenv import load_dotenv
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompt  (v3 — production)
#
# Evolution notes
#   v1  prompts/v1_naive.txt      — "Extract parameters …" → hallucinated CSR constants
#   v2  prompts/v2_keyword.txt    — added trigger-word list → inconsistent type field
#   v3  (below)                   — 1-shot example + negative rules + source tracing
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert RISC-V ISA specification analyst.

TASK
----
Extract **only** configurable architectural parameters from the provided
RISC-V specification text.

WHAT COUNTS AS A PARAMETER
---------------------------
A parameter must be explicitly described in the text using language such as:
  • "implementation-defined" or "implementation-specific"
  • "optional" / "optionally"
  • "may" / "might" / "should"
  • "execution environment provides … a means to discover"

WHAT IS **NOT** A PARAMETER
-----------------------------
Do NOT extract:
  • Fixed architectural constants (e.g. "12-bit encoding space")
  • Mandatory ISA encoding rules (e.g. CSR address bit allocations)
  • Static bit-field definitions that are identical across all implementations

RULES
-----
1. Every parameter you output MUST appear explicitly in the input text.
2. Do NOT invent, infer, or hallucinate parameters.
3. The `type` field must be one of: implementation-specific, implementation-defined, optional, or execution-environment-defined.
4. The `constraints` field must be a YAML list of individual constraint strings.
5. Include a `source` field with the specification section reference.

OUTPUT FORMAT
-------------
Return ONLY valid YAML matching the schema below.  No markdown fences, no
commentary, no extra text.

parameters:
  - name: <snake_case name>
    description: <one-line description>
    type: <implementation-specific | implementation-defined | optional | execution-environment-defined>
    constraints:
      - <constraint 1>
      - <constraint 2>
    source: <spec section reference, e.g. "Privileged Spec 19.3.1">

EXAMPLE
-------
Given input containing "The reset vector address is implementation-defined
and must be aligned to a 4-byte boundary (Privileged Spec 3.4)", you would
output:

parameters:
  - name: reset_vector_address
    description: Address of the first instruction fetched after reset.
    type: implementation-defined
    constraints:
      - Must be aligned to a 4-byte boundary
    source: "Privileged Spec 3.4"
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def strip_markdown_fences(text: str) -> str:
    """Remove ```yaml … ``` wrappers that some LLMs add despite instructions."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def validate_yaml(content: str) -> dict:
    """Parse YAML string and validate it has the expected schema structure."""
    data = yaml.safe_load(content)

    if not isinstance(data, dict) or "parameters" not in data:
        raise ValueError("YAML root must contain a 'parameters' key")

    params = data["parameters"]
    if not isinstance(params, list):
        raise ValueError("'parameters' must be a list")

    required_fields = {"name", "description", "type", "constraints"}
    valid_types = {
        "implementation-specific",
        "implementation-defined",
        "optional",
        "execution-environment-defined",
    }

    for i, param in enumerate(params):
        missing = required_fields - set(param.keys())
        if missing:
            log.warning("Parameter %d missing fields: %s", i, missing)

        ptype = param.get("type", "")
        if ptype not in valid_types:
            log.warning(
                "Parameter '%s' has non-standard type '%s' (expected one of %s)",
                param.get("name", f"#{i}"),
                ptype,
                valid_types,
            )

    return data


def build_client():
    """
    Detect API keys and return (client, model_name, provider_label).
    Priority: GEMINI_API_KEY > OPENAI_API_KEY.
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if gemini_key:
        base_url = os.getenv(
            "OPENAI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        model = os.getenv("OPENAI_MODEL", "gemini-2.0-flash-lite")
        client = OpenAI(api_key=gemini_key, base_url=base_url)
        return client, model, f"Google Gemini ({model})"

    if openai_key:
        base_url = os.getenv("OPENAI_BASE_URL")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        kwargs = {"api_key": openai_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)
        return client, model, f"OpenAI ({model})"

    return None, None, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    input_file = os.getenv("INPUT_FILE", "input.txt")
    output_file = os.getenv("OUTPUT_FILE", "output.yaml")

    # --- Build LLM client ---------------------------------------------------
    client, model_name, provider = build_client()
    if client is None:
        log.error(
            "No API key found. Set GEMINI_API_KEY or OPENAI_API_KEY in .env"
        )
        log.info("Tip: Run 'python extractor.py --mock' for offline demo.")
        sys.exit(1)

    # --- Read specification --------------------------------------------------
    if not os.path.exists(input_file):
        log.error("Input file '%s' not found.", input_file)
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as fh:
        specification = fh.read()
    log.info("Read %d chars from %s", len(specification), input_file)

    # --- Call LLM ------------------------------------------------------------
    log.info("Sending request to %s …", provider)
    try:
        response = client.chat.completions.create(
            model=model_name,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": specification},
            ],
        )
    except Exception as exc:
        log.error("API call failed: %s", exc)
        if "429" in str(exc) or "quota" in str(exc).lower():
            log.info("This is a rate-limit / quota error.")
            log.info("  → Add billing credits, or try a different model.")
        sys.exit(1)

    raw = response.choices[0].message.content
    cleaned = strip_markdown_fences(raw)

    # --- Validate & save ----------------------------------------------------
    try:
        data = validate_yaml(cleaned)
    except Exception as exc:
        log.warning("Validation issue: %s — saving raw output anyway.", exc)
        data = None

    with open(output_file, "w", encoding="utf-8") as fh:
        fh.write(cleaned + "\n")

    n_params = len(data["parameters"]) if data else "?"
    log.info("Extracted %s parameters → %s", n_params, output_file)
    print()
    print(cleaned)


if __name__ == "__main__":
    main()
