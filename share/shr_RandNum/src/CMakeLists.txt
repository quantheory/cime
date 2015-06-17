list(APPEND share_sources
  shr_RandNum_mod.F90
  dsfmt_f03/dSFMT.c dsfmt_f03/dSFMT_interface.F90 dsfmt_f03/dSFMT_utils.c
  kissvec/kissvec.c kissvec/kissvec_mod.F90
  mt19937/mersennetwister_mod.F90)

sourcelist_to_parent(share_sources)
