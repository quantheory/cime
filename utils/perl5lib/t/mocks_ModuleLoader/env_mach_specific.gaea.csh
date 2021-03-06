#!/usr/bin/env csh -f
#===============================================================================
# Automatically generated module settings for gaea
# DO NOT EDIT THIS FILE DIRECTLY!  Please edit env_mach_specific.xml
# in your CASEROOT. This file is overwritten every time modules are loaded!
#===============================================================================

source  /opt/modules/default/init/csh
set CESM_REPO = `./xmlquery CCSM_REPOTAG -value`
if($status == 0) then
  set COMPILER            = `./xmlquery  COMPILER          -value`
  set MPILIB              = `./xmlquery  MPILIB        -value`
  set DEBUG               = `./xmlquery  DEBUG         -value`
  set OS                  = `./xmlquery  OS        -value`
  set PROFILE_PAPI_ENABLE = `./xmlquery  PROFILE_PAPI_ENABLE -value`
endif
module rm PrgEnv-pgi
module rm PrgEnv-cray
module rm PrgEnv-gnu
module rm pgi
module rm cray
if ( $COMPILER == "pgi" ) then
	module load PrgEnv-pgi
	module switch pgi pgi/12.5.0
endif
if ( $COMPILER == "gnu" ) then
	module load PrgEnv-gnu
	module load torque
endif
if ( $COMPILER == "cray" ) then
	module load PrgEnv-cray/4.0.36
	module load cce/8.0.2
endif
module load torque/4.1.3
module load netcdf-hdf5parallel/4.2.0
module load parallel-netcdf/1.2.0
setenv OMP_STACKSIZE 64M
setenv MPICH_ENV_DISPLAY 1
