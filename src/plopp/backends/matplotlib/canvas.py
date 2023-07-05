# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)

from typing import Literal, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import scipp as sc
from matplotlib.collections import QuadMesh
from mpl_toolkits.axes_grid1 import make_axes_locatable

from ...core.limits import find_limits, fix_empty_range
from ...core.utils import maybe_variable_to_number, scalar_to_string
from .utils import fig_to_bytes, is_sphinx_build, silent_mpl_figure


def _none_if_not_finite(x):
    return x if np.isfinite(x) else None


class Canvas:
    """
    Matplotlib-based canvas used to render 2D graphics.
    It provides a figure and some axes, as well as functions for controlling the zoom,
    panning, and the scale of the axes.

    Parameters
    ----------
    ax:
        If supplied, use these axes to create the figure. If none are supplied, the
        canvas will create its own axes.
    cax:
        If supplied, use these axes for the colorbar. If none are supplied, and a
        colorbar is required, the canvas will create its own axes.
    figsize:
        The width and height of the figure, in inches.
    title:
        The title to be placed above the figure.
    grid:
        Display the figure grid if ``True``.
    vmin:
        The minimum value for the vertical axis. If a number (without a unit) is
        supplied, it is assumed that the unit is the same as the current vertical axis
        unit.
    vmax:
        The maximum value for the vertical axis. If a number (without a unit) is
        supplied, it is assumed that the unit is the same as the current vertical axis
        unit.
    autoscale:
        The behavior of the axis limits. If ``auto``, the limits automatically
        adjusts every time the data changes. If ``grow``, the limits are allowed to
        grow with time but they do not shrink.
    aspect:
        The aspect ratio for the axes.
    cbar:
        Add axes to host a colorbar if ``True``.
    """

    def __init__(
        self,
        ax: plt.Axes = None,
        cax: plt.Axes = None,
        figsize: Optional[Tuple[float, float]] = None,
        title: str = None,
        grid: bool = False,
        vmin: Union[sc.Variable, int, float] = None,
        vmax: Union[sc.Variable, int, float] = None,
        autoscale: Literal['auto', 'grow'] = 'auto',
        aspect: Literal['auto', 'equal'] = 'auto',
        cbar: bool = False,
        **ignored,
    ):
        # Note on the `**ignored`` keyword arguments: the figure which owns the canvas
        # creates both the canvas and an artist object (Line or Image). The figure
        # accepts keyword arguments, and has to somehow forward them to the canvas and
        # the artist. Since the figure has no detailed knowledge of the underlying
        # backend that implements the canvas, it cannot have specific arguments (such
        # as `ax` for specifying Matplotlib axes).
        # Instead, we forward all the kwargs from the figure to both the canvas and the
        # artist, and filter out the artist kwargs with `**ignored`.

        self.fig = None
        self.ax = ax
        self.cax = cax
        self._user_vmin = vmin
        self._user_vmax = vmax
        self.units = {}
        self.dims = {}
        self._own_axes = False
        self._autoscale = autoscale

        if self.ax is None:
            self._own_axes = True
            with silent_mpl_figure():
                self.fig, self.ax = plt.subplots(
                    figsize=(6.0, 4.0) if figsize is None else figsize
                )
            if self.is_widget():
                self.fig.canvas.toolbar_visible = False
                self.fig.canvas.header_visible = False
        else:
            self.fig = self.ax.get_figure()

        if cbar and (self.cax is None):
            divider = make_axes_locatable(self.ax)
            self.cax = divider.append_axes("right", "4%", pad="5%")

        self.ax.set_aspect(aspect)
        self.ax.set_title(title)
        self.ax.grid(grid)
        self._coord_formatters = []

        self._xmin = np.inf
        self._xmax = np.NINF
        self._ymin = np.inf
        self._ymax = np.NINF

    def is_widget(self):
        return hasattr(self.fig.canvas, "on_widget_constructed")

    def to_image(self):
        """
        Convert the underlying Matplotlib figure to an image widget from ``ipywidgets``.
        """
        from ipywidgets import Image

        return Image(value=fig_to_bytes(self.fig), format='png')

    def to_widget(self):
        if self.is_widget() and not is_sphinx_build():
            return self.fig.canvas
        else:
            return self.to_image()

    def autoscale(self):
        """
        Matplotlib's autoscale only takes lines into account. We require a special
        handling for meshes, which is part of the axes collections.

        Parameters
        ----------
        draw:
            Make a draw call to the figure if ``True``.
        """
        if self.ax.lines:
            self.ax.relim()
            self.ax.autoscale()
            xmin, xmax = self.ax.get_xlim()
            ymin, ymax = self.ax.get_ylim()
        else:
            xmin = np.inf
            xmax = np.NINF
            ymin = np.inf
            ymax = np.NINF
        for c in self.ax.collections:
            if isinstance(c, QuadMesh):
                coords = c.get_coordinates()
                left, right = fix_empty_range(
                    find_limits(
                        sc.array(dims=['x', 'y'], values=coords[..., 0]),
                        scale=self.xscale,
                    )
                )
                bottom, top = fix_empty_range(
                    find_limits(
                        sc.array(dims=['x', 'y'], values=coords[..., 1]),
                        scale=self.yscale,
                    )
                )
                xmin = min(xmin, left.value)
                xmax = max(xmax, right.value)
                ymin = min(ymin, bottom.value)
                ymax = max(ymax, top.value)
        if self._autoscale == 'grow':
            self._xmin = min(self._xmin, xmin)
            self._xmax = max(self._xmax, xmax)
            self._ymin = min(self._ymin, ymin)
            self._ymax = max(self._ymax, ymax)
        else:
            self._xmin = xmin
            self._xmax = xmax
            self._ymin = ymin
            self._ymax = ymax
        if self._user_vmin is not None:
            self._ymin = maybe_variable_to_number(
                self._user_vmin, unit=self.units.get('y')
            )
        if self._user_vmax is not None:
            self._ymax = maybe_variable_to_number(
                self._user_vmax, unit=self.units.get('y')
            )

        self.ax.set_xlim(
            _none_if_not_finite(self._xmin), _none_if_not_finite(self._xmax)
        )
        self.ax.set_ylim(
            _none_if_not_finite(self._ymin), _none_if_not_finite(self._ymax)
        )
        self.draw()

    def draw(self):
        """
        Make a draw call to the underlying figure.
        """
        self.fig.canvas.draw_idle()

    def save(self, filename: str, **kwargs):
        """
        Save the figure to file.
        The default directory for writing the file is the same as the
        directory where the script or notebook is running.

        Parameters
        ----------
        filename:
            Name of the output file. Possible file extensions are ``.jpg``, ``.png``,
            ``.svg``, and ``.pdf``.
        """
        self.fig.savefig(filename, **{**{'bbox_inches': 'tight'}, **kwargs})

    def show(self):
        """
        Make a call to Matplotlib's underlying ``show`` function.
        """
        self.fig.show()

    def crop(self, **limits):
        """
        Set the axes limits according to the crop parameters.

        Parameters
        ----------
        **limits:
            Min and max limits for each dimension to be cropped.
        """
        for xy, lims in limits.items():
            getattr(self.ax, f'set_{xy}lim')(
                *[
                    maybe_variable_to_number(lims[m], unit=self.units[xy])
                    for m in ('min', 'max')
                    if m in lims
                ]
            )

    def set_axes(self, dims, units):
        """
        Set the axes dimensions and units.

        Parameters
        ----------
        dims:
            The dimensions of the data.
        units:
            The units of the data.
        """
        self.units = units
        self.dims = dims
        self._cursor_x_placeholder = sc.scalar(0.0, unit=self.units['x'])
        self._cursor_y_placeholder = sc.scalar(0.0, unit=self.units['y'])
        self._cursor_x_prefix = ''
        self._cursor_y_prefix = ''
        if 'y' in self.dims:
            self._cursor_x_prefix = self.dims['x'] + '='
            self._cursor_y_prefix = self.dims['y'] + '='
        self.ax.format_coord = self.format_coord

    def register_format_coord(self, formatter):
        """
        Register a custom axis formatter for the x-axis.
        """
        self._coord_formatters.append(formatter)

    def format_coord(self, x: float, y: float) -> str:
        """
        Format the coordinates of the mouse pointer to show the value of the
        data at that point.

        Parameters
        ----------
        x:
            The x coordinate of the mouse pointer.
        y:
            The y coordinate of the mouse pointer.
        """
        self._cursor_x_placeholder.value = x
        self._cursor_y_placeholder.value = y
        out = (
            f"({self._cursor_x_prefix}{scalar_to_string(self._cursor_x_placeholder)}, "
            f"{self._cursor_y_prefix}{scalar_to_string(self._cursor_y_placeholder)})"
        )
        extra = [formatter(x, y) for formatter in self._coord_formatters]
        extra = [e for e in extra if e is not None]
        if extra:
            out += ": {" + ", ".join(extra) + "}"
        return out

    @property
    def empty(self) -> bool:
        """
        Check if the canvas is empty.
        """
        return not self.dims

    @property
    def title(self) -> str:
        """
        Get or set the title of the plot.
        """
        return self.ax.get_title()

    @title.setter
    def title(self, text: str):
        self.ax.set_title(text)

    @property
    def xlabel(self) -> str:
        """
        Get or set the label of the x-axis.
        """
        return self.ax.get_xlabel()

    @xlabel.setter
    def xlabel(self, lab: str):
        self.ax.set_xlabel(lab)

    @property
    def ylabel(self) -> str:
        """
        Get or set the label of the y-axis.
        """
        return self.ax.get_ylabel()

    @ylabel.setter
    def ylabel(self, lab: str):
        self.ax.set_ylabel(lab)

    @property
    def cblabel(self) -> str:
        """
        Get or set the label of the colorbar.
        """
        return self.cax.get_ylabel()

    @cblabel.setter
    def cblabel(self, lab: str):
        self.cax.set_ylabel(lab)

    @property
    def xscale(self) -> str:
        """
        Get or set the scale of the x-axis ('linear' or 'log').
        """
        return self.ax.get_xscale()

    @xscale.setter
    def xscale(self, scale: Literal['linear', 'log']):
        self.ax.set_xscale(scale)

    @property
    def yscale(self) -> str:
        """
        Get or set the scale of the y-axis ('linear' or 'log').
        """
        return self.ax.get_yscale()

    @yscale.setter
    def yscale(self, scale: Literal['linear', 'log']):
        self.ax.set_yscale(scale)

    @property
    def xmin(self) -> float:
        """
        Get or set the lower (left) bound of the x-axis.
        """
        return self.ax.get_xlim()[0]

    @xmin.setter
    def xmin(self, value: float):
        self.ax.set_xlim(value, self.xmax)

    @property
    def xmax(self) -> float:
        """
        Get or set the upper (right) bound of the x-axis.
        """
        return self.ax.get_xlim()[1]

    @xmax.setter
    def xmax(self, value: float):
        self.ax.set_xlim(self.xmin, value)

    @property
    def xrange(self) -> Tuple[float, float]:
        """
        Get or set the range/limits of the x-axis.
        """
        return self.ax.get_xlim()

    @xrange.setter
    def xrange(self, value: Tuple[float, float]):
        self.ax.set_xlim(value)

    @property
    def ymin(self) -> float:
        """
        Get or set the lower (bottom) bound of the y-axis.
        """
        return self.ax.get_ylim()[0]

    @ymin.setter
    def ymin(self, value: float):
        self.ax.set_ylim(value, self.ymax)

    @property
    def ymax(self) -> float:
        """
        Get or set the upper (top) bound of the y-axis.
        """
        return self.ax.get_ylim()[1]

    @ymax.setter
    def ymax(self, value: float):
        self.ax.set_ylim(self.ymin, value)

    @property
    def yrange(self) -> Tuple[float, float]:
        """
        Get or set the range/limits of the y-axis.
        """
        return self.ax.get_ylim()

    @yrange.setter
    def yrange(self, value: Tuple[float, float]):
        self.ax.set_ylim(value)

    @property
    def grid(self) -> str:
        """
        Get or set the visibility of the grid.
        """
        return self.ax.axes.get_xgridlines()[0].get_visible()

    @grid.setter
    def grid(self, visible: bool):
        self.ax.grid(visible)

    def reset_mode(self):
        """
        Reset the Matplotlib toolbar mode to nothing, to disable all Zoom/Pan tools.
        """
        if self.fig.canvas.toolbar.mode == 'zoom rect':
            self.zoom()
        elif self.fig.canvas.toolbar.mode == 'pan/zoom':
            self.pan()

    def zoom(self):
        """
        Activate the underlying Matplotlib zoom tool.
        """
        self.fig.canvas.toolbar.zoom()

    def pan(self):
        """
        Activate the underlying Matplotlib pan tool.
        """
        self.fig.canvas.toolbar.pan()

    def panzoom(self, value: Literal['pan', 'zoom', None]):
        """
        Activate or deactivate the pan or zoom tool, depending on the input value.
        """
        if value == 'zoom':
            self.zoom()
        elif value == 'pan':
            self.pan()
        elif value is None:
            self.reset_mode()

    def download_figure(self):
        """
        Save the figure to a PNG file via a pop-up dialog.
        """
        self.fig.canvas.toolbar.save_figure()

    def logx(self):
        """
        Toggle the scale between ``linear`` and ``log`` along the horizontal axis.
        """
        self.xscale = 'log' if self.xscale == 'linear' else 'linear'
        self._xmin = np.inf
        self._xmax = np.NINF
        self.autoscale()

    def logy(self):
        """
        Toggle the scale between ``linear`` and ``log`` along the vertical axis.
        """
        self.yscale = 'log' if self.yscale == 'linear' else 'linear'
        self._ymin = np.inf
        self._ymax = np.NINF
        self.autoscale()

    def finalize(self):
        """
        Finalize is called at the end of figure creation. Add any polishing operations
        here: trim the margins around the figure.
        """
        if self._own_axes:
            self.fig.tight_layout()
