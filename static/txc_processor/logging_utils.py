"""
GitHub Actions optimized logging - shows only progress milestones
Set environment variable: VERBOSE=1 for detailed logs
"""
import os

VERBOSE = os.getenv('VERBOSE', '0') == '1'
GITHUB_ACTIONS = os.getenv('GITHUB_ACTIONS') == 'true'

def log_progress(message, force=False):
    """Log progress milestones (always shown)"""
    if force or not GITHUB_ACTIONS:
        print(message)

def log_detail(message):
    """Log details (only if VERBOSE=1)"""
    if VERBOSE:
        print(message)

def log_separator():
    """Log separator for sections"""
    if not GITHUB_ACTIONS or VERBOSE:
        print("=" * 80)
