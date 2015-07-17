package SetupTools;
my $pkg_nm = 'SetupTools';

use strict;
use XML::LibXML;

#-------------------------------------------------------------------------------
sub create_namelist_infile
{
    my ($caseroot, $user_nl_file, $namelist_infile, $infile_text) = @_;

    open( file_usernl,"<${user_nl_file}"   ) or die "*** can't open file: $user_nl_file\n";
    open( file_infile,">${namelist_infile}") or die "*** can't open file: $namelist_infile";

    print file_infile "\&comp_inparm \n";

    if ($infile_text) {
	print file_infile $infile_text;
    }

    while (my $line = <file_usernl>) {
	if ($line =~ /^[\&\/\!]/ ) {
	    next; # do nothing
	} elsif ($line =~ /\$([\w\_]+)/) {
	    my %xmlvars = ();
	    getxmlvars(${caseroot},\%xmlvars);
	    $line = expand_xml_var($line, \%xmlvars);
	}
	print file_infile "$line";
    }
    print file_infile "\/ \n";

    close(file_infile);
    close(file_usernl);
}

#-------------------------------------------------------------------------------
sub expand_env
{
    my ($value, $xmlvars_ref) = @_;

    if ($value =~ /\$\{*([\w_]+)}*(.*)$/) {
       my $subst = $xmlvars_ref->{$1};
       $subst = $ENV{$1} unless defined $subst;
       $value =~ s/\$\{*${1}\}*/$subst/g;
    }

    if ($value =~ /\$\{*[\w_]+\}*.*$/) {
	$value = expand_env($value, $xmlvars_ref)
    }
    return $value;
}

#-------------------------------------------------------------------------------
sub expand_xml_var
{
    my ($value, $xmlvars_ref) = @_;

    if ($value =~ /\$\{*([\w_]+)}*(.*)$/) {
	my $found_xml;
	while ( my ($key, $subst) = each(%$xmlvars_ref) ) {
	    if ($key eq $1) {
		$value =~ s/\$\{*${1}\}*/$subst/g;
		$found_xml = 'yes';
		last;
	    }
	}
	if (! defined($found_xml) ) {
	    $value = expand_env($value, $xmlvars_ref) ;
	}
    }

    if ($value =~ /\$\{*[\w_]+\}*.*$/) {
	$value = expand_xml_var($value, $xmlvars_ref) ;
    }
    return $value;
}

#-------------------------------------------------------------------------------
sub getxmlvars
{
    # Read $caseroot xml files - put restuls in %xmlvars hash
    my ($caseroot, $xmlvars) = @_;

    my $parser = XML::LibXML->new( no_blanks => 1);

    my @files = <${caseroot}/*xml>;
    foreach my $file (@files) {
	my $xml_variables = $parser->parse_file($file);
	my @nodes = $xml_variables->findnodes(".//entry");
	foreach my $node (@nodes) {
	    my $id    = $node->getAttribute('id');
	    my $value = $node->getAttribute('value');
	    $xmlvars->{$id} = $value;
	}
    }
}

#-------------------------------------------------------------------------------
sub set_compiler
{
    # Parse the config_compiler.xml file into a Macros file for the
    # given machine and compiler. Search the user's ~/.cime directory
    # first, then use the standard compiler file if it is not available.
    my ($os,$compiler_file, $compiler, $machine, $mpilib, $print, $macrosfile, $output_format) = @_;

    # Read compiler xml
    my %compiler_settings;
    my @files = ("$ENV{\"HOME\"}/.cime/config_compilers.xml", "$compiler_file");
    foreach my $file (@files) {
	if (-f $file) {
	    my $xml = XML::LibXML->new( no_blanks => 1)->parse_file($file);
	    my @nodes = $xml->findnodes(".//compiler");
	    foreach my $node (@nodes) {

                next if ($node->nodeType() != XML_ELEMENT_NODE);

		my $COMPILER = $node->getAttribute('COMPILER');
		my $MACH     = $node->getAttribute('MACH');
		my $OS       = $node->getAttribute('OS');

		# Only pick up settings for which the defined attributes match
		next if (defined $COMPILER && $COMPILER ne $compiler);
		next if (defined $MACH     && $MACH     ne $machine );
		next if (defined $OS       && $OS       ne $os      );

		# compiler settings comprises arrays of child xml nodes,
                # organized according to the variable that they set.
                foreach my $compiler_var ($node->childNodes()) {
                    next if ($compiler_var->nodeType() != XML_ELEMENT_NODE);

                    if (not defined $compiler_settings{$compiler_var->nodeName}) {
                        $compiler_settings{$compiler_var->nodeName} = [];
                    }
                    push($compiler_settings{$compiler_var->nodeName}, $compiler_var);
                }
	    }
	}
    }

    # List of all variables that we will set.
    my @var_names = keys %compiler_settings;

    foreach my $var_name (@var_names){

        # reference to an array of elements that set this value.
        my $var_elements = $compiler_settings{$var_name};

	my %a = ();
	my @attrs = $flag->attributes();
	foreach my $attr (@attrs) {
	    my $attr_value = $attr->getValue();
	    my $attr_name  = $attr->getName();
	    $a{$attr_name} = $attr_value;
	}
	my @keys =  keys %a;
	my $name = $flag->nodeName();
	my $value  = $flag->textContent();
	my $hash = $macros->{_COND_};
	if ($#keys<0){
	    if($name =~ /^ADD_(.*)$/){
		my $basename = $1;
		if (defined $macros->{$basename}) {
		    $macros->{$basename} .= $value ;
		} elsif (defined $macros->{$name}) {
		    $macros->{$name}.=$value;
		} else {
		    $macros->{$name}=$value;
		}
		print "$basename+=$value\n" if($print>1);
	    } else {
		$macros->{$name}=$value;
		print "$name:=$value\n" if($print>1);
	    }
	}else{
	    my $key;
	    foreach $key (@keys){
		unless(defined $hash->{$key}{$a{$key}}){
		    $hash->{$key}{$a{$key}}={} ;
		}
		$hash=$hash->{$key}{$a{$key}};
	    }
	    $hash->{$name}=$value;

	}
    }
    my $compcpp = $compiler;
    $compcpp =~ tr/a-z/A-Z/;
    $macros->{ADD_CPPDEFS} .= " -D$os -DCPR$compcpp ";

    if(! defined($macros->{MPI_PATH}) && defined($ENV{MPI_PATH})){
      print "Setting MPI_PATH from Environment\n";
      $macros->{MPI_PATH}=$ENV{MPI_PATH};
    }
    if(! defined($macros->{NETCDF_PATH}) && defined($ENV{NETCDF_PATH})){
      print "Setting NETCDF_PATH from Environment\n";
      $macros->{NETCDF_PATH}=$ENV{NETCDF_PATH};
    }

    #    print Dumper($macros);
    $output_format="make" unless defined($output_format);
    open MACROS,">$macrosfile" or die "Could not open file $macrosfile to write";
    print MACROS "#\n# COMPILER=$compiler\n";
    print MACROS "# OS=$os\n";
    print MACROS "# MACH=$machine\n";
    my @keys =  sort keys %{$macros};

    if($output_format eq "make"){
	# open Macros file to write
	print MACROS "#\n# Makefile Macros generated from $compiler_file \n#\n";
	# print Dumper($macros);

	# print the settings out to the Macros file
	foreach (@keys){
	    next if($_ eq '_COND_');
	    if($_ =~ /^ADD_(.*)/){
		print MACROS "$1+=".$macros->{$_}."\n\n";
	    }else{
		print MACROS "$_:=".$macros->{$_}."\n\n";
	    }
	}
    } elsif($output_format eq "cmake"){
	print MACROS "#\n# cmake Macros generated from $compiler_file \n#\n";
        print MACROS "include(Compilers)\n";
	print MACROS "set(CMAKE_C_FLAGS_RELEASE \"\" CACHE STRING \"Flags used by c compiler.\" FORCE)\n";
	print MACROS "set(CMAKE_C_FLAGS_DEBUG \"\" CACHE STRING \"Flags used by c compiler.\" FORCE)\n";
	print MACROS "set(CMAKE_Fortran_FLAGS_RELEASE \"\" CACHE STRING \"Flags used by Fortran compiler.\" FORCE)\n";
	print MACROS "set(CMAKE_Fortran_FLAGS_DEBUG \"\" CACHE STRING \"Flags used by Fortran compiler.\" FORCE)\n";
        print MACROS "set(all_build_types \"None Debug Release RelWithDebInfo MinSizeRel\")\n";
        print MACROS "set(CMAKE_BUILD_TYPE \"\${CMAKE_BUILD_TYPE}\" CACHE STRING \"Choose the type of build, options are: \${all_build_types}.\" FORCE)\n\n";
	# print the settings out to the Macros file, do it in two passes so that path values appear first in the file.
	foreach (@keys){
	    next if($_ eq '_COND_');
	    my $value = $macros->{$_};
	    $value =~ s/\(/\{/g;
	    $value =~ s/\)/\}/g;
	    if($_ =~ /^.*_PATH/){
		print MACROS "set($_ $value)\n";
                print MACROS "list(APPEND CMAKE_PREFIX_PATH $value)\n\n";
	    }
	}
	foreach (@keys){
	    next if($_ eq '_COND_');
	    my $value = $macros->{$_};
	    $value =~ s/\(/\{/g;
	    $value =~ s/\)/\}/g;
	    if($_ =~ /CFLAGS/){
		print MACROS "add_flags(CMAKE_C_FLAGS $value)\n\n";
	    }elsif($_ =~ /FFLAGS/){
		print MACROS "add_flags(CMAKE_Fortran_FLAGS $value)\n\n";
            }elsif($_ =~ /CPPDEFS/){
		print MACROS "list(APPEND COMPILE_DEFINITIONS $value)\n\n";
            }elsif($_ =~ /SLIBS/ or $_ =~ /LDFLAGS/){
		print MACROS "add_flags(CMAKE_EXE_LINKER_FLAGS $value)\n\n";
		#	    }elsif($_ =~ /^ADD_(.*)/){
		#		print MACROS "add_flags($1 $value)\n\n";
		#	    }else{
		#		print MACROS "add_flags($_ $value)\n\n";
	    }
	}

    }
    # Recursively print the conditionals, combining tests to avoid repetition
    _parse_hash($macros->{_COND_}, 0, $output_format);

    close MACROS;
}

#-----------------------------------------------------------------------------------------------
#                               Private routines
#-----------------------------------------------------------------------------------------------
sub _parse_hash
{
    my($href,$depth, $output_format, $cmakedebug) = @_;
    my @keys = keys %{$href};
    my $k1;

    my $width=2*$depth;
    foreach $k1 (@keys){
	if(ref($href->{$k1})){
	    my $k2;
	    if($output_format eq "make" or $k1 =~ /DEBUG/){
		foreach $k2 (keys %{$href->{$k1}}){
		    if($output_format eq "make"){
			printf(MACROS "%${width}s"," ") if($width>0);
			printf(MACROS "ifeq (\$(%s), %s) \n",$k1,$k2);
		    }

		    _parse_hash($href->{$k1}{$k2},$depth+1, $output_format, $k2);
		}
	    }
	}else{
	    if($output_format eq "make"){
		if($k1=~/ADD_(.*)/){
		    printf(MACROS "%${width}s %s +=%s\n"," ",$1,$href->{$k1});
		}else{
		    printf(MACROS "%${width}s %s :=%s\n"," ",$k1,$href->{$k1});
		}
	    }else{
		my $value = $href->{$k1};
		$value =~ s/\(/\{/g;
		$value =~ s/\)/\}/g;
		if($cmakedebug =~ /TRUE/){
		    if($k1 =~ /CFLAGS/){
			printf(MACROS "add_flags(CMAKE_C_FLAGS_DEBUG $value)\n\n");
		    }elsif($k1 =~ /FFLAGS/){
			printf(MACROS "add_flags(CMAKE_Fortran_FLAGS_DEBUG $value)\n\n");
		    }elsif($k1 =~ /CPPDEF/){
			printf(MACROS "add_config_definitions(DEBUG $value)\n\n");
		    }elsif($_ =~ /SLIBS/ or $_ =~ /LDFLAGS/){
			print MACROS "add_flags(CMAKE_EXE_LINKER_FLAGS_DEBUG $value)\n\n";
		    }
		}else{
		    if($k1 =~ /CFLAGS/){
			printf( MACROS "add_flags(CMAKE_C_FLAGS_RELEASE $value)\n\n");
		    }elsif($k1 =~ /FFLAGS/){
			printf( MACROS "add_flags(CMAKE_Fortran_FLAGS_RELEASE $value)\n\n");
		    }elsif($k1 =~ /CPPDEF/){
			printf(MACROS "add_config_definitions(RELEASE $value)\n\n");
		    }elsif($_ =~ /SLIBS/ or $_ =~ /LDFLAGS/){
			print MACROS "add_flags(CMAKE_EXE_LINKER_FLAGS_RELEASE $value)\n\n";
		    }
		}
	    }
	}
    }
    $width-=2;
    if($output_format eq "make"){
	printf(MACROS "%${width}s"," ") if($width>0);
	printf(MACROS "endif\n\n") if($depth>0) ;
    }
}

#-------------------------------------------------------------------------------

1;
