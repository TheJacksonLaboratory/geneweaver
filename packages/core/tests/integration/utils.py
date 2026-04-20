"""Utilities for integration tests."""

import time
from collections.abc import Callable, Sequence


def call_function(func: Callable, num_times: int, rate: int, iterate_args: Sequence | None):
    """Call 'func' 'num_times' times at 'rate' times per second."""
    results = []

    for i in range(num_times):
        start_time = time.time()
        results.append(func(iterate_args[i]) if iterate_args else func())
        time.sleep(max(1 / rate - (time.time() - start_time), 0))

    return results
