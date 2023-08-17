#
# dispatcher.py
#
#   Dispatcher class that encapsulates automation and invocation of registered
#   functions at predefined time intervals.
#   This class is intended to be simple and no attempt was made at timing accuracy.
#   Functions will be called if the predefined time interval is greater or equal
#   to the time delta of the function's last invocation
#

import time

class Dispatcher:
    """Dispatcher class, encapsulates automation and invocation of registered functions at defined time intervals."""

    def __init__(self, param_init={}):
        """Initialize the dispatch table with the function identification and call interval."""

        self.shared_parameters = param_init
        self.dispatch_table = {}

    def register(self, func_ref_name, function, call_interval):
        """Register a function with the dispatcher instance."""

        temp_function_def = {"function":function, "call_interval":call_interval, "last_invocation_time":0.0}
        self.dispatch_table[func_ref_name] = temp_function_def

    def unregister(self, func_ref_name):
        """Unregister and remove a function from the dispatcher list"""

        if func_ref_name in self.__dispatch_table:
            del self.dispatch_table[func_ref_name]

    def show(self, func_ref_name=None):
        """Print out the registration information of a function."""

        if func_ref_name:
            if func_ref_name in self.__dispatch_table:
                print self.dispatch_table[func_ref_name]
            else:
                print 'Function {} not registered.'.format(func_ref_name)
        else:
            for name in self.dispatch_table:
                print self.dispatch_table[name]

    def dispatch(self):
        """
        Should be called periodically and as often as possible to invoke registered functions.
        Timing interval accuracy of dispatched functions is directly related to how often this function is called.
        Call at an interval of less than half of the shortest invocation interval of all registered functions,
        for example: if shortest invocation interval is 2sec, call dispatch() every 1sec or less.
        """

        for function in self.dispatch_table:
            self.function_param = self.dispatch_table[function]
            self.time_now = time.time()

            if self.time_now - self.function_param['last_invocation_time'] >= self.function_param['call_interval']:
                self.function_param['last_invocation_time'] = self.time_now
                self.function_param['function'](self.shared_parameters)
