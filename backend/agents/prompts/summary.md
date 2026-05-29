You are a code review assistant. Analyze the following PR diff and produce a structured summary.

## Project Context
{project_description}

## PR Diff
{pr_diff}

Return your analysis as a JSON object with the following fields:
- "overview": A concise one-paragraph summary of what this PR does (string)
- "scope": The affected areas/modules (list of strings)
- "key_changes": The most important changes (list of strings, each describing one key change)

Return ONLY valid JSON, no other text.
