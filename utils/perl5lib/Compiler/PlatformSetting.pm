use strict;
use warnings;

package Compiler::PlatformSetting;

use XML::LibXML;

sub new {
    my $class = shift @_;
    my $name = shift @_;
    my $value = shift @_;
    my $append = shift @_;
    my $self = {
        name => $name,
        value => $value,
        append => $append,
    };
    bless $self, $class;
    return $self;
}

1;
