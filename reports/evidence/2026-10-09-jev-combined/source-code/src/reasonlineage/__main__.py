"""`python -m reasonlineage` runs the same commands as the `reasonlineage` script."""

import sys

from .cli import main

sys.exit(main())
