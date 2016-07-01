from __future__ import division

import numpy as np

from stingray import Lightcurve
import stingray.utils as utils

__all__ = ['Covariancespectrum']


class Covariancespectrum(object):

    def __init__(self, event_list, dt, band_interest=None,
                 ref_band_interest=None):
        """
        Parameters
        ----------
        event_list : numpy 2D array
            A numpy 2D array with first column as time of arrival and second
            column as photon energies associated.

        dt : float
            The time resolution of the Lightcurve formed from the energy bin.

        band_interest : iterable of tuples, default All
            An iterable of tuples with minimum and maximum values of the range
            in the band of interest. e.g list of tuples, tuple of tuples.

        ref_band_interest : tuple of reference band range, default All
            A tuple with minimum and maximum values of the range in the band
            of interest in reference channel.
        """
        self.min_energy, self.max_energy = np.min(event_list.T[1]), np.max(event_list.T[1])
        self.min_time, self.max_time = np.min(event_list.T[0]), np.max(event_list.T[0])

        if ref_band_interest is None:
            ref_band_interest = (self.min_energy, self.max_energy)

        assert type(ref_band_interest) in (list, tuple), "Ref Band interest " \
                                                         "should be either " \
                                                         "tuple or list."

        assert len(ref_band_interest) == 2, "Band interest should be a tuple " \
                                            "with min and max energy value " \
                                            "for the reference band."
        self.ref_band_interest = ref_band_interest

        if band_interest is not None:
            for element in list(band_interest):
                assert type(element) in (list, tuple), "band_interest should " \
                                                       "be iterable of either " \
                                                       "tuple or list."
                assert len(element) == 2, "Band interest should be a tuple " \
                                          "with min and max energy values."

        self.band_interest = band_interest
        self.dt = dt

        self.event_list = event_list

        # Sorted by energy values as second row
        event_list_T = event_list[self.event_list[:, 1].argsort()].T

        self._construct_energy_events(event_list_T)

        self._update_energy_events()

        self._construct_energy_covar()


    def _construct_energy_events(self, event_list_T):

        least_count = np.diff(np.unique(event_list_T[1])).min()

        # An array of unique energy values
        unique_energy = np.unique(event_list_T[1])

        # A dictionary with energy bin as key and events as value of the key
        self.energy_events = {}

        for i in range(len(unique_energy) - 1):
            self.energy_events[unique_energy[i] + least_count*0.5] = []

        # Add time of arrivals to corresponding energy bins
        for energy in self.energy_events.keys():
            if energy == self.max_energy - least_count*0.5:  # The last energy bin
                toa = event_list_T[0][np.logical_and(
                    event_list_T[1] >= energy - least_count*0.5,
                    event_list_T[1] <= energy + least_count*0.5)]
                self.energy_events[energy] = sorted(toa)
            else:
                toa = event_list_T[0][np.logical_and(
                    event_list_T[1] >= energy - least_count*0.5,
                    event_list_T[1] < energy + least_count*0.5)]
                self.energy_events[energy] = sorted(toa)


    def _update_energy_events(self):

        if self.band_interest is not None:
            energy_events_ = {}
            for band in list(self.band_interest):
                mid_bin = (band[0] + band[1]) / 2
                energy_events_[mid_bin] = []

                # Modify self.energy_events to form a band with one key
                for key in list(self.energy_events.keys()):
                    if key >= band[0] and key <= band[1]:
                        energy_events_[mid_bin] += self.energy_events[key]
                        del self.energy_events[key]

            self.energy_events.update(energy_events_)


    def _init_energy_covar(self):
        # The dictionary with covariance spectrum for each energy bin
        self.energy_covar = {}

        # Initialize it with empty mapping
        if self.band_interest is None:
            for key in self.energy_events.keys():
                self.energy_covar[key] = []
        else:
            for band in list(self.band_interest):
                mid_bin = (band[0] + band[1]) / 2
                self.energy_covar[mid_bin] = []


    def _construct_energy_covar(self):

        self._init_energy_covar()

        for energy in self.energy_covar.keys():
            lc = Lightcurve.make_lightcurve(self.energy_events[energy], self.dt, tstart=self.min_time, tseg=self.max_time - self.min_time)

            # Calculating timestamps for lc_ref
            toa_ref = []
            for key, value in self.energy_events.items():
                if key >= self.ref_band_interest[0] and key <= self.ref_band_interest[1]:
                    if key != energy:
                        toa_ref.extend(value)

            toa_ref = np.array(sorted(toa_ref))

            lc_ref = Lightcurve.make_lightcurve(toa_ref, self.dt, tstart=self.min_time, tseg=self.max_time - self.min_time)

            assert len(lc.time) == len(lc_ref.time)

            covar = self._compute_covariance(lc, lc_ref)

            self.energy_covar[energy] = covar

        self.covar = np.vstack(self.energy_covar.items())

    def _compute_covariance(self, lc1, lc2):
        return np.cov(lc1.counts, lc2.counts)[0][1]
