from concurrent.futures import ThreadPoolExecutor, wait
from cocoscrapers.modules import log_utils

# Init global thread pool
tp = ThreadPoolExecutor(max_workers=10)
_shutdown = False  # Track shutdown state


def run_and_wait(func, iterable):
    futures = []
    for item in iterable:
        # Submit each task to the thread pool
        future = tp.submit(func, item)
        futures.append(future)
    # Wait for all tasks to complete
    wait(futures)


def run_and_wait_multi(func, iterable):
    results = tp.map(lambda args: func(*args), iterable)
    return results


def shutdown_executor():
    global _shutdown
    if not _shutdown:
        try:
            tp.shutdown(wait=True)
            _shutdown = True
            log_utils.log('ThreadPool shutdown complete', log_utils.LOGINFO)
        except Exception as e:
            log_utils.log(f'ThreadPool shutdown failed: {e}', log_utils.LOGWARNING)
    else:
        log_utils.log('ThreadPool already shut down, skipping', log_utils.LOGDEBUG)
