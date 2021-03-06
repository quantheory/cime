
from CIME.XML.standard_module_setup import *
from CIME.case_submit               import submit
from CIME.XML.files                 import Files
from CIME.XML.component             import Component
from CIME.XML.machines              import Machines
from CIME.case                      import Case
from CIME.utils                     import expect, get_model, run_cmd, append_status
from CIME.XML.env_mach_specific import EnvMachSpecific
from CIME.utils                     import expect
from CIME.check_lockedfiles         import check_lockedfiles
from CIME.preview_namelists         import preview_namelists
from CIME.task_maker                import TaskMaker

import gzip, shutil, time, sys, os

logger = logging.getLogger(__name__)

###############################################################################
def preRunCheck(case):
###############################################################################

    # Pre run initialization code..
    caseroot = case.get_value("CASEROOT")
    cimeroot = case.get_value("CIMEROOT")
    din_loc_root = case.get_value("DIN_LOC_ROOT")
    compiler = case.get_value("COMPILER")
    debug = case.get_value("DEBUG")
    mach = case.get_value("MACH")
    batchsubmit = case.get_value("BATCHSUBMIT")
    mpilib = case.get_value("MPILIB")
    rundir = case.get_value("RUNDIR")
    build_complete = case.get_value("BUILD_COMPLETE")

    # check for locked files.
    check_lockedfiles(case.get_value("CASEROOT"))
    logger.debug("check_lockedfiles OK")

    # check that build is done
    expect (build_complete,
            "BUILD_COMPLETE is not true\nPlease rebuild the model interactively")
    logger.debug("build complete is %s " %build_complete)

    # load the module environment...
    env_module = case._get_env("mach_specific")
    env_module.load_env_for_case(compiler=case.get_value("COMPILER"),
                                 debug=case.get_value("DEBUG"),
                                 mpilib=case.get_value("MPILIB"))

    # set environment variables
    # This is a requirement for yellowstone only
    if mpilib == "mpi-serial" and "MP_MPILIB" in os.environ:
        del os.environ["MP_MPILIB"]
    else:
        os.environ["MPILIB"] = mpilib

    if batchsubmit is None or len(batchsubmit) == 0:
        os.environ["LBQUERY"] = "FALSE"
        os.environ["BATCHQUERY"] = "undefined"
    elif batchsubmit == 'UNSET':
        os.environ["LBQUERY"] = "FALSE"
        os.environ["BATCHQUERY"] = "undefined"
    else:
        os.environ["LBQUERY"] = "TRUE"

    # create the timing directories, optionally cleaning them if needed.
    if not os.path.isdir(rundir):
        os.mkdir(rundir)

    if os.path.isdir(os.path.join(rundir,"timing")):
        shutil.rmtree(os.path.join(rundir,"timing"))

    os.makedirs(os.path.join(rundir,"timing","checkpoints"))

    # run preview namelists
    preview_namelists(case)

    # document process
    append_status("Run started ",caseroot=caseroot,
                 sfile="CaseStatus")

    logger.info( "-------------------------------------------------------------------------")
    logger.info( " - To prestage required restarts, untar a restart.tar file into %s" %(rundir))
    logger.info( " - Case input data directory (DIN_LOC_ROOT) is %s " %(din_loc_root))
    logger.info( " - Checking for required input datasets in DIN_LOC_ROOT")
    logger.info( "-------------------------------------------------------------------------")

###############################################################################
def runModel(case):
###############################################################################

    # Set OMP_NUM_THREADS
    tm = TaskMaker(case)
    num_threads = tm.thread_count
    os.environ["OMP_NUM_THREADS"] = str(num_threads)

    # Run the model
    logger.info("%s MODEL EXECUTION BEGINS HERE" %(time.strftime("%Y-%m-%d %H:%M:%S")))

    machine = Machines(machine=case.get_value("MACH"))
    cmd = machine.get_full_mpirun(tm, case, "case.run")
    cmd = case.get_resolved_value(cmd)

    logger.debug("run command is %s " %cmd)
    rundir = case.get_value("RUNDIR")
    run_cmd(cmd, from_dir=rundir)
    logger.info( "%s MODEL EXECUTION HAS FINISHED" %(time.strftime("%Y-%m-%d %H:%M:%S")))

###############################################################################
def postRunCheck(case, lid):
###############################################################################

    caseroot = case.get_value("CASEROOT")
    rundir = case.get_value("RUNDIR")
    model = case.get_value("MODEL")

    # find the last model.log and cpl.log
    model_logfile = os.path.join(rundir,model + ".log." + lid)
    cpl_logfile   = os.path.join(rundir,"cpl" + ".log." + lid)

    if not os.path.isfile(model_logfile):
        msg = "Model did not complete, no %s log file "%model_logfile
        append_status(msg, caseroot=caseroot, sfile="CaseStatus")
        expect(False, msg)
    elif not os.path.isfile(cpl_logfile):
        msg = "Model did not complete, no cpl log file"
        append_status(msg, caseroot=caseroot, sfile="CaseStatus")
        expect(False, msg)
    elif os.stat(model_logfile).st_size == 0:
        msg = " Run FAILED "
        append_status(msg, caseroot=caseroot, sfile="CaseStatus")
        expect (False, msg)
    else:
        if 'SUCCESSFUL TERMINATION' in open(cpl_logfile).read():
            msg = "Run SUCCESSFUL"
            append_status(msg, caseroot=caseroot, sfile="CaseStatus" )
        else:
            msg = "Model did not complete - see %s \n " %(cpl_logfile)
            append_status(msg, caseroot=caseroot, sfile="CaseStatus")
            expect (False, msg)

###############################################################################
def getTimings(case, lid):
###############################################################################

    check_timing = case.get_value("CHECK_TIMING")
    if check_timing:
        caseroot = case.get_value("CASEROOT")
        timingDir = os.path.join(caseroot, "timing")
        if not os.path.isdir(timingDir):
            os.makedirs(timingDir)

        logger.info("Running timing script %s " %(os.path.join(caseroot, "Tools", "getTiming")))
        cmd = "%s -lid %s " %(os.path.join(caseroot,"Tools","getTiming"), lid)
        run_cmd(cmd)

        # save the timing files if desired
        save_timing = case.get_value("SAVE_TIMING")
        if save_timing:
            rundir = case.get_value("RUNDIR")
            shutil.move(os.path.join(rundir,"timing"),
                        os.path.join(rundir,"timing."+lid))

        # compress relevant timing files
        logger.info( "gzipping timing stats.." )
        model = case.get_value("MODEL")
        timingfile = os.path.join(timingDir, model + "_timing_stats." + lid)
        with open(timingfile, 'rb') as f_in, gzip.open(timingfile + '.gz', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.remove(timingfile)
        logger.info("Done with timings")
###############################################################################
def saveLogs(case, lid):
###############################################################################

    logdir = case.get_value("LOGDIR")
    if logdir is not None and len(logdir) > 0:
        if not os.path.isdir(logdir):
            os.makedirs(logdir)

        caseroot = case.get_value("CASEROOT")
        rundir = case.get_value("RUNDIR")

        # get components
        files = Files()
        config_file = files.get_value("CONFIG_DRV_FILE")
        component = Component(config_file)
        comps = [x.lower() for x in component.get_valid_model_components()]
        comps = [x.replace('drv', 'cpl') for x in comps]
        model = [case.get_value("MODEL")]
        comps = comps + model

        # for each component, compress log files and copy to logdir
        for comp in comps:
            logfile = os.path.join(rundir, comp + '.log.' + lid)
            if os.path.isfile(logfile):
                f_in = open(logfile)
                f_out = gzip.open(logfile + '.gz', 'wb')
                f_out.writelines(f_in)
                f_out.close()
                f_in.close()
                os.remove(logfile)
                logfile_copy = logfile + '.gz'
                shutil.copy(logfile_copy,
                            os.path.join(caseroot, logdir, os.path.basename(logfile_copy)))

###############################################################################
def resubmitCheck(case):
###############################################################################

    # check to see if we need to do resubmission from this particular job,
    # Note that Mira requires special logic

    dout_s = case.get_value("DOUT_S")
    mach = case.get_value("MACH")
    testcase = case.get_value("TESTCASE")
    resubmit_num = case.get_value("RESUBMIT")

    # If dout_s is True than short-term archiving handles the resubmit
    # that is not the case on Mira
    resubmit = False
    if not dout_s and resubmit_num > 0:
        resubmit = True
    elif dout_s and mach == 'mira':
        resubmit = True

    if resubmit:
        if testcase is not None and testcase in ['ERR']:
            job = "case.test"
        else:
            job = "case.run"
        submit(case, job=job, resubmit=True)

###############################################################################
def DoDataAssimilation(case, da_script, lid):
###############################################################################
    cmd = da_script + "1> da.log.%s 2>&1" %(lid)
    logger.debug("running %s" %da_script)
    run_cmd(cmd)
    # disposeLog(case, 'da', lid)  THIS IS UNDEFINED!

###############################################################################
def case_run(case):
###############################################################################
    # Set up the run, run the model, do the postrun steps
    run_with_submit = case.get_value("RUN_WITH_SUBMIT")
    expect (run_with_submit,
            "You are not calling the run script via the submit script. "
            "As a result, short-term archiving will not be called automatically."
            "Please submit your run using the submit script like so:"
            " ./case.submit")

    data_assimilation = case.get_value("DATA_ASSIMILATION")
    data_assimilation_cycles = case.get_value("DATA_ASSIMILATION_CYCLES")
    data_assimilation_script = case.get_value("DATA_ASSIMILATION_SCRIPT")

    # set up the LID
    lid = time.strftime("%y%m%d-%H%M%S")
    os.environ["LID"] = lid

    for _ in range(data_assimilation_cycles):
        preRunCheck(case)
        runModel(case)
        postRunCheck(case, lid)
        saveLogs(case, lid)       # Copy log files back to caseroot
        getTimings(case, lid)     # Run the getTiming script
        if data_assimilation:
            DoDataAssimilation(case, data_assimilation_script, lid)

    resubmitCheck(case)

    return True
