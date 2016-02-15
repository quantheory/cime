package Build::MacroMaker;

use strict;
use warnings;
use XML::LibXML;

use Log::Log4perl qw(get_logger);
my $logger;

BEGIN{
    $logger = get_logger();
}

require Build::MacroMatchList;
require Build::MacroMatchTree;

my %FLAG_VARS = map { $_ => 1 } ("CFLAGS", "CMAKE_OPTS", "CONFIG_ARGS",
                                 "CPPDEFS", "CXX_LDFLAGS", "CXX_LIBS",
                                 "FC_AUTO_R8", "FFLAGS", "FFLAGS_NOOPT",
                                 "FIXEDFLAGS", "FREEFLAGS", "LDFLAGS", "MLIBS",
                                 "SLIBS");

sub new {
    my ($class, $schema_path, $os, $mach) = @_;
    my $self = {
        schema => XML::LibXML::Schema->new( location => $schema_path ),
        os => $os,
        mach => $mach,
    };
    bless $self, $class;
    return $self;
}

# Take a variable name, how machine-specific the match is, a node, a set of
# variable match lists, and the compiler vender (if any, optional), and add
# the node and its conditions to the appropriate match list (creating a new
# list if necessary.
sub add_node_to_lists {
    my ($self, $name, $specificity, $node, $match_lists, $node_compiler) = @_;
    my @attributes = $node->attributes();
    my %conditions;
    for my $attribute (@attributes) {
        $conditions{$attribute->nodeName} = $attribute->getValue();
    }
    if (defined $node_compiler) {
        $conditions{"COMPILER"} = $node_compiler;
    }
    # Make a match list if this is a new variable, or append it to
    # the list if we've seen a variable of this name already. The
    # MacroMatchList object takes care of throwing out less specific
    # matches in favor of more specific ones.
    if (!defined $match_lists->{$name}) {
        $match_lists->{$name} =
            Build::MacroMatchList->new($specificity,
                                       \%conditions,
                                       $node->textContent);
    } else {
        $match_lists->{$name}->append_match($specificity,
                                            \%conditions,
                                            $node->textContent);
    }
}

sub write_macros_file {
    my ($self, $build_system, $xml_fh, $output_fh) = @_;

    my $doc = XML::LibXML->new()->parse_fh($xml_fh);
    if (!defined eval { $self->{"schema"}->validate($doc) }) {
        die "$@";
    }
    my $root = $doc->documentElement();
    # Hash matching each named variable to a list of matches.
    my %match_lists;
    # Loop through compiler nodes.
    for my $compiler_node ($root->findnodes("compiler")) {
        # How specific the match is.
        my $specificity = 0;
        # Do we have a MACH attribute on this compiler element?
        my $node_mach = $compiler_node->getAttribute("MACH");
        if (defined $node_mach) {
            # If MACH is defined, a successful match is more specific, while
            # an unsuccessful match is skipped entirely.
            if ($node_mach eq $self->{"mach"}) {
                $specificity += 2;
            } else {
                next;
            }
        }
        # Same thing for OS. OS matches are less specific, so only increase
        # specificity by 1.
        my $node_os = $compiler_node->getAttribute("OS");
        if (defined $node_os) {
            if ($node_os eq $self->{"os"}) {
                $specificity += 1;
            } else {
                next;
            }
        }
        # COMPILER doesn't relate to the specificity, since we allow it to
        # be changed at build time.
        my $node_compiler = $compiler_node->getAttribute("COMPILER");
        # Look at everything in this compiler node.
        for my $node ($compiler_node->childNodes()) {
            # We want elements (not comments or whitespace).
            if ($node->nodeType == XML_ELEMENT_NODE) {
                if (defined $FLAG_VARS{$node->nodeName}) {
                    # This is a flag set, so we should look at the base flags to
                    # get the information.
                    for my $base_node ($node->findnodes("base")) {
                        $self->add_node_to_lists($node->nodeName, $specificity, $base_node,
                                                 \%match_lists, $node_compiler);
                    }
                } else {
                    # Otherwise, handle this node directly.
                    $self->add_node_to_lists($node->nodeName, $specificity, $node,
                                             \%match_lists, $node_compiler);
                }
            }
        }
    }
    # Look at all the variables we've accumulated.
    for my $name (keys %match_lists) {
        my $macro_tree = $match_lists{$name}->to_macro_tree($name);
        $macro_tree->to_makefile("", $output_fh);
    }
}

1;
