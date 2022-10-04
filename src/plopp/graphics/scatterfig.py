# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2022 Scipp contributors (https://github.com/scipp)

from .fig3d import Fig3d
from ..widgets import Cut3dTool

import scipp as sc
import ipywidgets as ipw


class ScatterFig(Fig3d):

    def __init__(self,
                 *nodes,
                 x,
                 y,
                 z,
                 figsize=(600, 400),
                 title=None,
                 cbar=None,
                 **kwargs):

        self._x = x
        self._y = y
        self._z = z
        self._kwargs = kwargs

        super().__init__(*nodes, figsize=figsize, title=title)

        limits = self.get_limits()
        self.cut_x = Cut3dTool(*nodes,
                               direction='x',
                               limits=limits,
                               view=self,
                               description='X',
                               icon='cube')
        self.cut_y = Cut3dTool(*nodes,
                               direction='y',
                               limits=limits,
                               view=self,
                               description='Y',
                               icon='cube')
        self.cut_z = Cut3dTool(*nodes,
                               direction='z',
                               limits=limits,
                               view=self,
                               description='Z',
                               icon='cube')
        space = ipw.HTML('&nbsp;&nbsp;&nbsp;&nbsp;')
        self.bottom_bar.children = list(self.bottom_bar.children) + [
            self.cut_x, space, self.cut_y, space, self.cut_z
        ]
        self.scene.add([self.cut_x.outline, self.cut_y.outline, self.cut_z.outline])

        self._original_children = list(self._children.keys())
        self.cut_x.button.observe(self._toggle_opacity, names='value')
        self.cut_y.button.observe(self._toggle_opacity, names='value')
        self.cut_z.button.observe(self._toggle_opacity, names='value')

    def update(self, new_values: sc.DataArray, key: str, colormapper=None):
        """
        Update image array with new values.
        """
        from .point_cloud import PointCloud
        from .outline import Outline

        if key not in self._children:
            if colormapper is not None:
                colormapper = self._children[colormapper].color_mapper
            pts = PointCloud(
                data=new_values,
                x=self._x,
                y=self._y,
                z=self._z,
                colormapper=colormapper,
                # cbar=self.right_bar,
                # figsize=self._figsize,
                **self._kwargs)
            self._children[key] = pts
            self.scene.add(pts.points)
            if colormapper is None:
                limits = self.get_limits()
                if self.outline is not None:
                    self.scene.remove(self.outline)
                self.outline = Outline(limits=limits)
                self.scene.add(self.outline)
                self._update_camera(limits=limits)
                self.axes_3d.scale = [self.camera.far] * 3
                self.right_bar.children = list(
                    self.right_bar.children) + [pts.color_mapper.widget]
        else:
            self._children[key].update(new_values=new_values)

    def get_limits(self):
        """
        Get global limits for all the point clouds in the scene.
        """
        xmin = None
        xmax = None
        ymin = None
        ymax = None
        zmin = None
        zmax = None
        for child in self._children.values():
            xlims, ylims, zlims = child.get_limits()
            if xmin is None or xlims[0] < xmin:
                xmin = xlims[0]
            if xmax is None or xlims[1] > xmax:
                xmax = xlims[1]
            if ymin is None or ylims[0] < ymin:
                ymin = ylims[0]
            if ymax is None or ylims[1] > ymax:
                ymax = ylims[1]
            if zmin is None or zlims[0] < zmin:
                zmin = zlims[0]
            if zmax is None or zlims[1] > zmax:
                zmax = zlims[1]
        return (sc.concat([xmin, xmax],
                          dim=self._x), sc.concat([ymin, ymax], dim=self._y),
                sc.concat([zmin, zmax], dim=self._z))

    def _toggle_opacity(self, change):
        """
        If any cut is active, set the opacity of the original children (not the cuts) to
        a low value. If all cuts are inactive, set the opacity back to 1.
        """
        opacity = 0.05 if any([self.cut_x.value, self.cut_y.value, self.cut_z.value
                               ]) else 1.0
        for name in self._original_children:
            self._children[name].opacity = opacity

    def remove(self, key):
        """
        Remove a point cloud from the scene.
        """
        self.scene.remove(self._children[key].points)
        del self._children[key]
