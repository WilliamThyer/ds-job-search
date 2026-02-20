"""Utility functions for job filtering and detection."""

import re
from typing import Optional


# Barcelona location patterns
BARCELONA_PATTERNS = [
    r'\bbarcelona\b',
    r'\bbcn\b',
    r'\bspain\b.*\bremote\b',
    r'\bremote\b.*\bspain\b',
    r'\bhybrid\b.*\bbarcelona\b',
    r'\bbarcelona\b.*\bhybrid\b',
]

# Data role keywords (broad for high recall)
DATA_ROLE_KEYWORDS = [
    'data scientist',
    'data analyst',
    'data engineer',
    'machine learning',
    'ml engineer',
    'ai engineer',
    'artificial intelligence',
    'analytics engineer',
    'applied scientist',
    'research scientist',
    'deep learning',
    'nlp engineer',
    'computer vision',
    'data science',
]

# Great fit keywords (strict - core DS/ML/AI roles only)
GREAT_FIT_KEYWORDS = [
    'data scientist',
    'data science',
    'machine learning engineer',
    'ml engineer',
    'mle',
    'data analyst',
    'ai engineer',
    'applied scientist',
    'research scientist',
    'deep learning',
    'nlp engineer',
    'computer vision engineer',
    'artificial intelligence',
]

# Keywords that disqualify a role from being a "great fit"
GREAT_FIT_EXCLUSIONS = [
    'intern',
    'internship',
    'product manager',
    'product owner',
    'software engineer',
    'software developer',
    'backend engineer',
    'frontend engineer',
    'full stack',
    'fullstack',
    'devops',
    'sre',
    'site reliability',
    'account manager',
    'sales',
    'marketing',
    'recruiter',
    'hr ',
    'human resources',
    'content',
    'designer',
    'ux ',
    'ui ',
    'customer success',
    'support engineer',
    'qa engineer',
    'test engineer',
    'project manager',
    'program manager',
    'business analyst',
    'financial analyst',
    'junior',  # Often indicates entry-level non-DS
]

# Keywords that suggest visa/relocation support
VISA_KEYWORDS = [
    'visa sponsorship',
    'visa sponsor',
    'work permit',
    'work authorization',
    'relocation support',
    'relocation package',
    'relocation assistance',
    'willing to relocate',
    'help with relocation',
]

RELOCATION_KEYWORDS = [
    'relocation',
    'relocate',
    'moving assistance',
    'moving package',
]

# Non-English indicators (Spanish/Catalan)
NON_ENGLISH_PATTERNS = [
    r'\bsomos\b',
    r'\bbuscamos\b',
    r'\bempresa\b',
    r'\btrabajo\b',
    r'\bexperiencia\b',
    r'\brequisitos\b',
    r'\bresponsabilidades\b',
    r'\bofrecemos\b',
    r'\bcientífico de datos\b',
    r'\bingeniero\b',
    r'\banalista\b',
    r'\bcerquem\b',  # Catalan
    r'\bfeina\b',    # Catalan
]


def is_barcelona_role(location: Optional[str], title: str, description: str) -> bool:
    """
    Check if job is Barcelona-based.
    Handles: "Barcelona", "Barcelona, Spain", "Remote - Spain", "Hybrid - Barcelona"
    """
    text = f"{location or ''} {title} {description}".lower()

    for pattern in BARCELONA_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


def is_data_role(title: str, description: str) -> bool:
    """
    Check if job is data-related (broad filter for high recall).
    Includes: Data Scientist, Data Analyst, Data Engineer, ML Engineer,
              AI Engineer, Analytics Engineer, Machine Learning, Applied Scientist
    Bias toward inclusion - accept false positives to avoid missing opportunities.
    """
    text = f"{title} {description}".lower()

    for keyword in DATA_ROLE_KEYWORDS:
        if keyword in text:
            return True

    return False


def is_great_fit(title: str, description: str = "") -> bool:
    """
    Check if job is a great fit (core DS/ML/AI role).
    More strict than is_data_role - excludes internships, PMs, SWEs, etc.
    Based primarily on title, with description as tiebreaker.
    """
    title_lower = title.lower()

    # Check for exclusions first (in title only)
    for exclusion in GREAT_FIT_EXCLUSIONS:
        if exclusion in title_lower:
            return False

    # Check for great fit keywords in title
    for keyword in GREAT_FIT_KEYWORDS:
        if keyword in title_lower:
            return True

    # Fallback: check description if title didn't match
    if description:
        desc_lower = description.lower()
        # Only match if strong signal in description AND no exclusions
        strong_signals = ['data scientist', 'machine learning engineer', 'ml engineer', 'data analyst']
        for signal in strong_signals:
            if signal in desc_lower:
                return True

    return False


def is_english_posting(title: str, description: str) -> bool:
    """
    Filter to English-language postings only.
    Excludes Spanish/Catalan postings.
    """
    text = f"{title} {description}".lower()

    # Count non-English indicators
    non_english_count = 0
    for pattern in NON_ENGLISH_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            non_english_count += 1

    # If multiple non-English indicators, likely not English
    return non_english_count < 3


def detect_visa_mentions(description: str) -> tuple[bool, bool]:
    """
    Returns (mentions_visa, mentions_relocation).
    Searches for: "visa sponsorship", "work permit", "relocation package", etc.
    """
    text = description.lower()

    mentions_visa = any(kw in text for kw in VISA_KEYWORDS)
    mentions_relocation = any(kw in text for kw in RELOCATION_KEYWORDS)

    return mentions_visa, mentions_relocation
