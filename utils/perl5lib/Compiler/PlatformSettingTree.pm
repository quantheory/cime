use strict;
use warnings;

package Compiler::PlatformSettingTree;

use XML::LibXML;

sub new {
    my $class = shift @_;
    my $conditional = shift @_;
    my $self = {
    };
    bless $self, $class;
    return $self;
}

1;
