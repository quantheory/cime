#!/usr/bin/env sh -f
#===============================================================================
# Automatically generated module settings for olympus
# DO NOT EDIT THIS FILE DIRECTLY!  Please edit env_mach_specific.xml
# in your CASEROOT. This file is overwritten every time modules are loaded!
#===============================================================================

.  /share/apps/modules/Modules/3.2.7/init/sh
CIME_REPO=`./xmlquery CIME_REPOTAG -value`
if [ -n $CIME_REPO  ]
then
  COMPILER=`./xmlquery  COMPILER          -value`
  MPILIB=`./xmlquery  MPILIB        -value`
  DEBUG=`./xmlquery  DEBUG         -value`
  OS=`./xmlquery  OS        -value`
  PROFILE_PAPI_ENABLE=`./xmlquery  PROFILE_PAPI_ENABLE -value`
fi
module purge
module load precision/i4
module load pgi/11.8
module load mvapich2/1.7
module load netcdf/4.1.3
