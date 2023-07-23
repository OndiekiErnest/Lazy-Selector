""" simple code profile decorator function """

import cProfile
import pstats
import io


def profile_function(function):
    """
    decorator function that uses cProfile
    to print cumulative code execution times
    """
    def inner(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        # run the code here
        retval = function(*args, **kwargs)
        pr.disable()
        s = io.StringIO()
        sortby = "cumulative"
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        print(s.getvalue())
        return retval

    return inner
