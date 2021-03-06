#!/usr/bin/env sh -f
#===============================================================================
# Automatically generated module settings for bluewaters
# DO NOT EDIT THIS FILE DIRECTLY!  Please edit env_mach_specific.xml
# in your CASEROOT. This file is overwritten every time modules are loaded!
#===============================================================================

.  /opt/modules/default/init/sh
CIME_REPO=`./xmlquery CIME_REPOTAG -value`
if [ -n $CIME_REPO  ]
then
  COMPILER=`./xmlquery  COMPILER          -value`
  MPILIB=`./xmlquery  MPILIB        -value`
  DEBUG=`./xmlquery  DEBUG         -value`
  OS=`./xmlquery  OS        -value`
  PROFILE_PAPI_ENABLE=`./xmlquery  PROFILE_PAPI_ENABLE -value`
fi
module rm PrgEnv-pgi
module rm PrgEnv-cray
module rm PrgEnv-gnu
module rm pgi
module rm cray
if [ "$COMPILER" = "pgi" ]
then
	module load PrgEnv-pgi
	module switch pgi pgi/14.2.0
fi
if [ "$COMPILER" = "gnu" ]
then
	module load PrgEnv-gnu/4.2.84
	module switch gcc gcc/4.8.2
fi
if [ "$COMPILER" = "cray" ]
then
	module load PrgEnv-cray/4.2.34
	module switch cce cce/8.2.6
fi
module load papi/5.3.2
module switch cray-mpich cray-mpich/7.0.3
module switch cray-libsci cray-libsci/12.2.0
module load torque/5.0.1
if [ "$MPILIB" != "mpi-serial" ]
then
	module load cray-netcdf-hdf5parallel/4.3.2
	module load cray-parallel-netcdf/1.5.0
fi
if [ "$MPILIB" = "mpi-serial" ]
then
	module load cray-netcdf/4.3.2
fi
module load cmake
module rm darshan
export OMP_STACKSIZE=64M
export MPICH_ENV_DISPLAY=1
export MPICH_PTL_MATCH_OFF=1
