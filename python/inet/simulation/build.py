"""
This module provides functionality for building simulation projects.

The main function is :py:func:`build_project`.
"""

import logging
import multiprocessing
import os
import shutil
import signal
import subprocess

from inet.common.compile import *
from inet.simulation.project import *

_logger = logging.getLogger(__name__)

def build_project(build_mode="makefile", **kwargs):
    """
    Builds all output files of a simulation project using either :py:func:`build_project_using_makefile` or :py:func:`build_project_using_tasks`.

    Parameters:
        build_mode (string):
            Specifies the requested build mode. Valid values are "makefile" and "task".

        kwargs (dict):
            Additional parameters are inherited from :py:func:`build_project_using_makefile` and :py:func:`build_project_using_tasks` functions.

    Returns (None):
        Nothing.
    """
    if build_mode == "makefile":
        build_function = build_project_using_makefile
    elif build_mode == "task":
        build_function = build_project_using_tasks
    else:
        raise Exception(f"Unknown build_mode argument: {build_mode}")
    return build_function(**kwargs)

def build_project_using_makefile(simulation_project=None, mode="release", capture_output=True, **kwargs):
    """
    Builds a simulation project using the Makefile generated by the command line tool :command:`opp_makemake`. The
    output files include executables, dynamic libraries, static libraries, C++ object files, C++ message file headers
    and their implementations, etc.

    Parameters:
        simulation_project (:py:class:`SimulationProject <inet.simulation.project.SimulationProject>`):
            The simulation project to build. If unspecified, then the default simulation project is used.

        mode (string):
            Specifies the build mode of the output binaries. Valid values are "debug" and "release".

    Returns (None):
        Nothing.
    """
    if simulation_project is None:
        simulation_project = get_default_simulation_project()
    _logger.info(f"Building {simulation_project.get_name()} started")
    args = ["make", "MODE=" + mode, "-j", str(multiprocessing.cpu_count())]
    _logger.debug(f"Running subprocess: {args}")
    subprocess_result = subprocess.run(args, cwd=simulation_project.get_full_path("."), capture_output=capture_output)
    if subprocess_result.returncode != 0:
        raise Exception(f"Build {simulation_project.get_name()} failed")
    _logger.info(f"Building {simulation_project.get_name()} ended")

class MultipleBuildTasks(MultipleTasks):
    def __init__(self, simulation_project=None, concurrent=True, multiple_task_results_class=MultipleBuildTaskResults, **kwargs):
        super().__init__(concurrent=concurrent, multiple_task_results_class=multiple_task_results_class, **kwargs)
        self.simulation_project = simulation_project

    def get_description(self):
        return self.simulation_project.get_name() + " " + super().get_description()

    def is_up_to_date(self):
        def get_file_modification_time(file_path):
            full_file_path = self.simulation_project.get_full_path(file_path)
            return os.path.getmtime(full_file_path) if os.path.exists(full_file_path) else None
        def get_file_modification_times(file_paths):
            return list(map(get_file_modification_time, file_paths))
        input_file_modification_times = get_file_modification_times(self.get_input_files())
        output_file_modification_times = get_file_modification_times(self.get_output_files())
        return input_file_modification_times and output_file_modification_times and \
               not list(filter(lambda timestamp: timestamp is None, output_file_modification_times)) and \
               max(input_file_modification_times) < min(output_file_modification_times)

    def get_input_files(self):
        input_files = []
        for task in self.tasks:
            input_files = input_files + task.get_input_files()
        return input_files

    def get_output_files(self):
        outpu_files = []
        for task in self.tasks:
            outpu_files = outpu_files + task.get_output_files()
        return outpu_files

    def run(self, **kwargs):
        if self.is_up_to_date():
            task_results = list(map(lambda task: task.task_result_class(task=task, result="SKIP", expected_result="SKIP", reason="Up-to-date"), self.tasks))
            return self.multiple_task_results_class(multiple_tasks=self, results=task_results)
        else:
            return super().run(**kwargs)

class MultipleMsgCompileTasks(MultipleTasks):
    def __init__(self, simulation_project=None, name="MSG compile task", mode="release", concurrent=True, multiple_task_results_class=MultipleBuildTaskResults, **kwargs):
        super().__init__(name=name, mode=mode, concurrent=concurrent, multiple_task_results_class=multiple_task_results_class, **kwargs)
        self.simulation_project = simulation_project
        self.mode = mode
        self.input_files = list(map(lambda input_file: self.simulation_project.get_full_path(input_file), self.simulation_project.get_msg_files()))
        self.output_files = list(map(lambda output_file: re.sub("\\.msg", "_m.cc", output_file), self.input_files)) + \
                            list(map(lambda output_file: re.sub("\\.msg", "_m.h", output_file), self.input_files))

    def get_description(self):
        return self.simulation_project.get_name() + " " + super().get_description()

    def is_up_to_date(self):
        def get_file_modification_time(file_path):
            full_file_path = self.simulation_project.get_full_path(file_path)
            return os.path.getmtime(full_file_path) if os.path.exists(full_file_path) else None
        def get_file_modification_times(file_paths):
            return list(map(get_file_modification_time, file_paths))
        input_file_modification_times = get_file_modification_times(self.input_files)
        output_file_modification_times = get_file_modification_times(self.output_files)
        return input_file_modification_times and output_file_modification_times and \
               not list(filter(lambda timestamp: timestamp is None, output_file_modification_times)) and \
               max(input_file_modification_times) < min(output_file_modification_times)

    def run(self, **kwargs):
        if self.is_up_to_date():
            task_results = list(map(lambda task: task.task_result_class(task=task, result="SKIP", expected_result="SKIP", reason="Up-to-date"), self.tasks))
            return self.multiple_task_results_class(multiple_tasks=self, results=task_results)
        else:
            return super().run(**kwargs)

    def run_protected(self, **kwargs):
        result = super().run_protected(**kwargs)
        for output_file in self.output_files:
            os.utime(self.simulation_project.get_full_path(output_file), None)
        return result

class MultipleCppCompileTasks(MultipleTasks):
    def __init__(self, simulation_project=None, name="C++ compile task", mode="release", concurrent=True, multiple_task_results_class=MultipleBuildTaskResults, **kwargs):
        super().__init__(name=name, mode=mode, concurrent=concurrent, multiple_task_results_class=multiple_task_results_class, **kwargs)
        self.simulation_project = simulation_project
        self.mode = mode
        input_files = self.simulation_project.get_cpp_files() + self.simulation_project.get_header_files()
        self.input_files = list(map(lambda input_file: self.simulation_project.get_full_path(input_file), input_files))
        self.output_files = list(map(lambda output_file: self.simulation_project.get_full_path(output_file), self.get_object_files()))

    def get_description(self):
        return self.simulation_project.get_name() + " " + super().get_description()

    def get_object_files(self):
        output_folder = f"out/clang-{self.mode}"
        object_files = []
        for cpp_folder in self.simulation_project.cpp_folders:
            file_paths = glob.glob(self.simulation_project.get_full_path(os.path.join(cpp_folder, "**/*.cc")), recursive=True)
            object_files = object_files + list(map(lambda file_path: os.path.join(output_folder, self.simulation_project.get_relative_path(re.sub("\\.cc", ".o", file_path))), file_paths))
        return object_files

    def is_up_to_date(self):
        def get_file_modification_time(file_path):
            full_file_path = self.simulation_project.get_full_path(file_path)
            return os.path.getmtime(full_file_path) if os.path.exists(full_file_path) else None
        def get_file_modification_times(file_paths):
            return list(map(get_file_modification_time, file_paths))
        input_file_modification_times = get_file_modification_times(self.input_files)
        output_file_modification_times = get_file_modification_times(self.output_files)
        return input_file_modification_times and output_file_modification_times and \
               not list(filter(lambda timestamp: timestamp is None, output_file_modification_times)) and \
               max(input_file_modification_times) < min(output_file_modification_times)

    def run(self, **kwargs):
        if self.is_up_to_date():
            task_results = list(map(lambda task: task.task_result_class(task=task, result="SKIP", expected_result="SKIP", reason="Up-to-date"), self.tasks))
            return self.multiple_task_results_class(multiple_tasks=self, results=task_results)
        else:
            return super().run(**kwargs)

    def run_protected(self, **kwargs):
        result = super().run_protected(**kwargs)
        for output_file in self.output_files:
            os.utime(self.simulation_project.get_full_path(output_file), None)
        return result

class CopyBinaryTask(BuildTask):
    def __init__(self, simulation_project=None, name="copy binaries task", type="dynamic library", mode="release", task_result_class=BuildTaskResult, **kwargs):
        super().__init__(simulation_project=simulation_project, name=name, task_result_class=task_result_class, **kwargs)
        self.type = type
        self.mode = mode

    def get_action_string(self, **kwargs):
        return "Copying"

    def get_parameters_string(self, **kwargs):
        return (self.type + "s" if self.type == "executable" else self.type[:-1] + "ies")

    def get_output_prefix(self):
        return "" if self.type == "executable" else "lib"

    def get_output_suffix(self):
        return "_dbg" if self.mode == "debug" else ""

    def get_output_extension(self):
        return "" if self.type == "executable" else (".so" if self.type == "dynamic library" else ".a")

    def get_input_files(self):
        result = []
        output_folder = f"out/clang-{self.mode}"
        if self.type == "executable":
            for executable in self.simulation_project.executables:
                source_file_name = self.simulation_project.get_full_path(os.path.join(output_folder, executable + self.get_output_suffix()))
                result.append(source_file_name)
        else:
            for library in (self.simulation_project.dynamic_libraries if self.type == "dynamic library" else self.simulation_project.static_libraries):
                library_file_name = self.get_output_prefix() + library + self.get_output_suffix() + self.get_output_extension()
                source_file_name = self.simulation_project.get_full_path(os.path.join(output_folder, library_file_name))
                result.append(source_file_name)
        return result

    def get_output_files(self):
        result = []
        if self.type == "executable":
            for executable in self.simulation_project.executables:
                destination_file_name = self.simulation_project.get_full_path(os.path.join(self.simulation_project.bin_folder, executable + self.get_output_suffix()))
                result.append(destination_file_name)
        else:
            for library in (self.simulation_project.dynamic_libraries if self.type == "dynamic library" else self.simulation_project.static_libraries):
                library_file_name = self.get_output_prefix() + library + self.get_output_suffix() + self.get_output_extension()
                destination_file_name = self.simulation_project.get_full_path(os.path.join(self.simulation_project.library_folder, library_file_name))
                result.append(destination_file_name)
        return result

    def run_protected(self, **kwargs):
        for output_file in self.get_output_files():
            if os.path.exists(output_file):
                os.remove(output_file)
        for input_file, output_file in zip(self.get_input_files(), self.get_output_files()):
            shutil.copy(input_file, output_file)
        return self.task_result_class(task=self, result="DONE")

class BuildSimulationProjectTask(MultipleTasks):
    """
    Represents a task that builds a simulation project.
    """

    def __init__(self, simulation_project, name="build task", mode="release", concurrent=True, multiple_task_results_class=MultipleBuildTaskResults, **kwargs):
        """
        Initializes a new build simulation project task.

        Parameters:
            concurrent (bool):
                Flag specifying whether the build is allowed to run sub-tasks concurrently or not.

            mode (string):
                Specifies the build mode for the output binaries. Valie values are "debug" and "release".
        """
        super().__init__(concurrent=False, name=name, mode=mode, multiple_task_results_class=multiple_task_results_class, **kwargs)
        self.simulation_project = simulation_project
        self.mode = mode
        self.concurrent_child_tasks = concurrent
        self.tasks = self.get_build_tasks(mode=mode, **kwargs)

    def get_description(self):
        return self.simulation_project.get_name() + " " + super().get_description()

    def get_build_tasks(self, **kwargs):
        output_folder = self.simulation_project.get_full_path(f"out/clang-{self.mode}")
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        msg_compile_tasks = list(map(lambda msg_file: MsgCompileTask(simulation_project=self.simulation_project, file_path=msg_file, mode=self.mode), self.simulation_project.get_msg_files()))
        multiple_msg_compile_tasks = MultipleMsgCompileTasks(simulation_project=self.simulation_project, mode=self.mode, tasks=msg_compile_tasks, concurrent=self.concurrent_child_tasks)
        msg_cpp_compile_tasks = list(map(lambda msg_file: CppCompileTask(simulation_project=self.simulation_project, file_path=re.sub("\\.msg", "_m.cc", msg_file), mode=self.mode), self.simulation_project.get_msg_files()))
        cpp_compile_tasks = list(map(lambda cpp_file: CppCompileTask(simulation_project=self.simulation_project, file_path=cpp_file, mode=self.mode), self.simulation_project.get_cpp_files()))
        all_cpp_compile_tasks = msg_cpp_compile_tasks + cpp_compile_tasks
        multiple_cpp_compile_tasks = MultipleCppCompileTasks(simulation_project=self.simulation_project, mode=self.mode, tasks=all_cpp_compile_tasks, concurrent=self.concurrent_child_tasks)
        link_tasks = flatten(map(lambda library: list(map(lambda build_type: LinkTask(simulation_project=self.simulation_project, type=build_type, mode=self.mode, compile_tasks=all_cpp_compile_tasks), self.simulation_project.build_types)), self.simulation_project.executables))
        multiple_link_tasks = MultipleBuildTasks(simulation_project=self.simulation_project, tasks=link_tasks, name="link task", concurrent=self.concurrent_child_tasks)
        copy_binary_tasks = list(map(lambda build_type: CopyBinaryTask(simulation_project=self.simulation_project, type=build_type, mode=self.mode), self.simulation_project.build_types))
        multiple_copy_binary_tasks = MultipleBuildTasks(simulation_project=self.simulation_project, tasks=copy_binary_tasks, name="copy task", concurrent=self.concurrent_child_tasks)
        all_tasks = []
        if multiple_msg_compile_tasks.tasks:
            all_tasks.append(multiple_msg_compile_tasks)
        if multiple_cpp_compile_tasks.tasks:
            all_tasks.append(multiple_cpp_compile_tasks)
            all_tasks.append(multiple_link_tasks)
            all_tasks.append(multiple_copy_binary_tasks)
        return all_tasks

def build_project_using_tasks(simulation_project, **kwargs):
    """
    Builds all output files of a simulation project using tasks. The output files include executables, dynamic libraries,
    static libraries, C++ object files, C++ message file headers and their implementations, etc.

    Parameters:
        simulation_project (:py:class:`SimulationProject <inet.simulation.project.SimulationProject>`):
            The simulation project to build. If unspecified, then the default simulation project is used.

        kwargs (dict):
            Additional parameters are inherited from the constructor of :py:class:`BuildSimulationProjectTask`.

    Returns (None):
        Nothing.
    """
    return BuildSimulationProjectTask(simulation_project, **dict(kwargs)).run(**kwargs)

def clean_project(simulation_project=None, mode="release", capture_output=True, **kwargs):
    if simulation_project is None:
        simulation_project = get_default_simulation_project()
    _logger.info(f"Cleaning {simulation_project.get_name()} started")
    args = ["make", "MODE=" + mode, "-j", str(multiprocessing.cpu_count()), "clean"]
    _logger.debug(f"Running subprocess: {args}")
    subprocess_result = subprocess.run(args, cwd=simulation_project.get_full_path("."), capture_output=capture_output)
    if subprocess_result.returncode != 0:
        raise Exception(f"Build {simulation_project.get_name()} failed")
    _logger.info(f"Cleaning {simulation_project.get_name()} ended")
