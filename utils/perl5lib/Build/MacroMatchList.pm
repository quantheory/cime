package Build::MacroMatchList;

use strict;
use warnings;
use XML::LibXML;

use Log::Log4perl qw(get_logger);
my $logger;

BEGIN{
    $logger = get_logger();
    require Build::MacroMatchTree;
}

# Just an enum expressing whether or not a variable setting is from an "append"
# element.
use constant {
    NORMAL_VAR => Build::MacroMatchTree::NORMAL_VAR,
    APPEND_VAR => Build::MacroMatchTree::APPEND_VAR,
};

sub new {
    # Note that this is constructed with the first match found, so we can be
    # sure that there is always at least one match in the list.
    my ($class, $specificity, $append_flag, $conditions, $value, $prepends,
        $appends, $depends) = @_;
    my %match = (
        append_flag => $append_flag,
        conditions => $conditions,
        value => $value,
        prepends => $prepends,
        appends => $appends,
    );
    my $self = {
        specificity => $specificity,
        matches => [\%match],
        depends => $depends,
    };
    bless $self, $class;
    return $self;
}

sub specificity {
    my ($self) = @_;
    return $self->{"specificity"}
}

sub matches {
    my ($self) = @_;
    return @{$self->{"matches"}}
}

sub append_match {
    my ($self, $specificity, $append_flag, $conditions, $value, $prepends,
        $appends, $depends) = @_;
    my %match = (
        append_flag => $append_flag,
        conditions => $conditions,
        value => $value,
        prepends => $prepends,
        appends => $appends,
    );
    if ($specificity == $self->specificity || $append_flag == APPEND_VAR) {
        # If the new match is equally specific, add it to the list.
        push @{ $self->{"matches"} }, \%match;
        push @{ $self->{"depends"} }, @{ $depends };
    } elsif ($specificity > $self->specificity) {
        # If the new match is more specific, it defeats our entire list, which
        # we should therefore replace with just the new value.
        $self->{"specificity"} = $specificity;
        $self->{"matches"} = [\%match];
        $self->{"depends"} = $depends;
    }
    # If the new match is less specific, do nothing with it.
}

sub ambiguity_check {
    # This takes a name just to give a good error message.
    my ($self, $name) = @_;
    # Here we loop over all pairs of match conditions, which takes a little bit
    # of fiddling since those are a couple of levels down from the
    # MacroMatchList object itself.
    my @remaining_matches = $self->matches;
    my $current_match_ref;
    while ($current_match_ref = pop @remaining_matches) {
        if ($current_match_ref->{'append_flag'} != NORMAL_VAR) { next; }
        my %current_conditions = %{ $current_match_ref->{'conditions'} };
        my @current_keys = keys %current_conditions;
        for my $other_match_ref (@remaining_matches) {
            if ($other_match_ref->{'append_flag'} != NORMAL_VAR) { next; }
            my %other_conditions = %{ $other_match_ref->{'conditions'} };

            # Having that information, we need to figure out if two variable
            # specifications could ambiguously apply to the same case. We don't
            # have to worry about this if one of two things hold:
            #  1. The two have inconsistent settings (e.g. one is for
            #     DEBUG="TRUE" and the other for DEBUG="FALSE").
            #  2. One setting is more specific than the other (e.g. an entry
            #     with DEBUG="TRUE" and MPILIB="mpich" overrides an entry with
            #     just an MPILIB setting).
            my $matches_are_consistent = 1;
            my $other_is_subset = 1;
            my $other_is_superset = 1;
            # Only look at attributes defined on at least one of the two
            # variable settings.
            my @keys_to_check = keys %other_conditions;
            push @keys_to_check, @current_keys;
            for my $condition_name (@keys_to_check) {
                my $current_value = $current_conditions{$condition_name};
                my $other_value = $other_conditions{$condition_name};
                # If "other" has an item not on "current", then "other" is not
                # less specific.
                if (!defined $current_value) {
                    $other_is_subset = 0;
                    next;
                }
                # If vice versa, then "other" is not more specific.
                if (!defined $other_value) {
                    $other_is_superset = 0;
                    next;
                }
                # If the two have conflicting settings, there's no ambiguity.
                if ($current_value ne $other_value) {
                    $matches_are_consistent = 0;
                    last;
                }
            }
            # Die if the two matches could apply to the same situation and if
            # neither is unambiguously more specific.
            if ($matches_are_consistent and ($other_is_subset == $other_is_superset)) {
                die "MacroMaker was given ambiguous XML input: variable $name " . 
                    "has two entries that could cover the same case";
            }
        }
    }
}

sub to_macro_tree {
    my ($self, $name) = @_;
    $self->ambiguity_check($name);
    Build::MacroMatchTree->new($name, $self->{'matches'})
}
