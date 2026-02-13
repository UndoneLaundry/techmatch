import re

def compute_common_flags(name_or_company: str):
    flags = []
    # Suspicious formatting: too many repeated chars, or lots of punctuation
    if re.search(r"(.)\1\1\1", name_or_company):
        flags.append(("SUSPICIOUS_NAME_FORMAT", "MEDIUM", "Repeated characters pattern detected."))
    if re.search(r"[^A-Za-z\s\-\']", name_or_company):
        flags.append(("SUSPICIOUS_NAME_FORMAT", "HIGH", "Contains disallowed characters."))
    if len(name_or_company.strip()) > 50:
        flags.append(("SUSPICIOUS_NAME_FORMAT", "LOW", "Unusually long name/company string."))
    return flags

def compute_technician_flags(skills_list):
    flags = []
    if len(skills_list) >= 12:
        flags.append(("UNUSUALLY_LONG_SKILLS_LIST", "LOW", "Very large skills list."))
    # repeated phrases
    joined = " ".join(skills_list).lower()
    if joined.count("repair") >= 5:
        flags.append(("REPEATED_PHRASES", "LOW", "Repeated phrases in skills detected."))
    return flags
