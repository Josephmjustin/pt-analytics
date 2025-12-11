#!/usr/bin/env python3
"""
Standalone ingestion script for cron
"""
import sys
import os

# Add project paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.append(os.path.join(project_root, 'scripts'))

import continuous_poller

if __name__ == "__main__":
    try:
        continuous_poller.poll_and_ingest()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
