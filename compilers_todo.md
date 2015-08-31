# Todo list for config_compilers refactoring

 - Get everything working with the new schema and scoring algorithm!
   - Including shell, env, and self-references.
   - Includes modifying both `Makefile` and `Compilers.cmake`.
   - Have to deal with case for `TRUE`/`true`/`FALSE`/`false`.
 - Remove `GPTL_CPPDEFS`.
 - Address issue where `-ffixed-line-length-none` is in `FIXEDFLAGS` instead of
   `FFLAGS`, which is correct except that only the latter is used in CMake (for
   unit tests only, or also PIO?). And the same for the free-form version of
   this option.
 - Add `REMOVE_COMPILER_OPTIMIZATION` with a default value of `$DEBUG` in
   `env_build.xml`.
 - Compiler sets:
   - Allow files to specify a different set of flags from the default.
   - Optimization flags should be split out separately, i.e. the default sets
     should be `default,default_optimization`.
   - Need to fix the "hack" in NAG flags with this feature.
 - Test on all supported machines.

# Potentially answer-changing next steps

 - Set `HAS_F2008_CONTIGUOUS` to `true` for PGI.
 - Make `CFLAGS` (`CXXFLAGS?`) respect the `DEBUG` and optimization-related
   options.
 - Why are we using `-O0` for non-`DEBUG` builds on goldbach/hobart?
