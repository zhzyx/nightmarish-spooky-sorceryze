"""Run the native read-only review contract in a separate ordinary game repository.

Reuses the same real editor controls, source-drift and adversarial-tool scenarios
as engine review. Only the model/GitHub transports are controlled fixtures.
"""

import run_design_batch as batch

batch.GAME_WORKSPACE = True

if __name__ == "__main__":
    raise SystemExit(batch.main())
