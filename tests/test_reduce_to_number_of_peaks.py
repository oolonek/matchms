import numpy
import pytest
from testfixtures import LogCapture
from matchms import Spectrum
from matchms.filtering import reduce_to_number_of_peaks
from matchms.logging_functions import reset_matchms_logger
from matchms.logging_functions import set_matchms_logger_level


def test_reduce_to_number_of_peaks_no_params():
    """Use default parameters."""
    mz = numpy.array([10, 20, 30, 40], dtype="float")
    intensities = numpy.array([0, 1, 10, 100], dtype="float")
    spectrum_in = Spectrum(mz=mz, intensities=intensities)

    spectrum = reduce_to_number_of_peaks(spectrum_in)

    assert spectrum == spectrum_in, "Expected no changes."


def test_reduce_to_number_of_peaks_no_params_w_parent_mass():
    """Use default parameters with present parent mass."""
    mz = numpy.array([10, 20, 30, 40], dtype="float")
    intensities = numpy.array([0, 1, 10, 100], dtype="float")
    spectrum_in = Spectrum(mz=mz, intensities=intensities,
                           metadata={"parent_mass": 50})

    spectrum = reduce_to_number_of_peaks(spectrum_in)

    assert spectrum == spectrum_in, "Expected no changes."


def test_reduce_to_number_of_peaks_set_to_none():
    """Test is spectrum is set to None if not enough peaks."""
    set_matchms_logger_level("INFO")
    mz = numpy.array([10, 20], dtype="float")
    intensities = numpy.array([0.5, 1], dtype="float")
    spectrum_in = Spectrum(mz=mz, intensities=intensities,
                           metadata={"parent_mass": 50})

    with LogCapture() as log:
        spectrum = reduce_to_number_of_peaks(spectrum_in, n_required=5)

    assert spectrum is None, "Expected spectrum to be set to None."
    log.check(
        ('matchms', 'INFO', "Spectrum with 2 (<5) peaks was set to None.")
    )
    reset_matchms_logger()


def test_reduce_to_number_of_peaks_n_max_4():
    """Test setting n_max parameter."""
    mz = numpy.array([10, 20, 30, 40, 50], dtype="float")
    intensities = numpy.array([1, 1, 10, 20, 100], dtype="float")
    spectrum_in = Spectrum(mz=mz, intensities=intensities)

    spectrum = reduce_to_number_of_peaks(spectrum_in, n_max=4)

    assert len(spectrum.peaks) == 4, "Expected that only 4 peaks remain."
    assert spectrum.peaks.mz.tolist() == [20., 30., 40., 50.], "Expected different peaks to remain."


def test_reduce_to_number_of_peaks_ratio_given_but_no_parent_mass():
    """A ratio_desired given without parent_mass should raise an exception."""
    mz = numpy.array([10, 20, 30, 40], dtype="float")
    intensities = numpy.array([0, 1, 10, 100], dtype="float")
    spectrum_in = Spectrum(mz=mz, intensities=intensities)

    with pytest.raises(Exception) as msg:
        _ = reduce_to_number_of_peaks(spectrum_in, n_required=4, ratio_desired=0.1)

    expected_msg = "Cannot use ratio_desired for spectrum without parent_mass."
    assert expected_msg in str(msg.value), "Expected specific exception message."


def test_reduce_to_number_of_peaks_required_2_desired_2():
    """Here: ratio_desired * parent_mass is 2, same as n_required."""
    mz = numpy.array([10, 20, 30, 40], dtype="float")
    intensities = numpy.array([0, 1, 10, 100], dtype="float")
    spectrum_in = Spectrum(mz=mz, intensities=intensities,
                           metadata={"parent_mass": 20})

    spectrum = reduce_to_number_of_peaks(spectrum_in, n_required=2, n_max=4, ratio_desired=0.1)

    assert len(spectrum.peaks) == 2, "Expected that only 2 peaks remain."
    assert spectrum.peaks.mz.tolist() == [30., 40.], "Expected different peaks to remain."


def test_reduce_to_number_of_peaks_required_3_desired_2():
    """Here: ratio_desired * parent_mass is 2, less than n_required."""
    mz = numpy.array([10, 20, 30, 40], dtype="float")
    intensities = numpy.array([0, 1, 10, 100], dtype="float")
    spectrum_in = Spectrum(mz=mz, intensities=intensities,
                           metadata={"parent_mass": 20})

    spectrum = reduce_to_number_of_peaks(spectrum_in, n_required=3, n_max=4, ratio_desired=0.1)

    assert len(spectrum.peaks) == 3, "Expected that only 3 peaks remain."
    assert spectrum.peaks.mz.tolist() == [20., 30., 40.], "Expected different peaks to remain."


def test_reduce_to_number_of_peaks_required_2_desired_6_max_4():
    """Here: ratio_desired * parent_mass is 6, more than n_required and more than n_max."""
    mz = numpy.array([10, 20, 30, 40, 50, 60], dtype="float")
    intensities = numpy.array([1, 1, 10, 100, 50, 20], dtype="float")
    spectrum_in = Spectrum(mz=mz, intensities=intensities,
                           metadata={"parent_mass": 60})

    spectrum = reduce_to_number_of_peaks(spectrum_in, n_required=3, n_max=4, ratio_desired=0.1)

    assert len(spectrum.peaks) == 4, "Expected that only 4 peaks remain."
    assert spectrum.peaks.mz.tolist() == [30., 40., 50., 60.], "Expected different peaks to remain."


def test_reduce_to_number_of_peaks_desired_5_check_sorting():
    """Check if mz and intensities order is sorted correctly """
    mz = numpy.array([10, 20, 30, 40, 50, 60], dtype="float")
    intensities = numpy.array([5, 1, 4, 3, 100, 2], dtype="float")
    spectrum_in = Spectrum(mz=mz, intensities=intensities,
                           metadata={"parent_mass": 20})

    spectrum = reduce_to_number_of_peaks(spectrum_in, n_max=5)

    assert spectrum.peaks.intensities.tolist() == [5., 4., 3., 100., 2.], "Expected different intensities."
    assert spectrum.peaks.mz.tolist() == [10., 30., 40., 50., 60.], "Expected different peaks to remain."


def test_empty_spectrum():
    spectrum_in = None
    spectrum = reduce_to_number_of_peaks(spectrum_in)

    assert spectrum is None, "Expected different handling of None spectrum."
