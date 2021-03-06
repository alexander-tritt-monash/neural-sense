import numpy as np
import matplotlib.pyplot as plt
# import sys, getopt      # Command line arguments
from numba import cuda  # GPU code
import colorama         # Colourful terminal
colorama.init()

# The different pieces that make up this sensing code
import archive as arch              # Saving results and configurations
from archive import handle_arguments

import test_signal                  # The properties of the magnetic signal, used for simulations and reconstructions
import spinsim                      # Main simulation package
import reconstruction as recon      # Uses compressive sensing to reconstruct the a magnetic signal

import sim

if __name__ == "__main__":
    # This will be recorded in the HDF5 file to give context for what was being tested
    description_of_test = "Arbitrary input"

    # Check to see if there is a compatible GPU
    if cuda.list_devices():
        print("\033[32mUsing cuda device {}\033[0m".format(cuda.list_devices()[0].name.decode('UTF-8')))
    else:
        print("\033[31mNo cuda devices found. System is incompatible. Exiting...\033[0m")
        exit()

    profile_state, archive_path = handle_arguments()

    # Initialise
    # cuda.profile_start()
    np.random.seed()

    # Make archive
    archive = arch.Archive(archive_path, description_of_test, profile_state)
    if profile_state != arch.ProfileState.ARCHIVE:
        archive.new_archive_file()

        # # Make signal
        # time_properties = test_signal.TimeProperties(5e-7, 1e-7, 1e-8, [0, 0.1])
        # signal = test_signal.TestSignal(
        #     # [],
        #     [test_signal.NeuralPulse(0.02333333, 10.0, 1000), test_signal.NeuralPulse(0.0444444444, 10.0, 1000)],
        #     # [NeuralPulse(0.02333333, 10.0, 1000)],
        #     [],
        #     # [SinusoidalNoise.new_detuning_noise(10)],
        #     time_properties
        # )
        # signal.write_to_file(archive.archive_file)

        # # Make state
        # # [0.5, 1/np.sqrt(2), 0.5]
        # state_properties = sim.manager.StateProperties(spinsim.SpinQuantumNumber.ONE)

        cuda.profile_start()

        # Time step fine test
        # time_step_fine = [5e-9, 1e-8, 2e-8, 2.5e-8, 4e-8, 5e-8, 1e-7, 2e-7, 2.5e-7, 4e-7, 5e-7, 1e-6, 2e-6, 2.5e-6, 5e-6]
        # time_step_fine = time_properties.time_step_coarse/np.floor(np.logspace(np.log10(200), np.log10(1), 50))
        # frequency = np.arange(50, 3051, 300)
        # time_step_fine = time_properties.time_step_coarse/np.floor(np.logspace(np.log10(200), np.log10(1), 10))
        # frequency = np.arange(50, 3051, 300)
        # frequency = np.arange(1000, 1003, 5)
        # sim.benchmark.new_benchmark_time_step_fine(archive, signal, frequency, time_step_fine, state_properties)
        # frequency = np.asarray([1000], dtype = np.float64)
        # time_step_fine = time_properties.time_step_coarse/np.floor(np.logspace(np.log10(200), np.log10(1), 10))
        # sim.benchmark.new_benchmark_scipy(archive, signal, frequency, time_step_fine, state_properties)

        # # Time test
        # frequency = np.arange(50, 3051, 1000)
        # sim.benchmark.new_benchmark_device(archive, signal, frequency, state_properties)

        # # Device aggregate
        # sim.benchmark.new_benchmark_device_aggregate(archive, ["20201208T132324", "20201214T183902", "20210414T123425"])

        # # Time step source test
        # time_step_source = np.logspace(-9, -6, 50)
        # frequency = np.arange(50, 3051, 300)
        # # frequency = np.arange(1000, 1003, 5)
        # sim.benchmark.new_benchmark_time_step_source(archive, signal, frequency, state_properties, time_step_source)

        # sim.benchmark.plot_benchmark_comparison(archive, ["20201113T173915", "20201113T202948", "20201113T204017", "20201113T205415", "20201113T210439", "20201113T211136"], ["CF4 RF", "CF4 LF", "HS RF", "HS LF", "MP RF", "MP LF"], "Effect of integration method on fine timestep benchmark (spin one)")

        # sim.benchmark.plot_benchmark_comparison(archive, ["20201116T110647", "20201116T111313", "20201116T111851", "20201116T112430", "20201116T112932", "20201116T113330"], ["CF4 RF", "CF4 LF", "HS RF", "HS LF", "MP RF", "MP LF"], "Effect of integration method on fine timestep benchmark\n(spin half, lie trotter)")

        sim.benchmark.plot_benchmark_comparison(archive, ["20201119T181459", "20201119T181809", "20201119T182040", "20201119T182334", "20201119T182612", "20201119T182817"], ["CF4 RF", "CF4 LF", "HS RF", "HS LF", "MP RF", "MP LF"], "Effect of integration method on fine timestep benchmark\n(spin half, analytic)")

        # # Trotter Test
        # sim.benchmark.new_benchmark_trotter_cutoff_matrix(archive, np.arange(80, 0, -4), 1e1)
        # # frequency = np.arange(50, 3051, 300)
        # # frequency = np.arange(50, 3051, 30)
        # # newBenchmark_trotter_cutoff(archive, signal, frequency, np.arange(60, 0, -4))
        
        # # Run simulations
        # frequency = np.arange(70, 3071, 30)
        # # frequency = np.arange(50, 3051, 3)
        # # frequency = np.arange(1000, 1003, 1)
        # simulation_manager = sim.manager.SimulationManager(signal, frequency, archive, state_properties)
        # simulation_manager.evaluate(False, False)
        # # experiment_results = ExperimentResults(simulation_manager.frequency, simulation_manager.frequency_amplitude)
        # experiment_results = sim.manager.ExperimentResults.new_from_simulation_manager(simulation_manager)
        # experiment_results.write_to_archive(archive)
        # experiment_results.plot(archive, signal)

        # # Make reconstructions
        # reconstruction = recon.Reconstruction(signal.time_properties)
        # reconstruction.readFrequenciesFrom_experiment_results(experiment_results)
        # # reconstruction.readFrequenciesFrom_test_signal(signal)
        # reconstruction.evaluateFISTA()
        # # reconstruction.evaluateISTAComplete()
        # reconstruction.plot(archive, signal)
        # reconstruction.write_to_file(archive.archive_file)

        # Clean up
        archive.close_archive_file()
        cuda.profile_stop()
        cuda.close()