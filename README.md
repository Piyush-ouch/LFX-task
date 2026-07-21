# AI-Assisted Extraction of Architectural Parameters from RISC-V Specifications
### LFX Mentorship Coding Challenge

An automated NLP/LLM pipeline designed to parse RISC-V ISA specification text snippets, identify implementation-specific and configurable architectural parameters, filter out fixed architectural constants, and produce structured, validated YAML output.

---

## 📌 Project Overview

When developing hardware, emulators, compilers, or verification suites for the **RISC-V ISA**, hardware engineers need to extract configurable architectural parameters (e.g., cache sizes, optional extensions, implementation-defined register behaviors) from official specification documents.

This project automates that process using Large Language Models (LLMs) and structured prompt constraints.

### Key Objectives
1. **Automated Extraction**: Read raw RISC-V ISA specification text (`input.txt`).
2. **Precision Parameter Filtering**: Distinguish between *configurable/implementation-defined parameters* (e.g., cache capacity, cache block size) and *fixed architectural constants* (e.g., CSR bit encoding rules).
3. **Structured Export**: Validate and output clean YAML adhering to a strict schema (`output.yaml`).

---

## 🤖 LLM Details & Model Selection

| Metric | Primary LLM (Google Gemini) | Fallback LLM (OpenAI) |
| :--- | :--- | :--- |
| **Model Name** | `gemini-3.5-flash` / `gemini-2.0-flash-lite` | `gpt-4o-mini` |
| **Developer / Provider** | Google DeepMind | OpenAI |
| **Context Length** | ~1,048,576 tokens (1M) | 128,000 tokens |
| **Temperature** | `0` (Deterministic Output) | `0` (Deterministic Output) |
| **API Interface** | OpenAI REST API Compatibility (`v1beta/openai/`) | Native OpenAI Chat Completions API |

---

## 💡 Prompt Strategy & Hallucination Mitigation

### A. Keyword Triggering Rules
In the RISC-V ISA manual, configurable parameters are explicitly signaled by specific keywords:
- `"implementation-specific"` / `"implementation-defined"`
- `"may"` / `"might"` / `"should"`
- `"optional"` / `"optionally"`
- `"execution environment provides software a means to discover"`

### B. Hallucination Prevention
1. **Contextual Grounding Directive**: Forced every parameter to be explicitly present in the provided spec text (`"Do NOT invent parameters"`).
2. **Negative Rules**: Instructed the LLM to explicitly ignore fixed architectural constants (such as static CSR bit allocations in Privileged Spec 2.1).
3. **Deterministic Sampling**: Set `temperature: 0` to eliminate non-deterministic sampling variance.
4. **Schema Validation**: Verified response structure via `PyYAML` parsing before writing `output.yaml`.

---

## 📁 Repository Structure

```
LFX_Coding_Challenge/
│
├── extractor.py       # Core Python script: reads input, queries LLM, cleans & validates YAML output
├── input.txt          # Input text file containing RISC-V specification snippets
├── output.yaml        # Generated output containing extracted architectural parameters
├── requirements.txt   # Python package dependencies
├── .env.example       # Environment template for API keys and configuration
├── .gitignore         # Ignores sensitive keys and submission scratch files
└── README.md          # Repository overview and setup guide
```

---

## 🛠️ Quick Start & Execution

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Key (`.env`)**:
   Copy `.env.example` to `.env` and insert your key:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   # OR
   OPENAI_API_KEY=your_openai_api_key
   ```

3. **Run Parameter Extraction**:
   ```bash
   python extractor.py
   ```
   *(To run in offline demonstration mode without an API key, use `python extractor.py --mock`)*.

---

## 📄 Output Result (`output.yaml`)

```yaml
parameters:
  - name: cache_capacity
    description: The capacity of a cache in the system.
    type: integer
    constraints: Implementation-specific.
  - name: cache_organization
    description: The organization of a cache in the system.
    type: string
    constraints: Implementation-specific.
  - name: cache_block_size
    description: The size of a cache block.
    type: integer
    constraints: Implementation-specific. Must represent a contiguous, naturally aligned power-of-two (NAPOT) range of memory locations. In the initial set of CMO extensions, the size of a cache block shall be uniform throughout the system.
```
