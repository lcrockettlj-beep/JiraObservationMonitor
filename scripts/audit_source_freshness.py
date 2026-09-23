"""Execution-only wrapper for the canonical Source Health freshness owner."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from app.audits.source_freshness import main
if __name__ == '__main__':
    main()
