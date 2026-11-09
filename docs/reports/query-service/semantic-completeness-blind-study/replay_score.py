"""JSON-boundary replay of the unchanged frozen scorer, no admission/gate change.

The first score.py execution stopped on U2/r1 because in-memory comparison keys
are tuples but retained JSON decodes them as lists. Normalize ONLY that transport
representation before its exact replay assertion. All verdicts, comparisons,
thresholds, reference checks and scoring code remain the frozen implementation.
"""
import json

import score


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    frozen_pair_decision = score.pair_decision

    def json_boundary(*args, **kwargs):
        return json.loads(json.dumps(frozen_pair_decision(*args, **kwargs)))

    score.pair_decision = json_boundary
    score.main(args.output)
