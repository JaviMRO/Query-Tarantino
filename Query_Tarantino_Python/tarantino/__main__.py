"""python -m tarantino: the command line of SPEC 10, run from Query_Tarantino_Python/."""

import os
import sys

from src.infrastructure.entrypoints.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], os.environ))
