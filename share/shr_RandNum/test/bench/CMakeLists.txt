set(test_sources test_shr_RandNum.F90)

set(sources_needed shr_RandNum_mod.F90 dSFMT.c dSFMT_interface.F90
  dSFMT_utils.c kissvec.c kissvec_mod.F90 mersennetwister_mod.F90)

extract_sources("${sources_needed}" "${share_sources}" test_sources)

add_executable(shr_RandNum_bench_exe ${test_sources})

add_custom_target(shr_RandNum_bench shr_RandNum_bench_exe)

add_dependencies(benchmark shr_RandNum_bench)
