"""Default DropPilot entry point. The original entry point is in docs/reference."""
from multiprocessing import freeze_support
from types import SimpleNamespace as ParsedArgs
import logging.handlers
from modern_main import main

if __name__ == "__main__":
    freeze_support()
    main()
