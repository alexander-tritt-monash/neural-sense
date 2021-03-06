import numpy as np
import matplotlib.pyplot as plt
import math
from numba import cuda
import numba as nb
import time as tm

from test_signal import *

class Reconstruction():
    """
    Controls a reconstruction of the signal from Fourier sine coefficients using compressive sensing
    """
    def __init__(self, time_properties, step_size_sparse = 0.1, step_size_manifold = 100000):
        self.time_properties = time_properties
        self.frequency = None
        self.frequency_amplitude = None
        self.amplitude = None

        self.step_size_sparse = step_size_sparse
        self.step_size_manifold = step_size_manifold

    def read_frequencies_directly(self, frequency, frequency_amplitude, number_of_samples = 100, frequency_cutoff = 3000):
        """
        Import arbitrary frequency values for reconstruction
        """
        permutation = np.random.choice(range(np.sum(frequency < frequency_cutoff)), number_of_samples)
        self.frequency = np.ascontiguousarray(frequency[permutation])
        self.frequency_amplitude = np.ascontiguousarray(frequency_amplitude[permutation])

    def read_frequencies_from_experiment_results(self, experiment_results, number_of_samples = 100, frequency_cutoff = 100000):
        """
        Import frequency values from an experimental results object
        """
        self.read_frequencies_directly(experiment_results.frequency, experiment_results.frequency_amplitude, number_of_samples, frequency_cutoff)

    def read_frequencies_from_test_signal(self, test_signal):
        """
        Import frequency values from the dot product Fourier transform of a signal
        """
        self.read_frequencies_directly(test_signal.frequency, test_signal.frequency_amplitude)

    def write_to_file(self, archive):
        """
        Save the reconstruction results to a hdf5 file
        """
        archive_group_reconstruction = archive.require_group("reconstruction")
        self.time_properties.write_to_file(archive_group_reconstruction)
        archive_group_reconstruction["frequency"] = self.frequency
        archive_group_reconstruction["frequency_amplitude"] = self.frequency_amplitude
        archive_group_reconstruction["amplitude"] = self.amplitude

    def plot(self, archive, test_signal):
        """
        Plot the reconstruction signal, possibly against a template test signal
        """
        plt.figure()
        if test_signal is not None:
            plt.plot(test_signal.time_properties.time_coarse, test_signal.amplitude, "-k")
        plt.plot(self.time_properties.time_coarse, self.amplitude, "-r")
        if test_signal is not None:
            plt.legend(["Original", "Reconstruction"])
        plt.xlabel("Time (s)")
        plt.ylabel("Amplitude (Hz)")
        plt.grid()
        plt.title(archive.execution_time_string + "Reconstruction")
        plt.savefig(archive.plot_path + "reconstruction.pdf")
        plt.savefig(archive.plot_path + "reconstruction.png")
        plt.show()

    def evaluate_ista_complete(self):
        """
        Run compressive sensing based on the Iterative Shrinkage Thresholding Algorithm (ISTA)
        """
        print("\033[33m_starting reconstruction...\033[0m")

        # Start timing reconstruction
        executionTime_end_points = np.empty(2)
        executionTime_end_points[0] = tm.time()
        executionTime_end_points[1] = executionTime_end_points[0]

        self.amplitude = np.empty_like(self.time_properties.time_coarse)                          # Reconstructed signal
        frequency_amplitude_prediction = np.empty_like(self.frequency_amplitude)                   # Partial sine Fourier transform of reconstructed signal
        fourier_transform = np.empty((self.frequency.size, self.time_properties.time_coarse.size)) # Storage for sine Fourier transform operator

        # Setup GPU block and grid sizes
        threads_per_block = 128
        blocksPer_grid_time = (self.time_properties.time_coarse.size + (threads_per_block - 1)) // threads_per_block

        reconstruct_ista_complete[blocksPer_grid_time, threads_per_block](self.time_properties.time_coarse, self.amplitude, self.frequency, self.frequency_amplitude, frequency_amplitude_prediction, fourier_transform, self.time_properties.time_step_coarse, 0, 100.0, 10.0)

        print(str(tm.time() - executionTime_end_points[1]) + "s")
        print("\033[32m_done!\033[0m")
        executionTime_end_points[1] = tm.time()

    def evaluate_fista(self):
        """
        Run compressive sensing based on the Fast Iterative Shrinkage Thresholding Algorithm (FISTA)
        """
        print("\033[33m_starting reconstruction...\033[0m")

        # Start timing reconstruction
        executionTime_end_points = np.empty(2)
        executionTime_end_points[0] = tm.time()
        executionTime_end_points[1] = executionTime_end_points[0]

        self.amplitude = np.empty_like(self.time_properties.time_coarse)                          # Reconstructed signal
        frequency_amplitude_prediction = np.empty_like(self.frequency_amplitude)                   # Partial sine Fourier transform of reconstructed signal
        fourier_transform = np.empty((self.frequency.size, self.time_properties.time_coarse.size)) # Storage for sine Fourier transform operator

        # Setup GPU block and grid sizes
        threads_per_block = 128
        blocksPer_grid_time = (self.time_properties.time_coarse.size + (threads_per_block - 1)) // threads_per_block
        blocksPer_grid_frequency = (self.frequency.size + (threads_per_block - 1)) // threads_per_block

        # Initialise 
        reconstruct_ista_initialisation_step[blocksPer_grid_time, threads_per_block](self.frequency, self.frequency_amplitude, self.time_properties.time_step_coarse, self.time_properties.time_coarse, self.amplitude, fourier_transform)

        amplitude_previous = 0*self.amplitude    # The last amplitude, used in the fast step, and to check (Cauchy) convergence
        fast_step_size = 1                        # Initialise the fast step size to one
        fastStep_size_previous = 1

        while sum((self.amplitude - amplitude_previous)**2) > 1e0:   # Stop if signal has converged
            amplitude_previous = 1*self.amplitude    # Keep track of previous amplitude

            # Run ISTA steps
            reconstruct_ista_prediction_step[blocksPer_grid_frequency, threads_per_block](self.frequency_amplitude, self.amplitude, fourier_transform, frequency_amplitude_prediction)
            reconstruct_sista_manifold_step[blocksPer_grid_time, threads_per_block](frequency_amplitude_prediction, self.step_size_manifold, fourier_transform, self.amplitude)
            reconstruct_ista_sparse_step[blocksPer_grid_time, threads_per_block](self.step_size_sparse, self.amplitude)

            # Run the fast step
            fastStep_size_previous = fast_step_size
            fast_step_size = (1 + math.sqrt(1 + 4*fast_step_size**2))/2
            self.amplitude = self.amplitude + ((fastStep_size_previous - 1)/fast_step_size)*(self.amplitude - amplitude_previous)

        print(str(tm.time() - executionTime_end_points[1]) + "s")
        print("\033[32m_done!\033[0m")
        executionTime_end_points[1] = tm.time()
    
    def evaluate_naive_ista(self):
        """
        Run compressive sensing based on the Iterative Shrinkage Thresholding Algorithm (ISTA).
        The same as FISTA, but without the fast step.
        """
        self.amplitude = np.empty_like(self.time_properties.time_coarse)
        frequency_amplitude_prediction = np.empty_like(self.frequency_amplitude)
        fourier_transform = np.empty((self.frequency.size, self.time_properties.time_coarse.size))

        threads_per_block = 128
        blocksPer_grid_time = (self.time_properties.time_coarse.size + (threads_per_block - 1)) // threads_per_block
        blocksPer_grid_frequency = (self.frequency.size + (threads_per_block - 1)) // threads_per_block
        reconstructNaive_initialisation_step[blocksPer_grid_time, threads_per_block](self.frequency, self.frequency_amplitude, self.time_properties.time_step_coarse, self.time_properties.time_coarse, self.amplitude, fourier_transform)
        # manifold_step_size = 100000
        reconstructNaive_prediction_step[blocksPer_grid_frequency, threads_per_block](self.frequency_amplitude, self.amplitude, fourier_transform, frequency_amplitude_prediction)
        square_loss = sum(frequency_amplitude_prediction**2)

        # frequency = cuda.to_device(frequency)
        # frequency_amplitude = cuda.to_device(frequency_amplitude)
        # frequency_amplitude_prediction = cuda.to_device(frequency_amplitude_prediction)
        # time_coarse = cuda.to_device(time_coarse)
        # amplitude = cuda.to_device(amplitude)
        # print(square_loss)

        # plt.figure()
        # plt.plot(time_coarse, amplitude)
        # plt.show()
        amplitude_previous = 0*self.amplitude
        while sum((self.amplitude - amplitude_previous)**2) > 1:
            # if iteration_index == 0:
            #     manifold_step_size = 2
            # else:
            #     manifold_step_size = 0.00005
            # if square_loss < 1e-4:
            amplitude_previous = 1*self.amplitude
            reconstruct_ista_sparse_step[blocksPer_grid_time, threads_per_block](self.step_size_sparse, self.amplitude)
            reconstruct_ista_prediction_step[blocksPer_grid_frequency, threads_per_block](self.frequency_amplitude, self.amplitude, fourier_transform, frequency_amplitude_prediction)
            # square_loss_previous = square_loss
            # square_loss = sum(frequency_amplitude_prediction**2)
            # if square_loss > square_loss_previous:
            #     manifold_step_size *= 2
            # else:
            #     manifold_step_size /= 2
            reconstruct_sista_manifold_step[blocksPer_grid_time, threads_per_block](frequency_amplitude_prediction, self.step_size_manifold, fourier_transform, self.amplitude)
            # if iteration_index % 1 == 0:
            #     # print(square_loss)
            #     # print(frequency_amplitude_prediction)

            #     plt.figure()
            #     plt.plot(time_coarse, amplitude)
            #     plt.show()

        # time_coarse = time_coarse.copy_to_host()
        # amplitude = amplitude.copy_to_host()
        # plt.figure()
        # plt.plot(self.time_properties.time_coarse, self.amplitude)
        # plt.show()

@cuda.jit()
def reconstruct_ista_complete(
    time_coarse, amplitude,                                          # Time
    frequency, frequency_amplitude, frequency_amplitude_prediction,    # Frequency
    fourier_transform, time_step_coarse,                               # Parameters
    sparse_penalty, min_accuracy, expected_amplitude                   # Parameters
):
    # Initialise
    time_index = cuda.threadIdx.x + cuda.blockIdx.x*cuda.blockDim.x
    if time_index < time_coarse.size:
        amplitude[time_index] = 0.0
        for frequency_index in range(frequency.size):
            # Find the Fourier transform coefficient
            fourier_transform[frequency_index, time_index] = math.sin(2*math.pi*frequency[frequency_index]*time_coarse[time_index])*time_step_coarse/(time_coarse[time_coarse.size - 1] - time_coarse[0])
            # # Apply the Moore–Penrose inverse of the Fourier transform, based off its SVD
            # amplitude[time_index] += fourier_transform[frequency_index, time_index]*(2.0*(time_coarse[time_coarse.size - 1] - time_coarse[0])/(time_step_coarse))*frequency_amplitude[frequency_index]

    step_size = (time_coarse[time_coarse.size - 1] - time_coarse[0])/time_step_coarse
    max_iteration_index = math.ceil((((expected_amplitude/(1e3*time_step_coarse))**2)/min_accuracy)/step_size)
    for iteration_index in range(max_iteration_index):
        # Prediction
        cuda.syncthreads()
        frequency_index = cuda.threadIdx.x + cuda.blockIdx.x*cuda.blockDim.x
        if frequency_index < frequency_amplitude_prediction.size:
            frequency_amplitude_prediction[frequency_index] = -frequency_amplitude[frequency_index]
            for time_index in range(time_coarse.size):
                frequency_amplitude_prediction[frequency_index] += fourier_transform[frequency_index, time_index]*0.0#amplitude[time_index]

        if cuda.threadIdx.x + cuda.blockIdx.x*cuda.blockDim.x == 0:
            print(frequency_amplitude_prediction[frequency_index], frequency_amplitude[frequency_index], amplitude[time_coarse.size - 1])

        # Linear inverse
        cuda.syncthreads()
        time_index = cuda.threadIdx.x + cuda.blockIdx.x*cuda.blockDim.x
        if time_index < time_coarse.size:
            for frequency_index in range(frequency_amplitude_prediction.size):
                amplitude[time_index] -= 2*fourier_transform[frequency_index, time_index]*(frequency_amplitude_prediction[frequency_index])*step_size

        # Shrinkage
        amplitude_temporary = math.fabs(amplitude[time_index]) - step_size*sparse_penalty
        if amplitude_temporary > 0:
            amplitude[time_index] = math.copysign(amplitude_temporary, amplitude[time_index])  # Apparently normal "sign" doesn't exist, but this weird thing does :P
        else:
            amplitude[time_index] = 0


@cuda.jit()
def reconstruct_ista_initialisation_step(frequency, frequency_amplitude, time_step_coarse, time_coarse, amplitude, fourier_transform):
    """
    Generate the Fourier transform matrix, and use the Moore–Penrose inverse to initialise the
    reconstruction to an allowed (but not optimal) solution
    """
    time_index = cuda.threadIdx.x + cuda.blockIdx.x*cuda.blockDim.x
    if time_index < time_coarse.size:
        amplitude[time_index] = 0
        for frequency_index in range(frequency.size):
            # Find the Fourier transform coefficient
            fourier_transform[frequency_index, time_index] = math.sin(2*math.pi*frequency[frequency_index]*time_coarse[time_index])*time_step_coarse/time_coarse[time_coarse.size - 1]
            # Apply the Moore–Penrose inverse of the Fourier transform, based off its SVD
            amplitude[time_index] += 2*fourier_transform[frequency_index, time_index]*(time_coarse[time_coarse.size - 1]/(time_step_coarse))*frequency_amplitude[frequency_index]

@cuda.jit()
def reconstruct_ista_sparse_step(step_size, amplitude):
    """
    Use gradient decent to minimise the one norm of the reconstruction (ie make it sparse)

    min Z(r),
    Z(r) = norm1(r) (in time),
    dZ(r)/dr(t) = sign(r(t))

    This algorithm is equivalent to
    
    r = sign(r)*ReLU(abs(r) - step_size)

    from the paper on FISTA.
    """
    time_index = cuda.threadIdx.x + cuda.blockIdx.x*cuda.blockDim.x
    if time_index < amplitude.size:
        amplitude_previous = amplitude[time_index]
        if amplitude_previous > 0:
            amplitude[time_index] -= step_size
        elif amplitude_previous < 0:
            amplitude[time_index] += step_size
        # Set to zero rather than oscillate
        if amplitude[time_index]*amplitude_previous < 0:
            amplitude[time_index] = 0

@cuda.jit()
def reconstruct_ista_prediction_step(frequency_amplitude, amplitude, fourier_transform, frequency_amplitude_prediction):
    """
    Take the sine Fourier transform of the reconstructed signal, and compare it to the measured frequency components. Returns the difference.
    """
    frequency_index = cuda.threadIdx.x + cuda.blockIdx.x*cuda.blockDim.x
    if frequency_index < frequency_amplitude_prediction.size:
        frequency_amplitude_prediction[frequency_index] = -frequency_amplitude[frequency_index]
        for time_index in range(amplitude.size):
            frequency_amplitude_prediction[frequency_index] += fourier_transform[frequency_index, time_index]*amplitude[time_index]

@cuda.jit()
def reconstruct_sista_manifold_step(frequency_amplitude_prediction, step_size, fourier_transform, amplitude):
    """
    Use gradient decent to bring the reconstruction closer to having the correct partial sine Fourier transform.

    min X(r),
    X(r) = norm2(S r - s) (in frequency)
    dX(r)/dr = 2 S^T (S r - s)
    """
    time_index = cuda.threadIdx.x + cuda.blockIdx.x*cuda.blockDim.x
    if time_index < amplitude.size:
        for frequency_index in range(frequency_amplitude_prediction.size):
            amplitude[time_index] -= fourier_transform[frequency_index, time_index]*(frequency_amplitude_prediction[frequency_index])*step_size