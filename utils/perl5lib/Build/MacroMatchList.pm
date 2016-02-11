package Build::MacroMatchList;

use strict;
use warnings;
use XML::LibXML;

use Log::Log4perl qw(get_logger);
my $logger;

BEGIN{
    $logger = get_logger();
}

require Build::MacroMatchList;

sub new {
    # Note that this is constructed with the first match found, so we can be
    # sure that there is always at least one match in the list.
    my ($class, $specificity, $conditions, $value) = @_;
    my %match = (
        conditions => $conditions,
        value => $value,
    );
    my $self = {
        specificity => $specificity,
        matches => [\%match],
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
    my ($self, $specificity, $conditions, $value) = @_;
    my %match = (
        conditions => $conditions,
        value => $value,
    );
    if ($specificity == $self->specificity) {
        # If the new match is equally specific, add it to the list.
        push @{$self->{"matches"}}, \%match;
    } elsif ($specificity > $self->specificity) {
        # If the new match is more specific, it defeats our entire list, which
        # we should therefore replace with just the new value.
        $self->{"specificity"} = $specificity;
        $self->{"matches"} = [\%match];
    }
    # If the new match is less specific, do nothing with it.
}

sub to_macro_tree {
    my ($self, $name) = @_;
    Build::MacroMatchTree->new($name, $self->{'matches'})
}
