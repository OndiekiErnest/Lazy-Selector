<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> d36391c7013cb6b9ef61944bc1620bd6ba942f04
""" simple code profile decorator function """

import cProfile
import pstats
import io


def profile_function(function):
    """
    decorator function that uses cProfile
    to print cumulative code execution times
    """
<<<<<<< HEAD

=======
>>>>>>> d36391c7013cb6b9ef61944bc1620bd6ba942f04
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
<<<<<<< HEAD
=======
=======
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
>>>>>>> a4e48a141439482a4b6694fbb454ee0b61de7240
>>>>>>> d36391c7013cb6b9ef61944bc1620bd6ba942f04
