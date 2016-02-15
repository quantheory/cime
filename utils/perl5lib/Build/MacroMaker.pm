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
                # Convert the attributes on this node to a hash.
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
                if (!defined $match_lists{$node->nodeName}) {
                    $match_lists{$node->nodeName} =
                        Build::MacroMatchList->new($specificity,
                                                   \%conditions,
                                                   $node->textContent);
                } else {
                    $match_lists{$node->nodeName}->append_match($specificity,
                                                                \%conditions,
                                                                $node->textContent);
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
