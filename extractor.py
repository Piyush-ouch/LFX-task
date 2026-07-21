"""
AI-assisted RISC-V Architectural Parameter Extractor

Reads a specification snippet from input.txt,
sends it to an LLM, and saves the extracted parameters as YAML.
"""

import os
import sys
import yaml
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env if present
load_dotenv()

SYSTEM_PROMPT = """
You are an expert RISC-V ISA analyst.

Your task is to extract architectural parameters from the provided RISC-V specification.

A parameter should be extracted when it represents:

- implementation-defined behavior
- implementation-specific behavior
- optional features
- configurable architectural properties
- privilege-dependent architectural fields
- execution environment dependent properties

Do NOT invent parameters.

Every extracted parameter must appear explicitly in the specification.

Return ONLY valid YAML.

Schema:

parameters:
  - name:
    description:
    type:
    constraints:
"""


def clean_yaml_output(raw_content: str) -> str:
    """Strips Markdown backtick fences if present in LLM output."""
    content = raw_content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        # Remove opening ```yaml or ``` line
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove closing ``` line if present
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return content


def main():
    input_file = "input.txt"
    output_file = "output.yaml"

    # Check for --mock flag for offline evaluation/testing
    is_mock = "--mock" in sys.argv or os.getenv("MOCK_MODE", "").lower() == "true"

    if is_mock:
        print("[MOCK MODE] Running offline parameter extraction demonstration...")
        if not os.path.exists(input_file):
            print(f"Error: '{input_file}' not found.")
            sys.exit(1)

        print(f"Reading specification from {input_file}...")
        mock_output = """parameters:
  - name: cache_capacity
    description: Total capacity of the cache.
    type: implementation-specific
    constraints:
      - Determined by the hardware implementation
      - Discoverable through the execution environment

  - name: cache_organization
    description: Structural organization of the cache.
    type: implementation-specific
    constraints:
      - Determined by the hardware implementation
      - Discoverable through the execution environment

  - name: cache_block_size
    description: Size of an individual cache block.
    type: implementation-specific
    constraints:
      - Uniform throughout the system in the initial set of CMO extensions
      - Represents a contiguous, naturally aligned power-of-two (NAPOT) memory range
      - Discoverable through the execution environment"""

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(mock_output)

        print("Extraction completed successfully (Mock Mode).")
        print(f"Extracted parameters written to {output_file}:\n")
        print(mock_output)
        return

    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if gemini_key:
        api_key = gemini_key
        base_url = os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
        model_name = os.getenv("OPENAI_MODEL", "gemini-3.5-flash")
        provider_info = f"Google Gemini API (Model: {model_name})"
        client = OpenAI(api_key=api_key, base_url=base_url)
    elif openai_key:
        api_key = openai_key
        base_url = os.getenv("OPENAI_BASE_URL")
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        provider_info = f"OpenAI API (Model: {model_name})"
        if base_url:
            client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            client = OpenAI(api_key=api_key)
    else:
        print("Error: No API key found (neither GEMINI_API_KEY nor OPENAI_API_KEY is set).")
        print("Please set your API key in a .env file:")
        print("  - For Google Gemini (Free Tier): GEMINI_API_KEY=your_gemini_key")
        print("  - For OpenAI:                    OPENAI_API_KEY=your_openai_key")
        print("\nTip: Run 'python extractor.py --mock' for offline demonstration mode.")
        sys.exit(1)

    if not os.path.exists(input_file):
        print(f"Error: '{input_file}' not found.")
        sys.exit(1)

    print(f"Reading specification from {input_file}...")
    with open(input_file, "r", encoding="utf-8") as f:
        specification = f.read()

    print(f"Sending request to {provider_info}...")
    try:
        response = client.chat.completions.create(
            model=model_name,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": specification},
            ],
        )

        raw_output = response.choices[0].message.content
        yaml_output = clean_yaml_output(raw_output)

        # Validate that output is valid YAML
        try:
            parsed_data = yaml.safe_load(yaml_output)
            if not isinstance(parsed_data, dict) or "parameters" not in parsed_data:
                print("Warning: Generated output did not contain the expected 'parameters' root key.")
        except yaml.YAMLError as ye:
            print(f"Warning: Output generated by LLM was not valid YAML: {ye}")

        # Save extracted parameters to output.yaml
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(yaml_output)

        print("Extraction completed successfully.")
        print(f"Extracted parameters written to {output_file}:\n")
        print(yaml_output)

    except Exception as e:
        err_msg = str(e)
        print(f"An error occurred during API execution: {err_msg}")
        if "insufficient_quota" in err_msg or "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            print("\n[API Quota / Rate Limit Exceeded Error]")
            if gemini_key:
                print("Your Google Gemini API Key encountered a rate limit / quota restriction.")
                print("Solutions:")
                print("  1. Verify your Gemini API key project limits at https://aistudio.google.com/ app settings.")
                print("  2. You can set OPENAI_MODEL=gemini-2.0-flash-lite in your .env file.")
                print("  3. Or test offline demonstration mode using: python extractor.py --mock")
            else:
                print("Your OpenAI account currently has $0 available credit balance.")
                print("Creating a new API key on an account with $0 balance will still return HTTP 429.")
                print("Solutions:")
                print("  1. Add prepaid billing credits ($5) at https://platform.openai.com/settings/organization/billing")
                print("  2. Or test in offline demonstration mode using: python extractor.py --mock")
        sys.exit(1)


if __name__ == "__main__":
    main()

