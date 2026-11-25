"""Run the Phase 2 pipeline:  python scripts/run_pipeline.py

This tiny wrapper only makes the `src/` folder importable, then calls the real code.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from churn_analytics.pipeline import main  # noqa: E402

if __name__ == "__main__":
    main()
