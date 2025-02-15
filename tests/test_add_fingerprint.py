import numpy
import pytest
from testfixtures import LogCapture
from matchms import Spectrum
from matchms.filtering import add_fingerprint
from matchms.logging_functions import reset_matchms_logger
from matchms.logging_functions import set_matchms_logger_level


def test_add_fingerprint_from_smiles():
    """Test if fingerprint it generated correctly."""
    pytest.importorskip("rdkit")
    spectrum_in = Spectrum(mz=numpy.array([], dtype="float"),
                           intensities=numpy.array([], dtype="float"),
                           metadata={"smiles": "[C+]#C[O-]"})

    spectrum = add_fingerprint(spectrum_in, nbits=16)
    expected_fingerprint = numpy.array([0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0])
    assert numpy.all(spectrum.get("fingerprint") == expected_fingerprint), "Expected different fingerprint."


def test_add_fingerprint_from_inchi():
    """Test if fingerprint it generated correctly."""
    pytest.importorskip("rdkit")
    spectrum_in = Spectrum(mz=numpy.array([], dtype="float"),
                           intensities=numpy.array([], dtype="float"),
                           metadata={"inchi": "InChI=1S/C2O/c1-2-3"})

    spectrum = add_fingerprint(spectrum_in, nbits=16)
    expected_fingerprint = numpy.array([0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0])
    assert numpy.all(spectrum.get("fingerprint") == expected_fingerprint), "Expected different fingerprint."


def test_add_fingerprint_no_smiles_no_inchi():
    """Test if fingerprint it generated correctly."""
    set_matchms_logger_level("INFO")
    spectrum_in = Spectrum(mz=numpy.array([], dtype="float"),
                           intensities=numpy.array([], dtype="float"),
                           metadata={"compound_name": "test name"})

    with LogCapture() as log:
        spectrum = add_fingerprint(spectrum_in)
    assert spectrum.get("fingerprint", None) is None, "Expected None."
    log.check(
        ("matchms", "INFO", "No fingerprint was added (name: test name).")
    )
    reset_matchms_logger()


def test_add_fingerprint_empty_spectrum():
    """Test if empty spectrum is handled correctly."""

    spectrum = add_fingerprint(None)
    assert spectrum is None, "Expected None."
