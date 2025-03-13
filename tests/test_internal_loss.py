from matchms.importing import load_from_mgf
from matchms import Spectrum, Fragments

from typing import Optional
import matplotlib.pyplot as plt
import numpy as np



file_mgf = './tests/testdata/testdata_small.mgf'
spectra_from_path = list(load_from_mgf(file_mgf))



spectra_from_path[0].compute_losses()


res = spectra_from_path[0].compute_internal_losses()

spectra_from_path[0].compute_internal_losses_test()


print(res)

spectra_from_path[0].losses.mz
spectra_from_path[0].losses.intensities

spectra_from_path[0].internal_losses.mz
spectra_from_path[0].internal_losses.intensities

spectra_from_path[0].peaks.mz.


spectra_from_path[0].internal_losses.mz