# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)

import uuid
from typing import Literal

import numpy as np
import scipp as sc
from matplotlib.lines import Line2D

from ...core.utils import merge_masks
from ...graphics.bbox import BoundingBox, axis_bounds
from ...graphics.colormapper import ColorMapper
from ..common import check_ndim
from .canvas import Canvas
from .utils import parse_dicts_in_kwargs


class Scatter:
    """
    Artist to represent a two-dimensional scatter plot.

    Parameters
    ----------
    uid:
        The unique identifier of the artist.
    canvas:
        The canvas that will display the scatter plot.
    data:
        The initial data to create the line from.
    x:
        The name of the coordinate that is to be used for the X positions.
    y:
        The name of the coordinate that is to be used for the Y positions.
    size:
        The size of the markers.
    color:
        The color of the markers (this is ignored if a colorbar is used).
    artist_number:
        Number of the artist (can be used to set the color of the artist).
    colormapper:
        The colormapper to use for the scatter plot.
    mask_color:
        The color of the masked points.
    cbar:
        Whether to use a colorbar.
    """

    def __init__(
        self,
        uid: str,
        canvas: Canvas,
        data: sc.DataArray,
        x: str = 'x',
        y: str = 'y',
        size: str | None = None,
        artist_number: int = 0,
        colormapper: ColorMapper | None = None,
        mask_color: str = 'black',
        cbar: bool = False,
        **kwargs,
    ):
        check_ndim(data, ndim=1, origin='Scatter')
        self.uid = uid
        self._canvas = canvas
        self._ax = self._canvas.ax
        self._data = data
        self._x = x
        self._y = y
        self._size = size
        self._colormapper = colormapper
        # Because all keyword arguments from the figure are forwarded to both the canvas
        # and the line, we need to remove the arguments that belong to the canvas.
        kwargs.pop('ax', None)

        scatter_kwargs = parse_dicts_in_kwargs(kwargs, name=data.name)

        self.label = data.name if not cbar else None
        self._unit = self._data.unit
        self._id = uuid.uuid4().hex

        markers = list(Line2D.markers.keys())
        default_plot_style = {
            'marker': markers[(artist_number + 2) % len(markers)],
        }
        if not cbar:
            default_plot_style['color'] = f'C{artist_number}'

        merged_kwargs = {**default_plot_style, **scatter_kwargs}
        if self._size is None:
            s = merged_kwargs.pop('s', None)
        else:
            s = self._data.coords[self._size].values

        self._scatter = self._ax.scatter(
            self._data.coords[self._x].values,
            self._data.coords[self._y].values,
            s=s,
            label=self.label,
            **merged_kwargs,
        )
        if self._colormapper is not None:
            self._colormapper.add_artist(self.uid, self)
            self._scatter.set_array(None)

        xmask = self._data.coords[self._x].values.copy()
        ymask = self._data.coords[self._y].values.copy()
        visible_mask = False
        if self._data.masks:
            not_one_mask = ~merge_masks(self._data.masks).values
            xmask[not_one_mask] = np.nan
            ymask[not_one_mask] = np.nan
            visible_mask = True
        self._mask = self._ax.scatter(
            xmask,
            ymask,
            s=s,
            marker=merged_kwargs['marker'],
            edgecolors=mask_color,
            facecolor="None",
            linewidth=3.0,
            zorder=self._scatter.get_zorder() + 1,
            visible=visible_mask,
        )

    def notify_artist(self, message: str) -> None:
        """
        Receive notification from the colormapper that its state has changed.
        We thus need to update the colors of the points.

        Parameters
        ----------
        message:
            The message from the colormapper.
        """
        self._update_colors()

    def _update_colors(self):
        """
        Update the colors of the scatter points.
        """
        self._scatter.set_facecolors(self._colormapper.rgba(self.data))

    def update(self, new_values: sc.DataArray):
        """
        Update the x and y positions of the data points from new data.

        Parameters
        ----------
        new_values:
            New data to update the line values, masks, errorbars from.
        """
        check_ndim(new_values, ndim=1, origin='Scatter')
        self._data = new_values
        self._scatter.set_offsets(
            np.stack(
                [self._data.coords[self._x].values, self._data.coords[self._y].values],
                axis=1,
            )
        )
        if self._size is not None:
            self._scatter.set_sizes(self._data.coords[self._size].values)
        if self._colormapper is not None:
            self._update_colors()

    def remove(self):
        """
        Remove the scatter and mask artists from the canvas.
        """
        self._scatter.remove()
        self._mask.remove()
        if self._colormapper is not None:
            self._colormapper.remove_artist(self.uid)

    @property
    def data(self):
        """ """
        return self._data

    def bbox(self, xscale: Literal['linear', 'log'], yscale: Literal['linear', 'log']):
        """
        The bounding box of the scatter points.
        """
        scatter_x = self._data.coords[self._x]
        scatter_y = self._data.coords[self._y]
        return BoundingBox(
            **{**axis_bounds(('xmin', 'xmax'), scatter_x, xscale, pad=True)},
            **{**axis_bounds(('ymin', 'ymax'), scatter_y, yscale, pad=True)},
        )
