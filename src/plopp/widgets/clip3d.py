# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)
from functools import reduce
from typing import Any, Callable, Dict, Literal, Tuple

import ipywidgets as ipw
import numpy as np
import scipp as sc

from ..core import Node
from ..graphics import BaseFig
from .debounce import debounce
from .style import BUTTON_LAYOUT

OPERATIONS = {'or': sc.logical_or, 'and': sc.logical_and, 'xor': sc.logical_xor}


def select(da: sc.DataArray, s: Tuple[str, sc.Variable]) -> sc.DataArray:
    return da[s]


class Clip3dTool(ipw.HBox):
    """
    A tool that provides a slider to extract a slab of points in a three-dimensional
    scatter plot, and add it to the scene as an opaque cut. The slider controls the
    position and range of the slice. When the slider is dragged, the red outline of the
    cut is moved at the same time, while the actual point cloud gets updated less
    frequently using a debounce mechanism.

    Parameters
    ----------
    limits:
        The spatial extent of the points in the 3d figure in the XYZ directions.
    direction:
        The direction normal to the slice.
    plain_update:
        A function to update the scene without debouncing.
    throttled_update:
        A function to update the scene with debouncing.
    color:
        Color of the cut's outline.
    linewidth:
        Width of the line delineating the outline.
    """

    def __init__(
        self,
        limits: Tuple[sc.Variable, sc.Variable, sc.Variable],
        direction: Literal['x', 'y', 'z'],
        plain_update: Callable,
        throttled_update: Callable,
        color: str = 'red',
        linewidth: float = 1.5,
    ):
        import pythreejs as p3

        self._limits = limits
        self._direction = direction
        axis = 'xyz'.index(self._direction)
        self.dim = self._limits[axis].dim
        self._unit = self._limits[axis].unit
        self.visible = True
        self._plain_update = plain_update
        self._throttled_update = throttled_update

        w_axis = 2 if self._direction == 'x' else 0
        h_axis = 2 if self._direction == 'y' else 1
        width = (self._limits[w_axis][1] - self._limits[w_axis][0]).value
        height = (self._limits[h_axis][1] - self._limits[h_axis][0]).value

        self.outlines = [
            p3.LineSegments(
                geometry=p3.EdgesGeometry(
                    p3.PlaneBufferGeometry(width=width, height=height)
                ),
                material=p3.LineBasicMaterial(color=color, linewidth=linewidth),
            ),
            p3.LineSegments(
                geometry=p3.EdgesGeometry(
                    p3.PlaneBufferGeometry(width=width, height=height)
                ),
                material=p3.LineBasicMaterial(color=color, linewidth=linewidth),
            ),
        ]
        if self._direction == 'x':
            for outline in self.outlines:
                outline.rotateY(0.5 * np.pi)
        if self._direction == 'y':
            for outline in self.outlines:
                outline.rotateX(0.5 * np.pi)

        center = [var.mean().value for var in self._limits]
        vmin = self._limits[axis][0].value
        vmax = self._limits[axis][1].value
        dx = vmax - vmin
        delta = 0.05 * dx
        self.slider = ipw.FloatRangeSlider(
            min=vmin,
            max=vmax,
            value=[center[axis] - delta, center[axis] + delta],
            step=dx * 0.01,
            description=direction.upper(),
            style={'description_width': 'initial'},
            layout={'width': '470px', 'padding': '0px'},
        )

        self.cut_visible = ipw.Button(
            icon='eye-slash',
            tooltip='Hide cut',
            layout={'width': '16px', 'padding': '0px'},
        )

        for outline, val in zip(self.outlines, self.slider.value):
            pos = list(center)
            pos[axis] = val
            outline.position = pos

        self.unit_label = ipw.Label(f'[{self._unit}]')
        self.cut_visible.on_click(self.toggle)
        self.slider.observe(self.move, names='value')

        super().__init__([self.slider, ipw.Label(f'[{self._unit}]'), self.cut_visible])

    def toggle(self, owner):
        """
        Toggle the visibility of the cut on and off.
        """
        self.visible = not self.visible
        for outline in self.outlines:
            outline.visible = self.visible
        self.slider.disabled = not self.visible
        owner.icon = 'eye-slash' if self.visible else 'eye'
        owner.tooltip = 'Hide cut' if self.visible else 'Show cut'
        self._plain_update()

    def toggle_border(self, value: bool):
        """
        Toggle the border visbility.
        """
        for outline in self.outlines:
            outline.visible = value

    def move(self, value: Dict[str, Any]):
        """
        Move the outline of the cut according to new position given by the slider.
        """
        # Early return if relative difference between new and old value is small
        old = np.array(value['old'])
        if np.abs((np.array(value['new']) - old) / old).max() < 1e-6:
            return
        for outline, val in zip(self.outlines, value['new']):
            pos = list(outline.position)
            axis = 'xyz'.index(self._direction)
            pos[axis] = val
            outline.position = pos
        self._throttled_update()

    @property
    def range(self):
        return sc.scalar(self.slider.value[0], unit=self._unit), sc.scalar(
            self.slider.value[1], unit=self._unit
        )


class ClippingPlanes(ipw.HBox):
    """
    A widget to make clipping planes for spatial cutting (see :class:`Clip3dTool`) to
    make spatial cuts in the X, Y, and Z directions on a three-dimensional scatter plot.

    Parameters
    ----------
    fig:
        The 3d figure that contains the point clouds to be cut.
    """

    def __init__(self, fig: BaseFig):
        self._view = fig._view
        self._limits = self._view.get_limits()
        self.cuts = []
        self._operation = 'or'

        self.tabs = ipw.Tab(layout={'width': '550px'})
        self._original_nodes = list(self._view.graph_nodes.values())
        self._nodes = {}

        self.add_cut_label = ipw.Label('Add cut:')
        layout = {'width': '45px', 'padding': '0px 0px 0px 0px'}
        self.add_x_cut = ipw.Button(
            description='X',
            icon='plus',
            tooltip='Add X cut',
            layout=layout,
        )
        self.add_y_cut = ipw.Button(
            description='Y',
            icon='plus',
            tooltip='Add Y cut',
            layout=layout,
        )
        self.add_z_cut = ipw.Button(
            description='Z',
            icon='plus',
            tooltip='Add Z cut',
            layout=layout,
        )
        self.add_x_cut.on_click(lambda _: self._add_cut('x'))
        self.add_y_cut.on_click(lambda _: self._add_cut('y'))
        self.add_z_cut.on_click(lambda _: self._add_cut('z'))

        self.opacity = ipw.BoundedFloatText(
            min=0,
            max=0.5,
            step=0.01,
            disabled=True,
            value=0.03,
            description='Opacity:',
            tooltip='Set the opacity of the background',
            style={'description_width': 'initial'},
            layout={'width': '142px', 'padding': '0px 0px 0px 0px'},
        )
        self.opacity.observe(self._set_opacity, names='value')

        self.cut_borders_visibility = ipw.ToggleButton(
            value=True,
            disabled=True,
            icon='border-style',
            tooltip='Toggle visbility of the borders of the cuts',
            **BUTTON_LAYOUT,
        )
        self.cut_borders_visibility.observe(
            self.toggle_border_visibility, names='value'
        )

        self.cut_operation = ipw.Dropdown(
            options=['OR', 'AND', 'XOR'],
            value='OR',
            disabled=True,
            tooltip='Operation to combine multiple cuts',
            layout={'width': '60px', 'padding': '0px 0px 0px 0px'},
        )
        self.cut_operation.observe(self.change_operation, names='value')

        self.delete_cut = ipw.Button(
            tooltip='Delete cut',
            icon='trash',
            disabled=True,
            **BUTTON_LAYOUT,
        )
        self.delete_cut.on_click(self._remove_cut)

        super().__init__(
            [
                self.tabs,
                ipw.VBox(
                    [
                        ipw.HBox([self.add_x_cut, self.add_y_cut, self.add_z_cut]),
                        self.opacity,
                        ipw.HBox(
                            [
                                self.cut_borders_visibility,
                                self.cut_operation,
                                self.delete_cut,
                            ]
                        ),
                    ]
                ),
            ]
        )

        self.layout.display = 'none'

    def _add_cut(self, direction: Literal['x', 'y', 'z']):
        """
        Add a cut in the specified direction.
        """
        cut = Clip3dTool(
            direction=direction,
            limits=self._limits,
            plain_update=self.update_state,
            throttled_update=self.throttled_update,
        )
        self._view.canvas.add(cut.outlines)
        self.cuts.append(cut)
        self.tabs.children = list(self.tabs.children) + [cut]
        self.tabs.selected_index = len(self.cuts) - 1
        self.update_controls()
        self.update_state()

    def _remove_cut(self, _):
        cut = self.cuts.pop(self.tabs.selected_index)
        self._view.canvas.remove(cut.outlines)
        self.tabs.children = self.cuts
        self.update_state()
        self.update_controls()

    def update_controls(self):
        """
        If there are no active cuts, disable the controls.
        If there is at least one cut, set the opacity of the original children
        (not the cuts) to a low value, otherwise set it back to 1.
        """
        at_least_one_cut = any(1 for cut in self.cuts if cut.visible)
        self.delete_cut.disabled = not at_least_one_cut
        self.cut_borders_visibility.disabled = not at_least_one_cut
        self.cut_operation.disabled = not at_least_one_cut
        self.tabs.titles = [cut._direction.upper() for cut in self.cuts]
        self.opacity.disabled = not at_least_one_cut
        opacity = self.opacity.value if at_least_one_cut else 1.0
        self._set_opacity({'new': opacity})

    def _set_opacity(self, change: Dict[str, Any]):
        """
        Set the opacity of the original point clouds in the figure, not the cuts.
        """
        self._view.set_opacity(change['new'])

    def toggle_visibility(self):
        """
        Toggle the visibility of the control buttons for making the cuts.
        """
        self.layout.display = None if self.layout.display == 'none' else 'none'

    def toggle_border_visibility(self, change: Dict[str, Any]):
        """
        Toggle the visibility of the borders of the cuts.
        """
        for cut in self.cuts:
            cut.toggle_border(change['new'])

    def change_operation(self, change: Dict[str, Any]):
        """
        Change the operation to combine multiple cuts.
        """
        self._operation = change['new'].lower()
        self.update_state()

    def update_state(self):
        """
        Update the state, combining all the active cuts, using the selected binary
        operation. The resulting selection is then used to either create or update a
        second point cloud which is included in the scene.
        The original point cloud is then set to be semi-transparent.
        When the position/range of a cut is changed, this function is called via a
        debounce mechanism to avoid updating the cloud too often. Only the outlines of
        the cuts are moved in real time, which is cheap.
        """
        for nodes in self._nodes.values():
            self._view.remove(nodes['slice'].id)
            nodes['slice'].remove()
        self._nodes.clear()

        visible_cuts = [cut for cut in self.cuts if cut.visible]
        if not visible_cuts:
            return

        for n in self._original_nodes:
            da = n.request_data()
            selections = []
            for cut in visible_cuts:
                xmin, xmax = cut.range
                selections.append(
                    (da.coords[cut.dim] > xmin) & (da.coords[cut.dim] < xmax)
                )
            selection = reduce(
                lambda x, y: OPERATIONS[self._operation](x, y), selections
            )
            if selection.sum().value > 0:
                if n.id not in self._nodes:
                    select_node = Node(selection)
                    self._nodes[n.id] = {
                        'select': select_node,
                        'slice': Node(lambda da, s: da[s], da=n, s=select_node),
                    }
                    self._nodes[n.id]['slice'].add_view(self._view)
                else:
                    self._nodes[n.id]['select'].func = lambda: selection
                self._nodes[n.id]['select'].notify_children("")

    @debounce(0.3)
    def throttled_update(self):
        self.update_state()
