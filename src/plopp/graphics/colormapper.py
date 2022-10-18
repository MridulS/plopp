# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2022 Scipp contributors (https://github.com/scipp)

from ..core.limits import find_limits, fix_empty_range
from ..core.utils import merge_masks
from ..widgets import ToggleTool
from .io import fig_to_bytes

import matplotlib as mpl
from matplotlib.colors import Normalize, LogNorm, LinearSegmentedColormap
import matplotlib.pyplot as plt
from matplotlib.colorbar import ColorbarBase
import scipp as sc
from copy import copy
import numpy as np


def _get_cmap(name, nan_color=None):

    try:
        if hasattr(mpl, 'colormaps'):
            cmap = copy(mpl.colormaps[name])
        else:
            cmap = mpl.cm.get_cmap(name)
    except (KeyError, ValueError):
        cmap = LinearSegmentedColormap.from_list("tmp", [name, name])
    # TODO: we need to set under and over values for the cmap with
    # `cmap.set_under` and `cmap.set_over`. Ideally these should come from a config?
    if nan_color is not None:
        cmap.set_bad(color=nan_color)
    return cmap


class ColorMapper:

    def __init__(
            self,
            # notify_on_change=None,
            cax=None,
            cmap: str = 'viridis',
            mask_cmap: str = 'gray',
            norm: str = "linear",
            vmin=None,
            vmax=None,
            nan_color=None,
            figsize=None):

        self.cax = cax
        self.cmap = _get_cmap(cmap, nan_color=nan_color)
        self.mask_cmap = _get_cmap(mask_cmap, nan_color=nan_color)
        self.user_vmin = vmin
        self.user_vmax = vmax
        # self._vmin = {'linear': np.inf, 'log': np.inf}
        # self._vmax = {'linear': np.NINF, 'log': np.NINF}
        self.vmin = np.inf
        self.vmax = np.NINF
        self.norm = norm
        # self.normalizer = {'linear': Normalize(), 'log': LogNorm()}

        # Note that we need to set vmin/vmax for the LogNorm, if not an error is
        # raised when making the colorbar before any call to update is made.
        self.normalizer = Normalize() if self.norm == "linear" else LogNorm(vmin=1,
                                                                            vmax=2)
        # self._notify_on_change = [notify_on_change]
        self.colorbar = None
        self.unit = None
        self.name = None
        # self._figheight = figheight
        self.changed = False
        self.children = {}
        self.widget = None

        # print(self.normalizer, self.normalizer.vmin, self.normalizer.vmax)

        if self.cax is None:
            dpi = 100
            height_inches = figsize[1] / dpi
            cbar_fig = plt.figure(figsize=(height_inches * 0.2, height_inches))
            self.cax = cbar_fig.add_axes([0.05, 0.02, 0.25, 1.0])

        self.colorbar = ColorbarBase(self.cax, cmap=self.cmap, norm=self.normalizer)
        self.cax.yaxis.set_label_coords(-1.1, 0.5)
        # cbar_ax.set_ylabel(f'{self.name} [{self.unit}]')

    def __setitem__(self, key, val):
        self.children[key] = val

    def __getitem__(self, key):
        return self.children[key]

    def to_widget(self):
        import ipywidgets as ipw
        self.widget = {
            'image':
            ipw.HTML(),
            'button':
            ToggleTool(self.toggle_norm,
                       value=self.norm == 'log',
                       description='log',
                       tooltip='Toggle data norm').widget
        }
        self._update_colorbar_image()
        return ipw.VBox(list(self.widget.values()))

    def _update_colorbar_image(self):
        # Choose a dpi that makes the sizes in inches (mpl colorbar) and pixels
        # (pythreejs renderer) match.
        dpi = 100
        # Additional shrinking factor to make space for the 'log' toggle button
        height_inches = 0.88 * self._figheight / dpi
        cbar_fig = plt.figure(figsize=(height_inches * 0.2, height_inches))
        cbar_ax = cbar_fig.add_axes([0.05, 0.02, 0.25, 1.0])
        _ = ColorbarBase(cbar_ax, cmap=self.cmap, norm=self.norm)
        cbar_ax.set_ylabel(f'{self.name} [{self.unit}]')
        self.widget['image'].value = fig_to_bytes(cbar_fig, form='svg').decode()
        plt.close(cbar_fig)

    def rgba(self, data: sc.DataArray):
        """
        Return rgba values given a data array.
        """
        colors = self.cmap(self.normalizer(data.values))
        if data.masks:
            one_mask = merge_masks(data.masks).values
            colors[one_mask] = self.mask_cmap(self.normalizer(data.values[one_mask]))
        return colors

    def autoscale(self, data):
        """
        Re-compute the min and max range of values, given new values.
        """
        # if data is not None:
        #     self._data = data
        vmin, vmax = fix_empty_range(find_limits(data, scale=self.norm))
        print(vmin, vmax)
        # if self.norm == 'log':
        #     assert False
        if self.user_vmin is not None:
            assert self.user_vmin.unit == data.unit
            self.vmin = self.user_vmin.value
        elif vmin.value < self.vmin:
            self.vmin = vmin.value
        if self.user_vmax is not None:
            assert self.user_vmax.unit == data.unit
            self.vmax = self.user_vmax.value
        elif vmax.value > self.vmax:
            self.vmax = vmax.value

    def _set_children_colors(self):
        for child in self.children.values():
            child.set_colors(self.rgba(child.data))

    def update(self, data):

        print("in update", self.children)

        old_bounds = np.array([self.vmin, self.vmax])
        self.autoscale(data=data)

        self.normalizer.vmin = self.vmin
        self.normalizer.vmax = self.vmax

        if self.unit is None:
            self.unit = data.unit
            self.name = data.name
            self.cax.set_ylabel(f'{self.name} [{self.unit}]')

        if not np.allclose(old_bounds, np.array([self.vmin, self.vmax])):
            self._set_children_colors()
            # for child in self.children.values():
            #     child.set_colors(self.rgba(child.data))

        # if (self.colorbar is not None) and not np.allclose(
        #         old_bounds, np.array([self.vmin, self.vmax])):
        #     self._update_colorbar_image()

    # def rescale(self, data):
    #     old_bounds = np.array([self.vmin, self.vmax])
    #     self.autoscale(data=data, scale=self._norm)
    #     if (self.colorbar is not None) and not np.allclose(
    #             old_bounds, np.array([self.vmin, self.vmax])):
    #         self._update_colorbar_image()

    # def set_norm(self, data):
    #     """
    #     Set the norm of the color mapper and update the min/max values.
    #     """
    #     self.unit = data.unit
    #     self.name = data.name
    #     self.autoscale(data=data.data, scale='linear')
    #     self.autoscale(data=data.data, scale='log')
    #     # self.notify()

    def toggle_norm(self):
        """
        Toggle the norm flag, between `linear` and `log`.
        """
        print('colormapper togglenorm', self.children)
        self.norm = "log" if self.norm == "linear" else "linear"
        self.normalizer = Normalize() if self.norm == "linear" else LogNorm()
        self.vmin = np.inf
        self.vmax = np.NINF
        # cbar_fig.canvas.draw_idle()
        print(self.children)
        for child in self.children.values():
            self.autoscale(data=child._data)
        self._set_children_colors()

        # print(self._vmin, self._vmax)
        # print(self.norm.vmin, self.norm.vmax)
        # self.notify()
        if self.colorbar is not None:
            self.colorbar.mappable.norm = self.normalizer
            # self._update_colorbar_image()

    # def add_notify(self, callback):
    #     self._notify_on_change.append(callback)

    # def notify(self):
    #     for callback in self._notify_on_change:
    #         callback()

    # @property
    # def vmin(self):
    #     return self._vmin[self._norm]

    # @property
    # def vmax(self):
    #     return self._vmax[self._norm]

    # @property
    # def norm(self):
    #     return self.normalizer[self._norm]
