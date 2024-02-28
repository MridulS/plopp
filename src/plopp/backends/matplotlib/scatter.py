# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)

import uuid
from typing import Optional

import numpy as np
import scipp as sc
from matplotlib.lines import Line2D

from ...core.utils import merge_masks
from .canvas import Canvas


def _parse_dicts_in_kwargs(kwargs, name):
    out = {}
    for key, value in kwargs.items():
        if isinstance(value, dict):
            if name in value:
                out[key] = value[name]
        else:
            out[key] = value
    return out


class Scatter:
    """ """

    def __init__(
        self,
        canvas: Canvas,
        data: sc.DataArray,
        x: str = 'x',
        y: str = 'y',
        size: Optional[str] = None,
        number: int = 0,
        mask_color: str = 'black',
        cbar: bool = False,
        **kwargs,
    ):
        self._canvas = canvas
        self._ax = self._canvas.ax
        self._data = data
        self._x = x
        self._y = y
        self._size = size
        # Because all keyword arguments from the figure are forwarded to both the canvas
        # and the line, we need to remove the arguments that belong to the canvas.
        kwargs.pop('ax', None)

        scatter_kwargs = _parse_dicts_in_kwargs(kwargs, name=data.name)

        self._scatter = None
        self._mask = None
        # self._error = None
        self._dim = None
        self._unit = None
        self.label = data.name if not cbar else None
        self._dim = self._data.dim
        self._unit = self._data.unit
        self._id = uuid.uuid4().hex

        markers = list(Line2D.markers.keys())
        default_plot_style = {
            'marker': markers[(number + 2) % len(markers)],
        }
        if not cbar:
            default_plot_style['color'] = f'C{number}'
        self._scatter = self._ax.scatter(
            self._data.coords[self._x].values,
            self._data.coords[self._y].values,
            s=(
                self._data.coords[self._size].values if self._size is not None else None
            ),
            label=self.label,
            **{**default_plot_style, **scatter_kwargs},
        )

        if self.label and self._canvas._legend:
            leg_args = {}
            if isinstance(self._canvas._legend, (list, tuple)):
                leg_args = {'loc': self._canvas._legend}
            elif not isinstance(self._canvas._legend, bool):
                raise TypeError(
                    "Legend must be a bool, tuple, or a list, "
                    f"not {type(self._canvas._legend)}"
                )
            self._ax.legend(**leg_args)

    def update(self, new_values: sc.DataArray):
        """
        Update the x and y positions of the data points from new data.

        Parameters
        ----------
        new_values:
            New data to update the line values, masks, errorbars from.
        """
        self._data = new_values
        self._scatter.set_offsets(
            sc.concat(
                [self._data.coords[self._x], self._data.coords[self._y]],
                dim=f'{self._dim}_new',
            )
            .transpose()
            .values
        )
        if self._size is not None:
            self._scatter.set_sizes(self._data.coords[self._size].values)

    def remove(self):
        """
        Remove the line, masks and errorbar artists from the canvas.
        """
        self._scatter.remove()
        # self._mask.remove()
        # if self._error is not None:
        #     self._error.remove()

    # @property
    # def color(self):
    #     """
    #     The line color.
    #     """
    #     return self._line.get_color()

    # @color.setter
    # def color(self, val):
    #     self._line.set_color(val)
    #     if self._error is not None:
    #         for artist in self._error.get_children():
    #             artist.set_color(val)
    #     self._canvas.draw()
    def set_colors(self, rgba: np.ndarray):
        if self._scatter.get_array() is not None:
            self._scatter.set_array(None)
        self._scatter.set_facecolors(rgba)

    @property
    def data(self):
        """ """
        return self._data
