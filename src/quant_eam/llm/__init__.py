"""LLM plumbing: provider abstraction + cassette replay + redaction.

This package must not perform any network IO by default. Tests should use mock + replay modes.
"""

