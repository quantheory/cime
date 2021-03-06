"""
CIME ERI test  This class inherits from SystemTestsCommon
"""
from CIME.XML.standard_module_setup import *
from CIME.SystemTests.system_tests_common import SystemTestsCommon
from CIME.utils import run_cmd

import shutil, glob, os

logger = logging.getLogger(__name__)

def _helper(dout_sr, refdate, ref_to_d, rundir):
    rest_path = os.path.join(dout_sr, "rest", "%s-%s" % (refdate, ref_to_d))

    for item in glob.glob("%s/*%s*" % (rest_path, refdate)):
        os.symlink(item, os.path.join(rundir, os.path.basename(item)))

    for item in glob.glob("%s/*rpointer*" % rest_path):
        shutil.copy(item, rundir)

class ERI(SystemTestsCommon):

    def __init__(self, case):
        """
        initialize an object interface to the ERI system test
        """
        SystemTestsCommon.__init__(self, case)
        self._testname = "ERI"

    def run(self):
        caseroot = self._case.get_value("CASEROOT")
        clone1_path = "%s.ref1" % caseroot
        clone2_path = "%s.ref2" % caseroot
        #self._case.set_value("CHECK_TIMING", False)

        #
        # clone the main case to create ref1 and ref2 cases
        #
        clones = []
        for clone_path in [clone1_path, clone2_path]:
            if os.path.exists(clone_path):
                shutil.rmtree(clone_path)

            clones.append(self._case.create_clone(clone_path, keepexe=True))

        clone1, clone2 = clones
        orig_case = self._case
        orig_casevar = orig_case.get_value("CASE")

        #
        # determine run lengths needed below
        #
        stop_n = self._case.get_value("STOP_N")
        stop_option = self._case.get_value("STOP_OPTION")
        run_startdate = self._case.get_value("RUN_STARTDATE")

        stop_n1 = stop_n / 6
        rest_n1 = stop_n1
        start_1 = run_startdate

        stop_n2 = stop_n - stop_n1
        rest_n2 = stop_n2 / 2 + 1
        hist_n  = stop_n2

        start_1_year, start_1_month, start_1_day = [int(item) for item in start_1.split("-")]
        start_2_year = start_1_year + 2
        start_2 = "%04d-%02d-%02d" % (start_2_year, start_1_month, start_1_day)

        stop_n3 = stop_n2 - rest_n2
        rest_n3 = stop_n3 / 2 + 1

        stop_n4 = stop_n3 - rest_n3

        expect(stop_n4 >= 1 and stop_n1 >= 1, "Run length too short")

        #
        # (1) Test run:
        # do an initial ref1 case run
        # cloned the case and running there
        # (NOTE: short term archiving is on)
        #

        os.chdir(clone1_path)
        self._set_active_case(clone1)

        logger.info("ref1 startup: doing a %s %s startup run from %s and 00000 seconds" % (stop_n1, stop_option, start_1))
        logger.info("  writing restarts at %s %s" % (rest_n1, stop_option))
        logger.info("  short term archiving is on ")

        clone1.set_value("CONTINUE_RUN", False)
        clone1.set_value("RUN_STARTDATE", start_1)
        clone1.set_value("STOP_N", stop_n1)
        clone1.set_value("REST_OPTION", stop_option)
        clone1.set_value("REST_N", rest_n1)
        clone1.set_value("HIST_OPTION", "never")

        dout_sr1 = clone1.get_value("DOUT_S_ROOT")

        # force cam namelist to write out initial file at end of run
        if os.path.exists("user_nl_cam"):
            if "inithist" not in open("user_nl_cam", "r").read():
                with open("user_nl_cam", "a") as fd:
                    fd.write("inithist = 'ENDOFRUN'\n")

        success = self._run(suffix=None,
                            coupler_log_path=os.path.join(dout_sr1, "cpl", "logs"),
                            st_archive=True)
        if not success:
            return False

        #
        # (2) Test run:
        # do a hybrid ref2 case run
        # cloned the main case and running with ref1 restarts
        # (NOTE: short term archiving is on)
        #

        os.chdir(clone2_path)
        self._set_active_case(clone2)

        # Set startdate to start2, set ref date based on ref1 restart
        refdate_2 = run_cmd(r'ls -1dt %s/rest/*-00000* | head -1 | sed "s/-00000.*//" | sed "s/^.*rest\///"' % dout_sr1)
        ref_to_d2 = "00000"

        logger.info("ref2 hybrid: doing a %s %s startup hybrid run" % (stop_n2, stop_option))
        logger.info("  starting from %s and using ref1 %s and %s seconds" % (start_2, refdate_2, ref_to_d2))
        logger.info("  writing restarts at %s %s" % (rest_n2, stop_option))
        logger.info("  short term archiving is on ")

        # setup ref2 case
        clone2.set_value("RUN_TYPE",      "hybrid")
        clone2.set_value("RUN_STARTDATE", start_2)
        clone2.set_value("RUN_REFCASE",   "%s.ref1" % orig_casevar)
        clone2.set_value("RUN_REFDATE",   refdate_2)
        clone2.set_value("RUN_REFTOD",    ref_to_d2)
        clone2.set_value("GET_REFCASE",   False)
        clone2.set_value("CONTINUE_RUN",  False)
        clone2.set_value("STOP_N",        stop_n2)
        clone2.set_value("REST_OPTION",   stop_option)
        clone2.set_value("REST_N",        rest_n2)
        clone2.set_value("HIST_OPTION",   stop_option)
        clone2.set_value("HIST_N",        hist_n)

        rundir = clone2.get_value("RUNDIR")
        dout_sr2 = clone2.get_value("DOUT_S_ROOT")

        if not os.path.exists(rundir):
            os.makedirs(rundir)

        _helper(dout_sr1, refdate_2, ref_to_d2, rundir)

        # run ref2 case (all component history files will go to short term archiving)

        success = self._run(suffix=None,
                            coupler_log_path=os.path.join(dout_sr2, "cpl", "logs"),
                            st_archive=True)
        if not success:
            return False

        #
        # (3a) Test run:
        # do a branch run from ref2 restart (short term archiving is off)
        #

        os.chdir(caseroot)
        self._set_active_case(orig_case)

        refdate_3 = run_cmd(r'ls -1dt %s/rest/*-00000* | head -1 | sed "s/-00000.*//" | sed "s/^.*rest\///"' % dout_sr2)
        ref_to_d3 = "00000"

        logger.info("branch: doing a %s %s branch" % (stop_n3, stop_option))
        logger.info("  starting from ref2 %s and %s seconds restarts" % (refdate_3, ref_to_d3))
        logger.info("  writing restarts at %s %s" % (rest_n3, stop_option))
        logger.info("  short term archiving is off")

        self._case.set_value("RUN_TYPE"      , "branch")
        self._case.set_value("RUN_REFCASE"   , "%s.ref1" % self._case.get_value("CASE"))
        self._case.set_value("RUN_REFDATE"   , refdate_3)
        self._case.set_value("RUN_REFTOD"    , ref_to_d3)
        self._case.set_value("GET_REFCASE"   , False)
        self._case.set_value("CONTINUE_RUN"  , False)
        self._case.set_value("STOP_N"        , stop_n3)
        self._case.set_value("REST_OPTION"   , stop_option)
        self._case.set_value("REST_N"        , rest_n3)
        self._case.set_value("HIST_OPTION"   , stop_option)
        self._case.set_value("HIST_N"        , stop_n2)
        self._case.set_value("DOUT_S"        , False)

        rundir = self._case.get_value("RUNDIR")
        if not os.path.exists(rundir):
            os.makedirs(rundir)

        _helper(dout_sr2, refdate_3, ref_to_d3, rundir)

        # the following lines creates the initial component history files for the restart test
        for item in glob.glob("%s/*/hist/*nc" % dout_sr2):
            newfile = "%s:t" % item.replace(".ref2", "")
            os.symlink(item, os.path.join(rundir, newfile))

        self._component_compare_move("hybrid")

        # run branch case (short term archiving is off)
        success = self._run()
        if not success:
            return False

        #
        # (3b) Test run:
        # do a restart continue from (3a) (short term archiving off)
        #

        logger.info("branch restart: doing a %s %s continue restart test" % (stop_n4, stop_option))

        self._case.set_value("CONTINUE_RUN",  True)
        self._case.set_value("STOP_N",        stop_n4)
        self._case.set_value("REST_OPTION",   "never")
        self._case.set_value("DOUT_S",        False)
        self._case.set_value("HIST_OPTION",   stop_option)
        self._case.set_value("HIST_N",        hist_n)

        # do the restart run (short term archiving is off)
        success = self._run(suffix="rest")
        if not success:
            return False

        return self._component_compare_test("base", "hybrid") and \
               self._component_compare_test("base", "rest")
