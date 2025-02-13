import logging
from ..typing import SpectrumType


logger = logging.getLogger("matchms")


def make_charge_int(spectrum_in: SpectrumType) -> SpectrumType:
    """Convert charge field to integer (if possible)."""
    if spectrum_in is None:
        return None

    spectrum = spectrum_in.clone()

    # Avoid pyteomics ChargeList
    if isinstance(spectrum.get("charge", None), list):
        spectrum.set("charge", int(spectrum.get("charge")[0]))

    # convert string charges to int
    if isinstance(spectrum.get("charge", None), str):
        try:
            charge_int = int(spectrum.get('charge'))
            spectrum.set("charge", charge_int)
        except ValueError:
            logger.warning("Found charge (%s) cannot be converted to integer.", str(spectrum.get('charge')))

    return spectrum
