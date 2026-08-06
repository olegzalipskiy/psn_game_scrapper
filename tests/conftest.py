import os
import sys

# Ensure the project root (where psn_client.py, csv_writer.py, psn_export.py
# live) is importable regardless of how/where pytest is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
