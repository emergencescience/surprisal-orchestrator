#!/usr/bin/env bash
# generate_cpcc_submission.sh
# Concatenates backend python and javascript files into a single text document
# and extracts the first 30 pages and the last 30 pages (assuming 50 lines = 1 page).
# The CPCC requires continuous pages, so we concatenate them logically.

set -e

WORKSPACE_DIR="/Users/julian/gitbubble/emergence"
OUTPUT_FILE="${WORKSPACE_DIR}/apps/surprisal-orchestrator/cpcc_source_code_full.txt"
FINAL_PDF_TXT="${WORKSPACE_DIR}/apps/surprisal-orchestrator/cpcc_submission_60_pages.txt"

echo "Generating Full Codebase Concatenation..."

# Clear if exists
> "$OUTPUT_FILE"

# Function to append file contents with headers
append_file() {
    local file_path=$1
    if [ -f "$file_path" ]; then
        echo -e "\n\n/* ========================================================================= " >> "$OUTPUT_FILE"
        echo "   FILE: $(basename "$file_path")" >> "$OUTPUT_FILE"
        echo -e "   ========================================================================= */\n" >> "$OUTPUT_FILE"
        cat "$file_path" >> "$OUTPUT_FILE"
    fi
}

# 1. Highest Priority Files (Will be in the first 30 pages)
# Models and Services
append_file "${WORKSPACE_DIR}/apps/surprisal-orchestrator/core/models.py"
append_file "${WORKSPACE_DIR}/apps/surprisal-orchestrator/services/bounty_service.py"
append_file "${WORKSPACE_DIR}/apps/surprisal-orchestrator/services/execution.py"
append_file "${WORKSPACE_DIR}/apps/surprisal-orchestrator/routes/bounties.py"

# 2. Append the rest of the orchestrator files (excluding venv, migrations, etc.)
find "${WORKSPACE_DIR}/apps/surprisal-orchestrator" -type f -name "*.py" | grep -v "venv" | grep -v "__pycache__" | grep -v "tests/" | while read -r file; do
    # Skip if already appended
    if [[ ! "$file" =~ (models\.py|bounty_service\.py|execution\.py|routes/bounties\.py)$ ]]; then
        append_file "$file"
    fi
done

echo "Code concatenated to $OUTPUT_FILE"

# 3. Calculate lines and extract the 60-page requirement
# CPCC assumes 50 lines of code per page.
# 30 pages = 1500 lines.
TOTAL_LINES=$(wc -l < "$OUTPUT_FILE")

echo "Total lines of code: $TOTAL_LINES"

> "$FINAL_PDF_TXT"

if [ "$TOTAL_LINES" -lt 3000 ]; then
    echo "Total lines is less than 3000 (60 pages). Submitting the entire codebase."
    cp "$OUTPUT_FILE" "$FINAL_PDF_TXT"
else
    echo "Total lines > 3000. Extracting first 1500 lines and last 1500 lines..."
    head -n 1500 "$OUTPUT_FILE" > "$FINAL_PDF_TXT"
    echo -e "\n... [MIDDLE SECTION OMITTED FOR CPCC SUBMISSION] ...\n" >> "$FINAL_PDF_TXT"
    tail -n 1500 "$OUTPUT_FILE" >> "$FINAL_PDF_TXT"
fi

echo "Success! The final 60-page text sample is located at: $FINAL_PDF_TXT"
echo "You can convert $FINAL_PDF_TXT to PDF and submit along with your docs/*-zh.md PDFs."
