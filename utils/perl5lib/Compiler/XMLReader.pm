use strict;
use warnings;

package Compiler::XMLReader;

use XML::LibXML;

sub new {
    my $class = shift @_;
    my $mach = shift @_;
    my $os = shift @_;
    my $compiler = shift @_;
    my $self = {
        mach => $mach,
        os => $os,
        compiler => $compiler,
    };
    bless $self, $class;
    return $self;
}

1;
