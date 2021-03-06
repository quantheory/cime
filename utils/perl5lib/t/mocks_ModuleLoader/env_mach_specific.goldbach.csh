#!/usr/bin/env csh -f
#===============================================================================
# Automatically generated module settings for goldbach
# DO NOT EDIT THIS FILE DIRECTLY!  Please edit env_mach_specific.xml
# in your CASEROOT. This file is overwritten every time modules are loaded!
#===============================================================================

source /usr/share/Modules/init/csh
module purge
if ( $COMPILER == "intel" ) then
	module load compiler/intel/14.0.2
endif
if ( $COMPILER == "pgi" ) then
	module load compiler/pgi/14.10
endif
if ( $COMPILER == "nag" ) then
	module load compiler/nag/5.3.1-907
endif
if ( $COMPILER == "gnu" ) then
	module load compiler/gnu/4.4.7
endif
setenv P4_GLOBMEMSIZE 500000000
setenv NETCDF_DIR $NETCDF_PATH
limit stacksize unlimited
limit coredumpsize unlimited
