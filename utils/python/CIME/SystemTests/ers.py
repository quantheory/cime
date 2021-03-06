"""
CIME restart test  This class inherits from SystemTestsCommon
"""
from CIME.XML.standard_module_setup import *
from CIME.SystemTests.system_tests_common import SystemTestsCommon
from CIME.utils import run_cmd, append_status

logger = logging.getLogger(__name__)

class ERS(SystemTestsCommon):

    def __init__(self, case):
        """
        initialize an object interface to the ERS system test
        """
        SystemTestsCommon.__init__(self, case)

    def _ers_first_phase(self):
        stop_n      = self._case.get_value("STOP_N")
        stop_option = self._case.get_value("STOP_OPTION")
        expect(stop_n > 0, "Bad STOP_N: %d" % stop_n)

        # Move to config_tests.xml once that's ready
        rest_n = stop_n/2 + 1
        self._case.set_value("REST_N", rest_n)
        self._case.set_value("REST_OPTION", stop_option)
        self._case.set_value("HIST_N", stop_n)
        self._case.set_value("HIST_OPTION", stop_option)
        self._case.set_value("CONTINUE_RUN", False)
        self._case.flush()

        expect(stop_n > 2, "ERROR: stop_n value %d too short"%stop_n)
        logger.info("doing an %s %s initial test with restart file at %s %s"
                    %(str(stop_n), stop_option, str(rest_n), stop_option))
        return SystemTestsCommon.run(self)

    def _ers_second_phase(self):
        stop_n      = self._case.get_value("STOP_N")
        stop_option = self._case.get_value("STOP_OPTION")

        rest_n = stop_n/2 + 1
        stop_new = stop_n - rest_n
        expect(stop_new > 0, "ERROR: stop_n value %d too short %d %d"%(stop_new,stop_n,rest_n))

        self._case.set_value("STOP_N", stop_new)
        self._case.set_value("CONTINUE_RUN", True)
        self._case.set_value("REST_OPTION","never")
        self._case.flush()
        logger.info("doing an %s %s restart test"
                    %(str(stop_n), stop_option))
        success = SystemTestsCommon._run(self, "rest")

        # Compare restart file
        if success:
            return self._component_compare_test("base", "rest")
        else:
            return False

    def run(self):
        success = self._ers_first_phase()

        if success:
            return self._ers_second_phase()
        else:
            return False

    def report(self):
        SystemTestsCommon.report(self)
