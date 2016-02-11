package Build::MacroMatchTree;

use strict;
use warnings;
use XML::LibXML;

use Log::Log4perl qw(get_logger);
my $logger;

BEGIN{
    $logger = get_logger();
}

# This class forms a tree of Macros separated out according to the various
# conditions under which they are used (i.e. DEBUG, compile_threaded, etc.).

sub new {
    my ($class, $name, $matches_ref) = @_;
    # Find a condition in the match list.
    # We have to search because the very first entry might be the default, i.e.
    # there are no conditions at all.
    my $condition;
    my @matches = @{ $matches_ref };
    for my $match (@matches) {
        my %conditions = %{ $match->{'conditions'} };
        if (%conditions) {
            $condition = (keys %conditions)[0];
            last;
        }
    }
    my $self;
    if (defined $condition) {
        # If we found one, use it to partition our matches.
        my %partition;
        for my $match (@matches) {
            my %conditions = %{ $match->{'conditions'} };
            my $condition_value = $conditions{$condition};
            if (defined $condition_value) {
                delete $match->{'conditions'}->{$condition};
            } else {
                $condition_value = "";
            }
            if (defined $partition{$condition_value}) {
                push @{ $partition{$condition_value} }, $match;
            } else {
                $partition{$condition_value} = [$match];
            }
        }
        # Now recursively descend through each partition to classify values.
        my %macros;
        for my $condition_value (keys %partition) {
            $macros{$condition_value} =
                Build::MacroMatchTree->new($name, $partition{$condition_value});
        }
        $self = {
            condition_name => $condition,
            macros => \%macros,
        }
    } else {
        # Just the default here.
        $self = {
            sole_name => $name,
            sole_value => $matches[0]->{'value'},
        };
    }
    bless $self, $class;
    return $self;
}

sub to_makefile {
    my ($self, $indent, $output_fh) = @_;

    if (defined $self->{'sole_name'}) {
        my $name = $self->{'sole_name'};
        my $value = $self->{'sole_value'};
        print $output_fh $indent . "$name=$value\n";
    } else {
        my $condition_name = $self->{'condition_name'};
        my %macros = %{ $self->{'macros'} };
        # Print out all the "default" values first (the ones that don't use this
        # condition).
        if (defined $macros{""}) {
            $macros{""}->to_makefile($indent, $output_fh);
        }
        for my $condition_value (keys %macros) {
            if ($condition_value eq "") { next; }
            print $output_fh $indent."ifeq (\$($condition_name),$condition_value)\n";
            my $new_indent = $indent . "  ";
            $macros{$condition_value}->to_makefile($new_indent, $output_fh);
            print $output_fh "endif\n";
        }
    }
}
