package Build::MacroMatchTree;

use strict;
use warnings;
use XML::LibXML;

use Log::Log4perl qw(get_logger);
my $logger;

BEGIN{
    $logger = get_logger();
}

# Just an enum expressing whether or not a variable setting is from an "append"
# element.
use constant {
    NORMAL_VAR => 0,
    APPEND_VAR => 1,
};

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
        # This is a leaf of our tree; just include the values now.
        my $value;
        my @append_values;
        for my $match (@matches) {
            if ($match->{'append_flag'} == NORMAL_VAR) {
                $value = $match->{'value'};
            } else {
                push @append_values, $match->{'value'};
            }
        }
        $self = {
            name => $name,
            value => $value,
            append_values => \@append_values,
        };
    }
    bless $self, $class;
    return $self;
}

sub to_makefile {
    my ($self, $writer, $append_flag) = @_;

    if (defined $self->{'name'}) {
        my $name = $self->{'name'};
        if ($append_flag == NORMAL_VAR) {
            my $value = $self->{'value'};
            if (defined $value) {
                $writer->set_variable($name, $value);
            }
        } else {
            for my $value (@{ $self->{'append_values'} }) {
                $writer->append_variable($name, $value);
            }
        }
    } else {
        my $condition_name = $self->{'condition_name'};
        my %macros = %{ $self->{'macros'} };
        # Print out all the "default" values first (the ones that don't use this
        # condition).
        if (defined $macros{""}) {
            $macros{""}->to_makefile($writer, $append_flag);
        }
        for my $condition_value (keys %macros) {
            if ($condition_value eq "") { next; }
            $writer->start_ifeq("\$($condition_name)", $condition_value);
            $macros{$condition_value}->to_makefile($writer, $append_flag);
            $writer->end_ifeq();
        }
    }
}
