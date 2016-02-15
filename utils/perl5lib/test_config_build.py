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

        # Read in the Makefile/CMake output.
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

    def query_var(self, var_name, env, var):
        """Request the value of a variable in the Makefile, as a string.

        Arguments:
        var_name - Name of the variable to query.
        env - A dict containing extra environment variables to set when calling
              make.
        var - A dict containing extra make variables to set when calling make.
              (The distinction between env and var actually matters only for
               CMake, though.)
        """

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
        environment.update(var)
        subprocess.check_output(["gmake", "query", "--directory="+temp_dir],
                                stderr=subprocess.STDOUT, env=environment)

        with open(output_name, "r") as output:
            query_result = output.read().strip()

        # Clean up the Makefiles.
        shutil.rmtree(temp_dir)

        return query_result

    def assert_variable_equals(self, var_name, value, env=dict(), var=dict()):
        """Assert that a variable in the Makefile has a given value.

        Arguments:
        var_name - Name of variable to check.
        value - The string that the variable value should be equal to.
        env - Optional. Dict of environment variables to set when calling make.
        var - Optional. Dict of make variables to set when calling make.
        """
        self.parent.assertEqual(self.query_var(var_name, env, var), value)


class CMakeTester(object):

    """Helper class for checking CMake output.

    Public methods:
    __init__
    query_var
    assert_variable_equals
    """

    _cmakelists_template = """
include(./Macros.cmake)
file(WRITE query.out "${{{}}}")
"""

    def __init__(self, parent, cmake_string):
        """Constructor for CMake test helper class.

        Arguments:
        parent - The TestCase object that is using this item.
        cmake_string - CMake contents to test.
        """
        self.parent = parent
        self.cmake_string = cmake_string

    def query_var(self, var_name, env, var):
        """Request the value of a variable in Macros.cmake, as a string.

        Arguments:
        var_name - Name of the variable to query.
        env - A dict containing extra environment variables to set when calling
              cmake.
        var - A dict containing extra CMake variables to set when calling cmake.
        """

        # Write the CMake strings to temporary files.
        temp_dir = tempfile.mkdtemp()
        macros_file_name = os.path.join(temp_dir, "Macros.cmake")
        cmakelists_name = os.path.join(temp_dir, "CMakeLists.txt")
        output_name = os.path.join(temp_dir, "query.out")

        with open(macros_file_name, "w") as macros_file:
            for key in var:
                macros_file.write("set(CIME_{} {})\n".format(key, var[key]))
            macros_file.write(self.cmake_string)
        with open(cmakelists_name, "w") as cmakelists:
            cmakelists.write(self._cmakelists_template.format("CIME_"+var_name))

        environment = os.environ.copy()
        environment.update(env)
        subprocess.check_output(["cmake", "."], cwd=temp_dir,
                                stderr=subprocess.STDOUT, env=environment)

        with open(output_name, "r") as output:
            query_result = output.read().strip()

        # Clean up the CMake files.
        shutil.rmtree(temp_dir)

        return query_result

    def assert_variable_equals(self, var_name, value, env=dict(), var=dict()):
        """Assert that a variable in the Makefile has a given value.

        Arguments:
        var_name - Name of variable to check.
        value - The string that the variable value should be equal to.
        env - Optional. Dict of environment variables to set when calling make.
        var - Optional. Dict of CMake variables to set when calling cmake.
        """
        self.parent.assertEqual(self.query_var(var_name, env, var), value)


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
        with self.assertRaisesRegexp(MacroScriptError,
                                     "parser error") as asrt:
            maker.make_macros("This is not valid XML.", "make")
        shutil.rmtree(asrt.exception.temp_test_dir)

    def test_script_rejects_xml_failing_schema(self):
        """The macro writer rejects XML that doesn't follow the schema."""
        maker = MacroTestMaker("SomeOS", "mymachine")
        test_xml = _wrap_config_build_xml("<justsometag/>")
        with self.assertRaisesRegexp(MacroScriptError,
                                     "Schemas validity error") as asrt:
            maker.make_macros(test_xml, "make")
        shutil.rmtree(asrt.exception.temp_test_dir)

    def test_script_rejects_bad_build_system(self):
        """The macro writer rejects a bad build system string."""
        maker = MacroTestMaker("SomeOS", "mymachine")
        with self.assertRaisesRegexp(MacroScriptError,
                                     "MacroMaker was given an unrecognized build system") as asrt:
            maker.make_macros("This string is irrelevant.", "argle-bargle")
        shutil.rmtree(asrt.exception.temp_test_dir)


class TestMakeOutput(unittest.TestCase):

    """Makefile macros tests.

    This class contains tests of the Makefile output of MacrosMaker.

    Aside from the usual setUp and test methods, this class has a utility method
    (xml_to_tester) that converts XML input directly to a MakefileTester object.
    """

    test_os = "SomeOS"
    test_machine = "mymachine"

    def setUp(self):
        self._maker = MacroTestMaker(self.test_os, self.test_machine)

    def xml_to_tester(self, xml_string):
        """Helper that directly converts an XML string to a MakefileTester."""
        test_xml = _wrap_config_build_xml(xml_string)
        return MakefileTester(self, self._maker.make_macros(test_xml, "make"))

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

    def test_reject_duplicate_defaults(self):
        """The macro writer dies if given many defaults."""
        xml1 = """<compiler><MPI_PATH>/path/to/default</MPI_PATH></compiler>"""
        xml2 = """<compiler><MPI_PATH>/path/to/other_default</MPI_PATH></compiler>"""
        with self.assertRaisesRegexp(MacroScriptError,
                                     "MacroMaker was given ambiguous XML input") as asrt:
            self.xml_to_tester(xml1+xml2)
        shutil.rmtree(asrt.exception.temp_test_dir)

    def test_reject_duplicates(self):
        """The macro writer dies if given many matches for a given configuration."""
        xml1 = """<compiler><MPI_PATH MPILIB="mpich">/path/to/mpich</MPI_PATH></compiler>"""
        xml2 = """<compiler><MPI_PATH MPILIB="mpich">/path/to/mpich2</MPI_PATH></compiler>"""
        with self.assertRaisesRegexp(MacroScriptError,
                                     "MacroMaker was given ambiguous XML input") as asrt:
            self.xml_to_tester(xml1+xml2)
        shutil.rmtree(asrt.exception.temp_test_dir)

    def test_reject_ambiguous(self):
        """The macro writer dies if given an ambiguous set of matches."""
        xml1 = """<compiler><MPI_PATH MPILIB="mpich">/path/to/mpich</MPI_PATH></compiler>"""
        xml2 = """<compiler><MPI_PATH DEBUG="FALSE">/path/to/mpi-debug</MPI_PATH></compiler>"""
        with self.assertRaisesRegexp(MacroScriptError,
                                     "MacroMaker was given ambiguous XML input") as asrt:
            self.xml_to_tester(xml1+xml2)
        shutil.rmtree(asrt.exception.temp_test_dir)

    def test_compiler_changeable_at_build_time(self):
        """The macro writer writes information for multiple compilers."""
        xml1 = """<compiler><SUPPORTS_CXX>FALSE</SUPPORTS_CXX></compiler>"""
        xml2 = """<compiler COMPILER="gnu"><SUPPORTS_CXX>TRUE</SUPPORTS_CXX></compiler>"""
        tester = self.xml_to_tester(xml1+xml2)
        tester.assert_variable_equals("SUPPORTS_CXX", "FALSE")
        tester.assert_variable_equals("SUPPORTS_CXX", "TRUE", env={"COMPILER": "gnu"})

    def test_base_flags(self):
        """Test that we get "base" compiler flags."""
        xml1 = """<compiler><FFLAGS><base>-O2</base></FFLAGS></compiler>"""
        tester = self.xml_to_tester(xml1)
        tester.assert_variable_equals("FFLAGS", "-O2")

    def test_machine_specific_base_flags(self):
        """Test selection among base compiler flag sets based on machine."""
        xml1 = """<compiler><FFLAGS><base>-O2</base></FFLAGS></compiler>"""
        xml2 = """<compiler MACH="{}"><FFLAGS><base>-O3</base></FFLAGS></compiler>""".format(self.test_machine)
        tester = self.xml_to_tester(xml1+xml2)
        tester.assert_variable_equals("FFLAGS", "-O3")

    def test_build_time_base_flags(self):
        """Test selection of base flags based on build-time attributes."""
        xml1 = """<compiler><FFLAGS><base>-O2</base></FFLAGS></compiler>"""
        xml2 = """<compiler><FFLAGS><base DEBUG="TRUE">-O3</base></FFLAGS></compiler>"""
        tester = self.xml_to_tester(xml1+xml2)
        tester.assert_variable_equals("FFLAGS", "-O2")
        tester.assert_variable_equals("FFLAGS", "-O3", env={"DEBUG": "TRUE"})

    def test_build_time_base_flags_same_parent(self):
        """Test selection of base flags in the same parent element."""
        xml1 = """<base>-O2</base>"""
        xml2 = """<base DEBUG="TRUE">-O3</base>"""
        tester = self.xml_to_tester("<compiler><FFLAGS>"+xml1+xml2+"</FFLAGS></compiler>")
        tester.assert_variable_equals("FFLAGS", "-O2")
        tester.assert_variable_equals("FFLAGS", "-O3", env={"DEBUG": "TRUE"})
        # Check for order independence here, too.
        tester = self.xml_to_tester("<compiler><FFLAGS>"+xml2+xml1+"</FFLAGS></compiler>")
        tester.assert_variable_equals("FFLAGS", "-O2")
        tester.assert_variable_equals("FFLAGS", "-O3", env={"DEBUG": "TRUE"})

    def test_append_flags(self):
        """Test appending flags to a list."""
        xml1 = """<compiler><FFLAGS><base>-delicious</base></FFLAGS></compiler>"""
        xml2 = """<compiler><FFLAGS><append>-cake</append></FFLAGS></compiler>"""
        tester = self.xml_to_tester(xml1+xml2)
        tester.assert_variable_equals("FFLAGS", "-delicious -cake")
        # Order independence, as usual.
        tester = self.xml_to_tester(xml2+xml1)
        tester.assert_variable_equals("FFLAGS", "-delicious -cake")

    def test_append_flags_without_base(self):
        """Test appending flags to a value set before Macros is included."""
        xml1 = """<compiler><FFLAGS><append>-cake</append></FFLAGS></compiler>"""
        tester = self.xml_to_tester(xml1)
        tester.assert_variable_equals("FFLAGS", "-delicious -cake", var={"FFLAGS": "-delicious"})

    def test_build_time_append_flags(self):
        """Test build_time selection of compiler flags."""
        xml1 = """<compiler><FFLAGS><append>-cake</append></FFLAGS></compiler>"""
        xml2 = """<compiler><FFLAGS><append DEBUG="TRUE">-and-pie</append></FFLAGS></compiler>"""
        tester = self.xml_to_tester(xml1+xml2)
        tester.assert_variable_equals("FFLAGS", "-cake")
        tester.assert_variable_equals("FFLAGS", "-cake -and-pie", env={"DEBUG": "TRUE"})

    def test_environment_variable_insertion(self):
        """Test that <env> elements insert environment variables."""
        xml1 = """<compiler><LDFLAGS><append>-L<env>NETCDF</env> -lnetcdf</append></LDFLAGS></compiler>"""
        tester = self.xml_to_tester(xml1)
        tester.assert_variable_equals("LDFLAGS", "-L/path/to/netcdf -lnetcdf",
                                      env={"NETCDF": "/path/to/netcdf"})

    def test_shell_command_insertion(self):
        """Test that <shell> elements insert shell command output."""
        xml1 = """<compiler><FFLAGS><base>-O<shell>echo 2</shell> -fast</base></FFLAGS></compiler>"""
        tester = self.xml_to_tester(xml1)
        tester.assert_variable_equals("FFLAGS", "-O2 -fast")

    def test_multiple_shell_commands(self):
        """Test that more than one <shell> element can be used."""
        xml1 = """<compiler><FFLAGS><base>-O<shell>echo 2</shell> -<shell>echo fast</shell></base></FFLAGS></compiler>"""
        tester = self.xml_to_tester(xml1)
        tester.assert_variable_equals("FFLAGS", "-O2 -fast")

    def test_env_and_shell_command(self):
        """Test that <env> elements work inside <shell> elements."""
        xml1 = """<compiler><FFLAGS><base>-O<shell>echo <env>OPT_LEVEL</env></shell> -fast</base></FFLAGS></compiler>"""
        tester = self.xml_to_tester(xml1)
        tester.assert_variable_equals("FFLAGS", "-O2 -fast", env={"OPT_LEVEL": "2"})

    def test_config_variable_insertion(self):
        """Test that <var> elements insert variables from config_build."""
        # Construct an absurd chain of references just to sure that we don't
        # pass by accident, e.g. outputting things in the right order just due
        # to good luck in a hash somewhere.
        xml1 = """<MPI_LIB_NAME>stuff-<var>MPI_PATH</var>-stuff</MPI_LIB_NAME>"""
        xml2 = """<MPI_PATH><var>MPICC</var></MPI_PATH>"""
        xml3 = """<MPICC><var>MPICXX</var></MPICC>"""
        xml4 = """<MPICXX><var>MPIFC</var></MPICXX>"""
        xml5 = """<MPIFC>mpicc</MPIFC>"""
        tester = self.xml_to_tester("<compiler>"+xml1+xml2+xml3+xml4+xml5+"</compiler>")
        tester.assert_variable_equals("MPI_LIB_NAME", "stuff-mpicc-stuff")

    def test_config_reject_self_references(self):
        """Test that <var> self-references are rejected."""
        # This is a special case of the next test, which also checks circular
        # references.
        xml1 = """<MPI_LIB_NAME><var>MPI_LIB_NAME</var></MPI_LIB_NAME>"""
        err_msg = "MacroMaker was given XML output with a circular <var> reference"
        with self.assertRaisesRegexp(MacroScriptError, err_msg) as asrt:
            self.xml_to_tester("<compiler>"+xml1+"</compiler>")
        shutil.rmtree(asrt.exception.temp_test_dir)

    def test_config_reject_cyclical_references(self):
        """Test that cyclical <var> references are rejected."""
        xml1 = """<MPI_LIB_NAME><var>MPI_PATH</var></MPI_LIB_NAME>"""
        xml2 = """<MPI_PATH><var>MPI_LIB_NAME</var></MPI_PATH>"""
        err_msg = "MacroMaker was given XML output with a circular <var> reference"
        with self.assertRaisesRegexp(MacroScriptError, err_msg) as asrt:
            self.xml_to_tester("<compiler>"+xml1+xml2+"</compiler>")
        shutil.rmtree(asrt.exception.temp_test_dir)


class TestCMakeOutput(TestMakeOutput):

    """CMake macros tests.

    This class contains tests of the CMake output of MacrosMaker.

    This class simply inherits all of the methods of TestMakeOutput, but changes
    the definition of xml_to_tester to create a CMakeTester instead.
    """

    def xml_to_tester(self, xml_string):
        """Helper that directly converts an XML string to a MakefileTester."""
        test_xml = _wrap_config_build_xml(xml_string)
        return CMakeTester(self, self._maker.make_macros(test_xml, "cmake"))


if __name__ == "__main__":
    unittest.main()
