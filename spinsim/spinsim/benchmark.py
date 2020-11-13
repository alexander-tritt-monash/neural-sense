import numpy as np
import matplotlib.pyplot as plt
import time as tm
from numba import cuda
from enum import Enum
import h5py

from . import manager
from . import utilities
from . import spinsim
from archive import *
from test_signal import *

class BenchmarkType(Enum):
    """
    An enum to define the type of benchmark being done. Each gives labels and plot parameters to allow for the plotting and arching code to be modular.

    Parameters
    ----------
    _value_ : `string`
        Label for the archive.
    x_label : `string`
        Horizontal label for when plotting.
    y_label : `string`
        Vertical label for when plotting.
    title : `string`
        Title for when plotting.
    x_scale : `string`
        The type of scaling to apply to the x axis for when plotting. Either `"linear"` for a linear scale, or `"log"` for a log scale.
    """
    def __init__(self, value, x_label, y_label, title, x_scale):
        super().__init__()
        self._value_ = value
        self.x_label = x_label
        self.y_label = y_label
        self.title = title
        self.x_scale = x_scale

    NONE = (
        "none",
        "Nothing (rad)",
        "RMS error",
        "Nothing",
        "log"
    )
    """
    No benchmark has been defined.
    """

    TIME_STEP_SOURCE = (
        "time_step_source",
        "Source time step (s)",
        "RMS error",
        "Effect of source time step size on RMS error",
        "log"
    )
    """
    The results of :func:`benchmark.manager.new_benchmark_trotter_cutoff()`.
    """

    TROTTER_CUTOFF = (
        "trotter_cutoff",
        "Trotter cutoff",
        "RMS error",
        "Effect of trotter cutoff on RMS error",
        "linear"
    )
    """
    The results of :func:`benchmark.manager.new_benchmark_trotter_cutoff()`.
    """

    TROTTER_CUTOFF_MATRIX = (
        "trotter_cutoff_matrix",
        "Trotter cutoff",
        "RMS error",
        "Effect of trotter cutoff on RMS error",
        "linear"
    )
    """
    The results of :func:`benchmark.manager.new_benchmark_trotter_cutoff_matrix()`.
    """

    TIME_STEP_FINE = (
        "time_step_fine",
        "Fine time step (s)",
        "RMS error",
        "Effect of fine time step size on RMS error",
        "log"
    )
    """
    The results of :func:`benchmark.manager.new_benchmark_time_step_fine()`.
    """

    TIME_STEP_FINE_FREQUENCY_DRIFT = (
        "time_step_fine_frequency_drift",
        "Fine time step (s)",
        "Frequency shift (Hz)",
        "Effect of fine time step size on frequency shift",
        "log"
    )
    """
    The results of :func:`benchmark.manager.new_benchmark_time_step_fine_frequency_drift()`.
    """

class BenchmarkResults:
    """
    A class that holds the results of an arbitrary benchmark, and has the ability to plot them.

    Attributes
    ----------
    benchmark_type : :class:`BenchmarkType`
        The benchmark that this was the result of. Also contains information used to archive and plot the results.
    parameter : :class:`numpy.ndarray`
        The value of the parameter being varied during the benchmark.
    error : :class:`numpy.ndarray`
        The error recorded during the benchmark.
    """
    def __init__(self, benchmark_type = BenchmarkType.NONE, parameter = None, error = None):
        """
        Parameters
        ----------
        benchmark_type : :class:`BenchmarkType`, optional
            The benchmark that this was the result of. Also contains information used to archive and plot the results. Defaults to :obj:`BenchmarkType.NONE`.
        parameter : :class:`numpy.ndarray`
            The value of the parameter being varied during the benchmark. Defaults to `None`.
        error : :class:`numpy.ndarray`
            The error recorded during the benchmark. Defaults to `None`.
        """
        self.benchmark_type = benchmark_type
        self.parameter = parameter
        self.error = error

    @staticmethod
    def read_from_archive(archive):
        """
        A constructor that reads a new benchmark result from a hdf5 file.

        Parameters
        ----------
        archive : :class:`archive.Archive`
            The archive object to read the benchmark from.
        """
        archive_group_benchmark = archive.archive_file["benchmark_results"]
        for benchmark_type in BenchmarkType:
            if benchmark_type.value in archive_group_benchmark.keys():
                archive_group_benchmark_results = archive_group_benchmark[benchmark_type.value]
                benchmark_results = BenchmarkResults(
                    benchmark_type,
                    archive_group_benchmark_results[benchmark_type.value],
                    archive_group_benchmark_results["error"]
                )
                return benchmark_results

    def write_to_archive(self, archive):
        """
        Save a benchmark to a hdf5 file.

        Parameters
        ----------
        archive : :class:`archive.Archive`
            The archive object to write the benchmark to.
        """
        archive_group_benchmark_results = archive.archive_file.require_group("benchmark_results/" + self.benchmark_type.value)
        archive_group_benchmark_results[self.benchmark_type.value] = self.parameter
        archive_group_benchmark_results["error"] = self.error

    def plot(self, archive = None, do_show_plot = True):
        """
        Plots the benchmark results.

        Parameters
        ----------
        archive : :class:`archive.Archive`, optional
            If specified, will save plots to the archive's `plot_path`.
        do_show_plot : `boolean`, optional
            If `True`, will attempt to show and save the plots. Can be set to false to overlay multiple archive results to be plotted later, as is done with :func:`benchmark_manager.plot_benchmark_comparison()`.
        """
        if do_show_plot:
            plt.figure()
            plt.plot(self.parameter[1:], self.error[1:], "rx--")
        else:
            plt.plot(self.parameter[1:], self.error[1:], "x--")
        plt.grid()
        plt.yscale("log")
        plt.xscale(self.benchmark_type.x_scale)
        plt.xlabel(self.benchmark_type.x_label)
        plt.ylabel(self.benchmark_type.y_label)
        if do_show_plot:
            if archive:
                plt.title(archive.execution_time_string + "\n" + self.benchmark_type.title)
                plt.savefig(archive.plot_path + "benchmark" + self.benchmark_type.value[0].capitalize() + self.benchmark_type.value[1:] + ".pdf")
                plt.savefig(archive.plot_path + "benchmark" + self.benchmark_type.value[0].capitalize() + self.benchmark_type.value[1:] + ".png")
            plt.show()

def plot_benchmark_comparison(archive, archive_times, legend, title):
    """
    Plots multiple benchmarks on one plot from previous archives.

    Parameters
    ----------
    archive : :class:`archive.Archive`
        Specifies the path to save the plot to.
    archive_times : `list` of `string`
        The identifiers of the archvies containing the benchmark results to be compared.
    legend : `list` of `string`
        Labels that describe what each of the benchmark result curves respresent.
    title : `string`
        What this comparison is trying to compare.
    """
    plt.figure()
    for archive_time in archive_times:
        archive_previous = Archive(archive.archive_path[:-25], "")
        archive_previous.open_archive_file(archive_time)
        benchmark_results = BenchmarkResults.read_from_archive(archive_previous)
        benchmark_results.plot(None, False)
        archive_previous.close_archive_file(False)
    plt.legend(legend)
    plt.title(archive.execution_time_string + "\n" + title)
    plt.savefig(archive.plot_path + "benchmark_comparison.pdf")
    plt.savefig(archive.plot_path + "benchmark_comparison.png")
    plt.show()

def new_benchmark_trotter_cutoff_matrix(archive, trotter_cutoff, norm_bound = 1.0):
    """
    Runs a benchmark for the trotter exponentiator :func:`utilities.matrixExponential_lie_trotter()` using arbitrary matrices. Uses :func:`benchmark_trotter_cutoff_matrix()` to execute the matrix exponentials.

    Specifically, let
    
    .. math::
        A_k = -i \\frac{\\nu}{4} (\\cos(k) F_x + \\cos(2k) F_y + \\cos(4k) F_z + \\cos(8k) F_q).

    See :func:`utilities.matrixExponential_lie_trotter()` for definitions of :math:`F` operators).

    Then :func:`utilities.matrixExponential_lie_trotter()` calculates the exponential of :math:`A_k` as

    .. math::
        E_{\\tau, k} = \\exp_\\tau(A_k).
    
    Let :math:`\\tau_0` be the first element in `trotter_cutoff`, ususally the largest. Then the error :math:`e_\\tau` is calculated as

    .. math::
        e_\\tau = \\frac{1}{\\#k}\\sum_{k, i, j} |(E_{\\tau, k})_{i,j} - E_{\\tau_0, k})_{i,j}|,

    where :math:`\\#k` is the number of matrices being considered in the benchmark (1e6).

    Parameters
    ----------
    archive : :class:`archive.Archive`
        Specifies where to save results and plots.
    trotter_cutoff : :class:`numpy.ndarray` of :class:`numpy.int`
        An array of values of the trotter cutoff to run the matrix exponentiator at.
    norm_bound : `float`, optional
        An upper bound to the size of the norm of the matrices being exponentiated, since :func:`utilities.matrixExponential_lie_trotter()` works better using matrices with smaller norms. See :math:`\\nu` above. Defaults to 1.

    Returns
    -------
    benchmark_results : :class:`benchmark_results.BenchmarkResults`
        Contains the errors found by the benchmark.
    """
    print("\033[33m_starting benchmark...\033[0m")
    time_index_max = 1000000
    result = np.empty((time_index_max, 3, 3), dtype = np.complex128)
    result_bench = np.empty((time_index_max, 3, 3), dtype = np.complex128)
    trotter_cutoff = np.asarray(trotter_cutoff)
    error = np.empty_like(trotter_cutoff, dtype = np.double)
    
    threads_per_block = 128
    blocks_per_grid = (time_index_max + (threads_per_block - 1)) // threads_per_block
    benchmark_trotter_cutoff_matrix[blocks_per_grid, threads_per_block](norm_bound, trotter_cutoff[0], result_bench)

    for trotter_cutoff_index in range(trotter_cutoff.size):
        benchmark_trotter_cutoff_matrix[blocks_per_grid, threads_per_block](norm_bound, trotter_cutoff[trotter_cutoff_index], result)
        result_difference = (result - result_bench)
        error[trotter_cutoff_index] = np.sqrt(np.sum(np.real(result_difference*np.conj(result_difference))))/time_index_max

    print("\033[32m_done!\033[0m")

    benchmark_results = BenchmarkResults(BenchmarkType.TROTTER_CUTOFF_MATRIX, trotter_cutoff, error)
    benchmark_results.write_to_archive(archive)
    benchmark_results.plot(archive)

    return benchmark_results

@cuda.jit
def benchmark_trotter_cutoff_matrix(norm_bound, trotter_cutoff, result):
    """
    Runs the exponentiations for the trotter matrix benchmark.

    Parameters
    ----------
    norm_bound : `float`, optional
        An upper bound to the size of the norm of the matrices being exponentiated, since :func:`utilities.matrixExponential_lie_trotter()` works better using matrices with smaller norms. Defaults to 1.
    trotter_cutoff : `int`
        The value trotter cutoff to run the matrix exponentiator at.
    result : :class:`numpy.ndarray` of :class:`numpy.cdouble`
        The results of the matrix exponentiations for this value of `trotter_cutoff`.
    """
    exponent = cuda.local.array((3, 3), dtype = nb.complex128)

    time_index = cuda.threadIdx.x + cuda.blockIdx.x*cuda.blockDim.x
    if time_index < result.shape[0]:
        x = norm_bound*math.cos(1.0*time_index)/4
        y = norm_bound*math.cos(2.0*time_index)/4
        z = norm_bound*math.cos(4.0*time_index)/4
        q = norm_bound*math.cos(8.0*time_index)/4

        exponent[0, 0] = -1j*(z + q/3)
        exponent[1, 0] = -1j*(x + 1j*y)/math.sqrt(2.0)
        exponent[2, 0] = 0.0

        exponent[0, 1] = -1j*(x - 1j*y)/math.sqrt(2.0)
        exponent[1, 1] = -1j*(-2/3)*q
        exponent[2, 1] = -1j*(x + 1j*y)/math.sqrt(2.0)

        exponent[0, 2] = 0.0
        exponent[1, 2] = -1j*(x - 1j*y)/math.sqrt(2.0)
        exponent[2, 2] = -1j*(-z + q/3)

        utilities.spin_one.matrixExponential_lie_trotter(exponent, result[time_index, :], trotter_cutoff)

def new_benchmark_trotter_cutoff(archive, signal, frequency, trotter_cutoff):
    """
    Runs a benchmark for the trotter exponentiator using the integrator.

    Specifically, let :math:`(\\psi_{f,\\tau})_{m,t}` be the calculated state of the spin system, with magnetic number (`state_index`) :math:`m` at time :math:`t`, simulated with a dressing of :math:`f` with a trotter cutoff of :math:`\\tau`. Let :math:`\\tau_0` be the first such trotter cutoff in `trotter_cutoff` (generally the largest one). Then the error :math:`e_\\tau` calculated by this benchmark is

    .. math::
        \\begin{align*}
            e_\\tau &= \\frac{1}{\\#t\\#f}\\sum_{t,f,m} |(\\psi_{f,\\tau})_{m,t} - (\\psi_{f,\\tau_0})_{m,t}|,
        \\end{align*}

    where :math:`\\#t` is the number of coarse time samples, :math:`\\#f` is the length of `frequency`.

    Parameters
    ----------
    archive : :class:`archive.Archive`
        Specifies where to save results and plots.
    signal : `list` of :class:`test_signal.TestSignal`
        The signals being simulated in the benchmark.
    frequency : :class:`numpy.ndarray` of :class:`numpy.double`
        The dressing frequencies being simulated in the benchmark.
    trotter_cutoff : :class:`numpy.ndarray` of :class:`numpy.int`
        An array of values of the trotter cutoff to run the simulations at. The accuracy of the simulation output with each of these values are then compared.

    Returns
    -------
    benchmark_results : :class:`benchmark_results.BenchmarkResults`
        Contains the errors found by the benchmark.
    """
    state_output = []
    error = []
    simulation_manager = manager.SimulationManager(signal, frequency, archive, None, state_output, trotter_cutoff)
    simulation_manager.evaluate(False)
    for trotter_cutoff_index in range(trotter_cutoff.size):
        error_temp = 0
        for frequency_index in range(frequency.size):
            state_difference = state_output[frequency_index + trotter_cutoff_index*frequency.size] - state_output[frequency_index]
            error_temp += np.sum(np.sqrt(np.real(np.conj(state_difference)*state_difference)))
        error += [error_temp/(frequency.size*state_output[0].size)]
    
    trotter_cutoff = np.asarray(trotter_cutoff)
    error = np.asarray(error)

    benchmark_results = BenchmarkResults(BenchmarkType.TROTTER_CUTOFF, trotter_cutoff, error)
    benchmark_results.write_to_archive(archive)
    benchmark_results.plot(archive)

    return benchmark_results

def new_benchmark_time_step_fine(archive, signal_template, frequency, time_step_fine):
    """
    Runs a benchmark to test error induced by raising the size of the time step in the integrator, comparing the output state.

    Specifically, let :math:`(\\psi_{f,\\mathrm{d}t})_{m,t}` be the calculated state of the spin system, with magnetic number (`state_index`) :math:`m` at time :math:`t`, simulated with a dressing of :math:`f` with a fine time step of :math:`\\mathrm{d}t`. Let :math:`\\mathrm{d}t_0` be the first such time step in `time_step_fine` (generally the smallest one). Then the error :math:`e_{\\mathrm{d}t}` calculated by this benchmark is

    .. math::
        \\begin{align*}
            e_{\\mathrm{d}t} &= \\frac{1}{\\#t\\#f}\\sum_{t,f,m} |(\\psi_{f,\\mathrm{d}t})_{m,t} - (\\psi_{f,\\mathrm{d}t_0})_{m,t}|,
        \\end{align*}

    where :math:`\\#t` is the number of coarse time samples, :math:`\\#f` is the length of `frequency`.

    Parameters
    ----------
    archive : :class:`archive.Archive`
        Specifies where to save results and plots.
    signal_template : :class:`test_signal.TestSignal`
        A description of the signal to use for the environment during the spinsim. For each entry in `time_step_fine`, this template is modified so that its :attr:`test_signal.TestSignal.time_properties.time_step_fine` is equal to that entry. All modified versions of the signal are then simulated for comparison.
    frequency : :class:`numpy.ndarray` of :class:`numpy.double`
        The dressing frequencies being simulated in the benchmark.
    time_step_fine : :class:`numpy.ndarray` of :class:`numpy.double`
        An array of time steps to run the simulations with. The accuracy of the simulation output with each of these values are then compared.

    Returns
    -------
    benchmark_results : :class:`benchmark_results.BenchmarkResults`
        Contains the errors found by the benchmark.
    """
    time_step_fine = np.asarray(time_step_fine)
    state_output = []
    error = []

    signal = []
    for timeStep_fine_instance in time_step_fine:
        time_properties = test_signal.TimeProperties(signal_template.time_properties.time_step_coarse, timeStep_fine_instance, signal_template.time_properties.time_step_source)
        signal_instance = test_signal.TestSignal(signal_template.neural_pulses, signal_template.sinusoidal_noises, time_properties, False)
        signal += [signal_instance]

    simulation_manager = manager.SimulationManager(signal, frequency, archive, None, state_output)
    simulation_manager.evaluate(False)

    for timeStep_fine_index in range(time_step_fine.size):
        error_temp = 0
        for frequency_index in range(frequency.size):
            state_difference = state_output[frequency_index + timeStep_fine_index*frequency.size] - state_output[frequency_index]
            error_temp += np.sum(np.sqrt(np.real(np.conj(state_difference)*state_difference)))
        error += [error_temp/(frequency.size*state_output[0].size)]
    
    error = np.asarray(error)

    benchmark_results = BenchmarkResults(BenchmarkType.TIME_STEP_FINE, time_step_fine, error)
    benchmark_results.write_to_archive(archive)
    benchmark_results.plot(archive)

    return benchmark_results

def new_benchmark_time_step_source(archive, signal_template, frequency, state_properties, time_step_source):
    """
    Runs a benchmark to test error induced by raising the size of the time step in the integrator, comparing the output state.

    Specifically, let :math:`(\\psi_{f,\\mathrm{d}t})_{m,t}` be the calculated state of the spin system, with magnetic number (`state_index`) :math:`m` at time :math:`t`, simulated with a dressing of :math:`f` with a fine time step of :math:`\\mathrm{d}t`. Let :math:`\\mathrm{d}t_0` be the first such time step in `time_step_fine` (generally the smallest one). Then the error :math:`e_{\\mathrm{d}t}` calculated by this benchmark is

    .. math::
        \\begin{align*}
            e_{\\mathrm{d}t} &= \\frac{1}{\\#t\\#f}\\sum_{t,f,m} |(\\psi_{f,\\mathrm{d}t})_{m,t} - (\\psi_{f,\\mathrm{d}t_0})_{m,t}|,
        \\end{align*}

    where :math:`\\#t` is the number of coarse time samples, :math:`\\#f` is the length of `frequency`.

    Parameters
    ----------
    archive : :class:`archive.Archive`
        Specifies where to save results and plots.
    signal_template : :class:`test_signal.TestSignal`
        A description of the signal to use for the environment during the spinsim. For each entry in `time_step_fine`, this template is modified so that its :attr:`test_signal.TestSignal.time_properties.time_step_fine` is equal to that entry. All modified versions of the signal are then simulated for comparison.
    frequency : :class:`numpy.ndarray` of :class:`numpy.double`
        The dressing frequencies being simulated in the benchmark.
    time_step_fine : :class:`numpy.ndarray` of :class:`numpy.double`
        An array of time steps to run the simulations with. The accuracy of the simulation output with each of these values are then compared.

    Returns
    -------
    benchmark_results : :class:`benchmark_results.BenchmarkResults`
        Contains the errors found by the benchmark.
    """
    time_step_source = np.asarray(time_step_source)
    state_output = []
    error = []

    signal = []
    for timeStep_source_instance in time_step_source:
        time_properties = test_signal.TimeProperties(signal_template.time_properties.time_step_coarse, signal_template.time_properties.time_step_fine, timeStep_source_instance)
        signal_instance = test_signal.TestSignal(signal_template.neural_pulses, signal_template.sinusoidal_noises, time_properties, False)
        signal += [signal_instance]

    simulation_manager = manager.SimulationManager(signal, frequency, archive, state_properties, state_output)
    simulation_manager.evaluate(False)

    for timeStep_source_index in range(time_step_source.size):
        error_temp = 0
        for frequency_index in range(frequency.size):
            state_difference = state_output[frequency_index + timeStep_source_index*frequency.size] - state_output[frequency_index]
            error_temp += np.sum(np.sqrt(np.real(np.conj(state_difference)*state_difference)))
        error += [error_temp/(frequency.size*state_output[0].size)]
    
    error = np.asarray(error)

    benchmark_results = BenchmarkResults(BenchmarkType.TIME_STEP_SOURCE, time_step_source, error)
    benchmark_results.write_to_archive(archive)
    benchmark_results.plot(archive)

    return benchmark_results

def new_benchmark_time_step_fine_frequency_drift(archive, signal_template, time_step_fines, dressing_frequency):
    """
    Runs a benchmark to test error induced by raising the size of the time step in the integrator, comparing measured frequency coefficients.

    Parameters
    ----------
    archive : :class:`archive.Archive`
        Specifies where to save results and plots.
    signal_template : :class:`test_signal.TestSignal`
        A description of the signal to use for the environment during the spinsim. For each entry in `time_step_fines`, this template is modified so that its :attr:`test_signal.TestSignal.time_properties.time_step_fine` is equal to that entry. All modified versions of the signal are then simulated for comparison.
    time_step_fines : :class:`numpy.ndarray` of :class:`numpy.double`
        An array of time steps to run the simulations with. The accuracy of the simulation output with each of these values are then compared.
    dressing_frequency : :class:`numpy.ndarray` of :class:`numpy.double`
        The dressing frequencies being simulated in the benchmark.
    """
    dressing_frequency = np.asarray(dressing_frequency)
    signal_template.get_amplitude()
    signal_template.get_frequency_amplitude()

    signals = []
    for time_step_fine in time_step_fines:
        time_properties = test_signal.TimeProperties(signal_template.time_properties.time_step_coarse, time_step_fine, signal_template.time_properties.time_step_source)
        signal = test_signal.TestSignal(signal_template.neural_pulses, signal_template.sinusoidal_noises, time_properties)
        signals += [signal]

    simulation_manager = manager.SimulationManager(signals, dressing_frequency, archive)
    simulation_manager.evaluate()

    frequency_drift = np.zeros(len(signals))
    for signal_index in range(len(signals)):
        for frequency_index, frequency in enumerate(dressing_frequency):
            frequency_drift[signal_index] += np.abs(simulation_manager.frequency_amplitude[frequency_index + signal_index*dressing_frequency.size] - signal_template.frequency_amplitude[signal_template.frequency == frequency])
        frequency_drift[signal_index] /= dressing_frequency.size

    benchmark_results = BenchmarkResults(BenchmarkType.TIME_STEP_FINE_FREQUENCY_DRIFT, np.asarray(time_step_fines), frequency_drift)
    benchmark_results.write_to_archive(archive)
    benchmark_results.plot(archive)

    return benchmark_results