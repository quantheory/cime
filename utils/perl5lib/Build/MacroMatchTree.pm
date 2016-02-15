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
        my (@prepends, @appends);
        my $value;
        my @append_values;
        for my $match (@matches) {
            if ($match->{'append_flag'} == NORMAL_VAR) {
                $value = $match->{'value'};
            } else {
                push @append_values, $match->{'value'};
            }
            push @prepends, @{$match->{'prepends'}};
            push @appends, @{$match->{'appends'}};
        }
        $self = {
            name => $name,
            value => $value,
            append_values => \@append_values,
            prepends => \@prepends,
            appends => \@appends,
        };
    }
    bless $self, $class;
    return $self;
}

sub to_build_file {
    my ($self, $writer, $append_flag) = @_;

    if (defined $self->{'name'}) {
        my $name = $self->{'name'};
        for my $prepend (@{ $self->{'prepends'} }) {
            $writer->write($prepend);
        }
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
        for my $append (@{ $self->{'appends'} }) {
            $writer->write($append);
        }
    } else {
        my $condition_name = $self->{'condition_name'};
        my %macros = %{ $self->{'macros'} };
        # Print out all the "default" values first (the ones that don't use this
        # condition).
        if (defined $macros{""}) {
            $macros{""}->to_build_file($writer, $append_flag);
        }
        for my $condition_value (keys %macros) {
            if ($condition_value eq "") { next; }
            my $env_ref = $writer->environment_variable_string($condition_name);
            $writer->start_ifeq($env_ref, $condition_value);
            $macros{$condition_value}->to_build_file($writer, $append_flag);
            $writer->end_ifeq();
        }
    }
}

sub split_tree() {
    # Split the tree into a part that only has regular values, and one that
    # only has appended values.
    my ($self) = @_;
    my ($normal_self, $append_self);
    if (defined $self->{'name'}) {
        if (defined $self->{'value'}) {
            $normal_self = { %$self };
            my @empty;
            $normal_self->{'append_values'} = \@empty;
            bless $normal_self, ref($self);
        }
        my @append_values = @{ $self->{'append_values'} };
        if (@append_values) {
            $append_self = { %$self };
            delete $append_self->{'value'};
            bless $append_self, ref($self);
        }
    } else {
        my (%normal_macros, %append_macros);
        my %macros = %{ $self->{'macros'} };
        for my $key (keys %macros) {
            my ($normal_tree, $append_tree) = $macros{$key}->split_tree();
            if (defined $normal_tree) {
                $normal_macros{$key} = $normal_tree;
            }
            if (defined $append_tree) {
                $append_macros{$key} = $append_tree;
            }
        }
        if (%normal_macros) {
            $normal_self = {
                condition_name => $self->{'condition_name'},
                macros => \%normal_macros,
            };
            bless $normal_self, ref($self);
        }
        if (%append_macros) {
            $append_self = {
                condition_name => $self->{'condition_name'},
                macros => \%append_macros,
            };
            bless $append_self, ref($self);
        }
    }
    return ($normal_self, $append_self);
}
