# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2022 Scipp contributors (https://github.com/scipp)

from scipp import DataArray
from ..tools import value_to_string
from ..model import node

import ipywidgets as ipw
from typing import Callable


def _coord_to_string(coord):
    out = value_to_string(coord.values)
    if coord.unit is not None:
        out += f" [{coord.unit}]"
    return out


class SliceWidget(ipw.VBox):
    """
    Widgets containing a slider for each of the input's dimensions, as well as
    buttons to modify the currently displayed axes.
    """

    def __init__(self, data_array, dims: list):
        self._container = []
        self._slider_dims = dims
        self.controls = {}
        self.view = None
        children = []

        for dim in dims:
            coord = data_array.meta[dim]
            slider = ipw.IntSlider(step=1,
                                   description=dim,
                                   min=0,
                                   max=data_array.sizes[dim],
                                   continuous_update=True,
                                   readout=False,
                                   layout={"width": "200px"})
            continuous_update = ipw.Checkbox(value=True,
                                             description="Continuous update",
                                             indent=False,
                                             layout={"width": "20px"})
            label = ipw.Label(value=_coord_to_string(coord[dim, 0]))
            ipw.jslink((continuous_update, 'value'), (slider, 'continuous_update'))

            self.controls[dim] = {
                'continuous': continuous_update,
                'slider': slider,
                'label': label,
                'coord': coord
            }
            slider.observe(self._update_label, names='value')
            children.append(ipw.HBox([continuous_update, slider, label]))

        super().__init__(children)

    def _update_label(self, change):
        dim = change['owner'].description
        coord = self.controls[dim]['coord'][dim, change['new']]
        self.controls[dim]['label'].value = _coord_to_string(coord)

    def _plopp_observe(self, callback: Callable, **kwargs):
        """
        TODO: Cannot name this method 'observe' when inheriting from HBox, so we name
        it '_plopp_observe' instead (see https://bit.ly/3SggPVS).
        """
        for dim in self.controls:
            self.controls[dim]['slider'].observe(callback, **kwargs)

    @property
    def value(self) -> dict:
        return {dim: self.controls[dim]['slider'].value for dim in self._slider_dims}


@node
def slice_dims(data_array: DataArray, slices: dict) -> DataArray:
    """
    Slice the data along dimension sliders that are not disabled for all
    entries in the dict of data arrays, and return a dict of 1d value
    arrays for data values, variances, and masks.
    """
    out = data_array
    for dim, sl in slices.items():
        out = out[dim, sl]
    return out
