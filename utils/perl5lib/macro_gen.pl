#!/usr/bin/env perl
use strict;
use warnings;

my $cimeroot;

BEGIN {
  #
  # setup paths for cime and local utility modules at compile time.
  #
  # Assumes that we are running from cime/perl5lib....
  #
  use Cwd qw(getcwd abs_path);
  use File::Basename;

  my $dir = dirname($0);
  if (!(-e $dir and -d $dir)) {
      $dir = getcwd();
  }
  $cimeroot = abs_path("$dir/../..");

  my @dirs = ("$dir",
              "$dir/CPAN",
              "$cimeroot/scripts");

  unshift @INC, @dirs;
  require Build::MacroMaker;
}

my ($infile, $build_system, $os, $machine) = @ARGV;

open(my $in_fh, "<", $infile)
    or die "cannot open $infile\n";

my $macro_maker = Build::MacroMaker->new("$cimeroot/cime_config/cesm/machines/config_build.xsd", $os, $machine);
$macro_maker->write_macros_file($build_system, $in_fh, \*STDOUT);

close($in_fh);

exit 0;
