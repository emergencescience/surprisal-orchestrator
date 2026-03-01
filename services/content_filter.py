import re

from fastapi import HTTPException

# Layer 1: The "Reflex" Engine Blocklist
BLOCKLIST = {
    # Hate / Bias
    "hate",
    "racist",
    "nazi",
    "fascist",
    "slave",
    "stupid",
    "idiot",
    "ugly",
    "fat",
}

# Layer 2: DLP (Data Loss Prevention) Regex Patterns
DLP_PATTERNS = {
    "OpenAI API Key": r"sk-[a-zA-Z0-9]{30,}",
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Private Key (Generic)": r"-----BEGIN PRIVATE KEY-----",
    "Email Address": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
}


class ContentRuleEngine:
    @staticmethod
    def validate(text: str):
        """
        Validates the text against blocklist and DLP patterns.
        Raises HTTPException(400) if a violation is found.
        """
        if not text:
            return

        # Normalize text: lowercase and remove simple punctuation for checking
        normalized_text = text.lower()

        # 1. Blocklist Check
        for word in BLOCKLIST:
            # Use regex to match whole words only to avoid false positives (e.g., "skill" containing "kill")
            if re.search(r"\b" + re.escape(word) + r"\b", normalized_text):
                raise HTTPException(status_code=400, detail=f"Content Violation: The word '{word}' is prohibited by the Harmonic Rule Engine.")

        # 2. DLP Check (Confidential Information)
        for name, pattern in DLP_PATTERNS.items():
            if re.search(pattern, text):
                raise HTTPException(status_code=400, detail=f"Security Violation: Your post contains a potential {name}. Please remove confidential data.")

        return True
