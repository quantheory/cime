#!/usr/bin/env python2
"""Tests for the generation of Macros files from config_build.xml"""

# De-CESM-ization notes:
#  - The schema should really be part of perl5lib, not in machines.

import os
import os.path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

# Let's try to figure out where CIME is. By default just look upward from the
# current directory.
CIME_ROOT = os.path.join(os.getcwd(), "..", "..")

# However, usually we can figure it out based on the path used to call the test
# script.
if os.access(sys.argv[0], os.F_OK):
    this_script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    CIME_ROOT = os.path.join(this_script_dir, "..", "..")

PERL5LIB_ROOT = os.path.join(CIME_ROOT, "utils", "perl5lib")

# Location of the schema file.
SCHEMA_PATH = os.path.join(CIME_ROOT, "cime_config", "cesm", "machines", "config_build.xsd")

class MacroScriptError(Exception):

    """Wrapper exception for MacroMaker failures.

    Public methods:
    __init__

    Public attributes:
    error - The underlying CalledProcessError.
    temp_test_dir - The temporary directory we were in when the error was
                    raised.
    """
    def __init__(self, error, temp_test_dir):
        """Construct an error from a CalledProcessError and test directory."""
        self.error = error
        self.temp_test_dir = temp_test_dir

    def __str__(self):
        """Provide some debugging information."""
        error_string = "macros script error in directory {}, " + \
                       "leading to output: {}"
        return error_string.format(self.temp_test_dir, self.error.output)


class MacroTestMaker(object):

    """Wrapper class used to generate Macros output from config_build XML.

    This class is intended primarily for testing purposes. Once created, a
    MacroTestMaker object can be used to transform an input XML file into an
    output macros file in Makefile or CMake format. Note that inputs/outputs are
    strings in memory, not files.

    Public methods:
    __init__
    make_macros

    Public attributes:
    os, machine - The target OS and machine; these are just copies of whatever
                  was input to __init__.
    """

    # This is a relatively dumb perl script that actually does the writing.
    _perl_template = """#!/usr/bin/env perl
    use strict;
    use warnings;

    unshift @INC, "{0}";

    require Build::MacroMaker;

    my ($build_system, $infile, $outfile) = @ARGV;

    open(my $in_fh, "<", $infile)
        or die "cannot open $infile\n";
    open(my $out_fh, ">", $outfile)
        or die "cannot open $outfile\n";

    my $macro_maker = Build::MacroMaker->new("{1}", "{2}", "{3}");
    $macro_maker->write_macros_file($build_system, $in_fh, $out_fh);

    close($in_fh);
    close($out_fh);

    exit 0;
    """

    def __init__(self, os, machine):
        """Create a MacroTestMaker object given an OS and a machine name."""
        # Store these here just for debugging/utility.
        self.os = os
        self.machine = machine
        # The script we will actually call to work the magic.
        self._script = self._perl_template.format(PERL5LIB_ROOT, SCHEMA_PATH, os, machine)

    def make_macros(self, build_xml, build_system):
        """Generate build system ("Macros" file) output from config_build XML.

        Arguments:
        build_xml - A string containing the XML to operate on.
        build_system - Either "make" or "cmake", depending on desired output.

        The return value is a string containing the build system output. If the
        underlying script dies, a subprocess.CalledProcessError will be thrown,
        containing the usual returncode and output attributes.
        """
        # First, set up the directory to run the perl script in.
        temp_dir = tempfile.mkdtemp()
        input_file_name = os.path.join(temp_dir, "config_build.xml")
        script_name = os.path.join(temp_dir, "MakeMacros.pl")
        output_file_name = os.path.join(temp_dir, "Macros")

        # Write out the provided XML and the script we're building.
        with open(input_file_name, "w") as input_file:
            input_file.write(build_xml)
        with open(script_name, "w") as script_file:
            script_file.write(self._script)
        os.chmod(script_name, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)

        # Call the macro script.
        try:
            subprocess.check_output([script_name, build_system, input_file_name,
                                     output_file_name], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            # Some tests want this error to be raised, but we want to clean up
            # the temporary directory in that case, so we need to communicate
            # that information in the exception.
            raise MacroScriptError(e, temp_dir)

        # Read in the Makefile output.
        with open(output_file_name, "r") as output_file:
            output_string = output_file.read()

        # Clean up the files we created. Not a huge deal if we miss this, but
        # we may as well avoid cluttering /tmp. If an unexpected error occurs
        # above, we might actually want this directory for debugging purposes,
        # so it's fine that this step is skipped if an exception is raised.
        shutil.rmtree(temp_dir)

        return output_string


def _wrap_config_build_xml(inner_string):
    """Utility function to create a config_build XML string.

    Pass this function a string containing <compiler> elements, and it will add
    the necessary header/footer to the file.
    """
    _xml_template = """<?xml version="1.0" encoding="UTF-8"?>
<config_build>
{}
</config_build>
"""

    return _xml_template.format(inner_string)

class MakefileTester(object):

    """Helper class for checking Makefile output.

    Public methods:
    __init__
    query_var
    assert_variable_equals
    """

    _makefile_template = """
include Macros
query:
	$(file > query.out,$({}))
    """

    def __init__(self, parent, make_string):
        """Constructor for Makefile test helper class.

        Arguments:
        parent - The TestCase object that is using this item.
        make_string - Makefile contents to test.
        """
        self.parent = parent
        self.make_string = make_string

    def query_var(self, var_name, env):
        """Request the value of a variable after the Makefile is processed."""

        # Write the Makefile strings to temporary files.
        temp_dir = tempfile.mkdtemp()
        macros_file_name = os.path.join(temp_dir, "Macros")
        makefile_name = os.path.join(temp_dir, "Makefile")
        output_name = os.path.join(temp_dir, "query.out")

        with open(macros_file_name, "w") as macros_file:
            macros_file.write(self.make_string)
        with open(makefile_name, "w") as makefile:
            makefile.write(self._makefile_template.format(var_name))

        environment = os.environ.copy()
        environment.update(env)
        subprocess.check_output(["gmake", "query", "--directory="+temp_dir],
                                stderr=subprocess.STDOUT, env=environment)

        with open(output_name, "r") as output:
            query_result = output.read().strip()

        # Clean up the Makefiles.
        shutil.rmtree(temp_dir)

        return query_result

    def assert_variable_equals(self, var_name, compare_string, env=dict()):
        self.parent.assertEqual(self.query_var(var_name, env), compare_string)


class TestBasic(unittest.TestCase):

    """Basic infrastructure tests.

    This class contains tests that do not actually depend on the output of the
    macro file conversion. This includes basic smoke testing and tests of
    error-handling in the routine.
    """

    def test_script_is_callable(self):
        """The test script can be called on valid output without dying."""
        # This is really more a smoke test of this script than anything else.
        maker = MacroTestMaker("SomeOS", "mymachine")
        test_xml = _wrap_config_build_xml("<compiler><SUPPORTS_CXX>FALSE</SUPPORTS_CXX></compiler>")
        maker.make_macros(test_xml, "make")

    def test_script_rejects_bad_xml(self):
        """The macro writer rejects input that's not valid XML."""
        maker = MacroTestMaker("SomeOS", "mymachine")
        try:
            maker.make_macros("This is not valid XML.", "make")
        except MacroScriptError as e:
            self.assertRegexpMatches(e.error.output, "parser error")
            # Since failing in this case is fine, remove the temporary
            # directory.
            shutil.rmtree(e.temp_test_dir)
        else:
            self.fail("Script was handed invalid XML but did not fail.")

    def test_script_rejects_xml_failing_schema(self):
        """The macro writer rejects XML that doesn't follow the schema."""
        maker = MacroTestMaker("SomeOS", "mymachine")
        test_xml = _wrap_config_build_xml("<justsometag/>")
        try:
            maker.make_macros(test_xml, "make")
        except MacroScriptError as e:
            self.assertRegexpMatches(e.error.output, "Schemas validity error")
            # Since failing in this case is fine, remove the temporary
            # directory.
            shutil.rmtree(e.temp_test_dir)
        else:
            self.fail("Script was handed XML not matching the schema but did not fail.")


class TestMakeOutput(unittest.TestCase):

    """Makefile macros tests.

    This class contains tests of the Makefile output of MacrosMaker.
    """

    test_os = "SomeOS"
    test_machine = "mymachine"

    def xml_to_tester(self, xml_string):
        """Helper that directly converts an XML string to a MakefileTester."""
        maker = MacroTestMaker(self.test_os, self.test_machine)
        test_xml = _wrap_config_build_xml(xml_string)
        return MakefileTester(self, maker.make_macros(test_xml, "make"))

    def test_generic_item(self):
        """The macro writer can write out a single generic item."""
        xml_string = "<compiler><SUPPORTS_CXX>FALSE</SUPPORTS_CXX></compiler>"
        tester = self.xml_to_tester(xml_string)
        tester.assert_variable_equals("SUPPORTS_CXX", "FALSE")

    def test_machine_specific_item(self):
        """The macro writer can pick out a machine-specific item."""
        xml1 = """<compiler MACH="{}"><SUPPORTS_CXX>TRUE</SUPPORTS_CXX></compiler>""".format(self.test_machine)
        xml2 = """<compiler><SUPPORTS_CXX>FALSE</SUPPORTS_CXX></compiler>"""
        tester = self.xml_to_tester(xml1+xml2)
        tester.assert_variable_equals("SUPPORTS_CXX", "TRUE")
        # Do this a second time, but with elements in the reverse order, to
        # ensure that the code is not "cheating" by taking the first match.
        tester = self.xml_to_tester(xml2+xml1)
        tester.assert_variable_equals("SUPPORTS_CXX", "TRUE")

    def test_ignore_non_match(self):
        """The macro writer ignores an entry with the wrong machine name."""
        xml1 = """<compiler MACH="bad"><SUPPORTS_CXX>TRUE</SUPPORTS_CXX></compiler>"""
        xml2 = """<compiler><SUPPORTS_CXX>FALSE</SUPPORTS_CXX></compiler>"""
        tester = self.xml_to_tester(xml1+xml2)
        tester.assert_variable_equals("SUPPORTS_CXX", "FALSE")
        # Again, double-check that we don't just get lucky with the order.
        tester = self.xml_to_tester(xml2+xml1)
        tester.assert_variable_equals("SUPPORTS_CXX", "FALSE")

    def test_os_specific_item(self):
        """The macro writer can pick out an OS-specific item."""
        xml1 = """<compiler OS="{}"><SUPPORTS_CXX>TRUE</SUPPORTS_CXX></compiler>""".format(self.test_os)
        xml2 = """<compiler><SUPPORTS_CXX>FALSE</SUPPORTS_CXX></compiler>"""
        tester = self.xml_to_tester(xml1+xml2)
        tester.assert_variable_equals("SUPPORTS_CXX", "TRUE")
        tester = self.xml_to_tester(xml2+xml1)
        tester.assert_variable_equals("SUPPORTS_CXX", "TRUE")

    def test_mach_beats_os(self):
        """The macro writer chooses machine-specific over os-specific matches."""
        xml1 = """<compiler OS="{}"><SUPPORTS_CXX>FALSE</SUPPORTS_CXX></compiler>""".format(self.test_os)
        xml2 = """<compiler MACH="{}"><SUPPORTS_CXX>TRUE</SUPPORTS_CXX></compiler>""".format(self.test_machine)
        tester = self.xml_to_tester(xml1+xml2)
        tester.assert_variable_equals("SUPPORTS_CXX", "TRUE")
        tester = self.xml_to_tester(xml2+xml1)
        tester.assert_variable_equals("SUPPORTS_CXX", "TRUE")

    def test_mach_and_os_beats_mach(self):
        """The macro writer chooses the most-specific match possible."""
        xml1 = """<compiler MACH="{}"><SUPPORTS_CXX>FALSE</SUPPORTS_CXX></compiler>""".format(self.test_machine)
        xml2 = """<compiler MACH="{}" OS="{}"><SUPPORTS_CXX>TRUE</SUPPORTS_CXX></compiler>"""
        xml2 = xml2.format(self.test_machine, self.test_os)
        tester = self.xml_to_tester(xml1+xml2)
        tester.assert_variable_equals("SUPPORTS_CXX", "TRUE")
        tester = self.xml_to_tester(xml2+xml1)
        tester.assert_variable_equals("SUPPORTS_CXX", "TRUE")

    def test_build_time_attribute(self):
        """The macro writer writes conditionals for build-time choices."""
        xml1 = """<compiler><MPI_PATH MPILIB="mpich">/path/to/mpich</MPI_PATH></compiler>"""
        xml2 = """<compiler><MPI_PATH MPILIB="openmpi">/path/to/openmpi</MPI_PATH></compiler>"""
        xml3 = """<compiler><MPI_PATH>/path/to/default</MPI_PATH></compiler>"""
        tester = self.xml_to_tester(xml1+xml2+xml3)
        tester.assert_variable_equals("MPI_PATH", "/path/to/default")
        tester.assert_variable_equals("MPI_PATH", "/path/to/mpich", env={"MPILIB": "mpich"})
        tester.assert_variable_equals("MPI_PATH", "/path/to/openmpi", env={"MPILIB": "openmpi"})
        tester = self.xml_to_tester(xml3+xml2+xml1)
        tester.assert_variable_equals("MPI_PATH", "/path/to/default")
        tester.assert_variable_equals("MPI_PATH", "/path/to/mpich", env={"MPILIB": "mpich"})
        tester.assert_variable_equals("MPI_PATH", "/path/to/openmpi", env={"MPILIB": "openmpi"})


if __name__ == "__main__":
    unittest.main()
