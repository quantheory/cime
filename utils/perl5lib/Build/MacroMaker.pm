package Build::MacroMaker;

use strict;
use warnings;
use XML::LibXML;

use Log::Log4perl qw(get_logger);
my $logger;

BEGIN{
    $logger = get_logger();
    # It might be hard to see where things come from if these are "use"'d, but
    # the use of constants means that they should be "require"'d in a BEGIN
    # block.
    require Build::MacroMatchList;
    require Build::MacroMatchTree;
    require Build::MacroMakeWriter;
}

# Just an enum expressing whether or not a variable setting is from an "append"
# element.
use constant {
    NORMAL_VAR => Build::MacroMatchTree::NORMAL_VAR,
    APPEND_VAR => Build::MacroMatchTree::APPEND_VAR,
};

sub new {
    my ($class, $schema_path, $os, $mach) = @_;
    # Get a hash of flag variables from the schema document.
    my $schema_doc = XML::LibXML->new()->parse_file($schema_path);
    my $xc = XML::LibXML::XPathContext->new($schema_doc);
    $xc->registerNs("xs", "http://www.w3.org/2001/XMLSchema");
    my @schema_elements = $xc->findnodes("//xs:group[\@name='compilerVars']/xs:choice/xs:element[\@type='flagsVar']");
    my %flag_vars;
    for my $element (@schema_elements) {
        $flag_vars{$element->{'name'}} = 1;
    }
    my $self = {
        schema => XML::LibXML::Schema->new( location => $schema_path ),
        os => $os,
        mach => $mach,
        flag_vars => \%flag_vars,
    };
    bless $self, $class;
    return $self;
}

# Handle references from a node's contents to an environment variable, another
# config_build variable, or a shell command.
sub handle_references {
    my ($self, $node, $writer) = @_;
    my $output_text = "";
    for my $child ($node->childNodes()) {
        if ($child->nodeType == XML_TEXT_NODE) {
            $output_text .= $child->data;
        } elsif ($child->nodeType == XML_ELEMENT_NODE) {
            my $child_name = $child->nodeName;
            if ($child_name eq "env") {
                my $env_name = $child->textContent;
                $output_text .= $writer->environment_variable_string($env_name);
            } elsif ($child_name eq "shell") {
                my $command_text = $self->handle_references($child, $writer);
                $output_text .= $writer->shell_command_string($command_text);
            } else {
                # This should be caught in the schema check, but no harm in
                # throwing an error here if that somehow fails.
                die "unrecognized element in variable value: $child_name";
            }
        }
    }
    return $output_text;
}

# Take a variable name, how machine-specific the match is, a node, a set of
# variable match lists, and the compiler vender this applies to (if any), and
# add the node and its conditions to the appropriate match list (creating a new
# list if necessary.
sub add_node_to_lists {
    # This argument list is admittedly pretty ridiculous.
    my ($self, $name, $specificity, $node, $match_lists, $append_flag, $writer, $node_compiler) = @_;
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
    my $node_contents = $self->handle_references($node, $writer);
    if (!defined $match_lists->{$name}) {
        $match_lists->{$name} =
            Build::MacroMatchList->new($specificity,
                                       $append_flag,
                                       \%conditions,
                                       $node_contents);
    } else {
        $match_lists->{$name}->append_match($specificity,
                                            $append_flag,
                                            \%conditions,
                                            $node_contents);
    }
}

sub write_macros_file {
    my ($self, $build_system, $xml_fh, $output_fh) = @_;

    my $writer;
    if ($build_system eq "make") {
        $writer = Build::MacroMakeWriter->new($output_fh);
    } else {
        die "MacroMaker was given an unrecognized build system";
    }

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
                if (defined $self->{'flag_vars'}{$node->nodeName}) {
                    # This is a flag set, so we should look at the base flags to
                    # get the information.
                    for my $base_node ($node->findnodes("base")) {
                        $self->add_node_to_lists($node->nodeName, $specificity, $base_node,
                                                 \%match_lists, NORMAL_VAR, $writer,
                                                 $node_compiler);
                    }
                    # And also the append flags.
                    for my $append_node ($node->findnodes("append")) {
                        $self->add_node_to_lists($node->nodeName, $specificity, $append_node,
                                                 \%match_lists, APPEND_VAR, $writer,
                                                 $node_compiler);
                    }
                } else {
                    # Otherwise, handle this node directly.
                    $self->add_node_to_lists($node->nodeName, $specificity, $node,
                                             \%match_lists, NORMAL_VAR, $writer,
                                             $node_compiler);
                }
            }
        }
    }
    # Look at all the variables we've accumulated.
    for my $name (keys %match_lists) {
        my $macro_tree = $match_lists{$name}->to_macro_tree($name);
        $macro_tree->to_makefile($writer, NORMAL_VAR);
        $macro_tree->to_makefile($writer, APPEND_VAR);
    }
}

1;
