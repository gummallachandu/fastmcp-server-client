Dynamic Coder Agent Overlay: Implementation with Coding Standards
1. Prompt Storage (S3)

Base Coder Prompt:

s3://prompts/coder/base_v1.json

Tech Stack Overlays:

s3://prompts/coder/stack/python_v1.json

s3://prompts/coder/stack/react_v1.json

etc.

Coding Standards Overlays (by org/team/project):

s3://prompts/coder/coding_standard/pep8_v1.json

s3://prompts/coder/coding_standard/google_v1.json

s3://prompts/coder/coding_standard/internal_v1.json

etc.

2. Context Extraction

Supervisor agent derives context:

tech_stack

coding_standard

project_type, user_preferences

Normalize fields to match overlay files.

3. Prompt Assembly

Fetch base prompt from S3.

Fetch tech stack overlay from S3.

Fetch coding standard overlay from S3 (default to org/team/project standard if none specified).

Concatenate as:

base prompt

tech stack overlay

coding standard overlay

Inject project variables (e.g., {project_name}) as needed.

4. Agent Dispatch

Pass fully assembled prompt to Coder agent.

Coder agent outputs code adhering to tech stack and coding standard guidelines.

5. Logging & Governance

Log:

Used prompt versions/overlays (base, stack, coding standard)

Context parameters

Output/code artifact



Summary Flow

Receive project context (tech_stack, coding_standard)

Normalize and select overlays

Fetch base, stack, and coding standard prompts from S3

Merge components (base → stack → coding standard)

Dispatch to Coder agent

Log overlays, versions, and output

Outcome:
The Coder agent’s behavior is tailored per project with:

Base developer persona

Correct tech stack best practices

Explicit coding standard guidelines
All merged dynamically for each run, ensuring output consistency and quality.
