package Build::MacroCMakeWriter;

use strict;
use warnings;
use XML::LibXML;

use Log::Log4perl qw(get_logger);
my $logger;

BEGIN{
    $logger = get_logger();
}

# Number of spaces to indent for if blocks.
use constant INDENT_INCREMENT => 2;

# Create a new writer using a file handle.
sub new {
    my ($class, $output_fh) = @_;
    my $self = {
        indent => 0,
        output_fh => $output_fh,
    };
    bless $self, $class;
    return $self;
}

# Write through file handle.
sub write {
    my ($self, $string) = @_;
    my $output_fh = $self->{'output_fh'};
    print $output_fh $self->indent . $string;
}

# Increase indent.
sub indent_right {
    my ($self) = @_;
    $self->{'indent'} += INDENT_INCREMENT;
}

# Decrease indent.
sub indent_left {
    my ($self) = @_;
    $self->{'indent'} -= INDENT_INCREMENT;
}

# Return the indent string.
sub indent {
    my ($self) = @_;
    return ' ' x $self->{'indent'};
}

# Return a string that represents an environment variable reference.
sub environment_variable_string {
    my ($self, $name) = @_;
    return "\$ENV{$name}";
}

# Return a string that represents a shell command.
sub shell_command_string {
    my ($self, $command) = @_;
    my $var_name = "CIME_TEMP_SHELL";
    my $set_var = "execute_process(COMMAND $command OUTPUT_VARIABLE $var_name OUTPUT_STRIP_TRAILING_WHITESPACE)\n";
    return ("$set_var", "\${$var_name}", "unset($var_name)\n");
}

# Return a string that represents a CMake variable reference.
sub variable_string {
    my ($self, $name) = @_;
    return "\${CIME_$name}";
}

# Write out a string to set a variable to some value.
sub set_variable {
    my ($self, $name, $value) = @_;
    $self->write("set(CIME_$name \"$value\")\n");
}

# Write out a string to append to a value.
sub append_variable {
    my ($self, $name, $value) = @_;
    my $self_ref = $self->variable_string($name);
    $self->write("set(CIME_$name \"$self_ref $value\")\n");
}

# Start an ifeq block.
sub start_ifeq {
    my ($self, $left, $right) = @_;
    $self->write("if(\"$left\" STREQUAL \"$right\")\n");
    $self->indent_right();
}

# End an ifeq block.
sub end_ifeq {
    my ($self) = @_;
    $self->indent_left();
    $self->write("endif()\n");
}
