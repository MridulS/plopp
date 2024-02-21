# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)

import asyncio
from functools import partial
from typing import Any, Callable, Dict, List, Literal, Tuple

import ipywidgets as ipw
import numpy as np
import scipp as sc

from ..core import View, Node, node
from .style import BUTTON_LAYOUT
from .tools import PlusMinusTool


class Timer:
    """
    From:
    https://ipywidgets.readthedocs.io/en/8.0.2/examples/Widget%20Events.html#Debouncing
    """

    def __init__(self, timeout: float, callback: Callable):
        self._timeout = timeout
        self._callback = callback

    async def _job(self):
        await asyncio.sleep(self._timeout)
        self._callback()

    def start(self):
        self._task = asyncio.ensure_future(self._job())

    def cancel(self):
        self._task.cancel()


def debounce(wait: float):
    """
    Decorator that will postpone a function's
    execution until after `wait` seconds
    have elapsed since the last time it was invoked.

    From:
    https://ipywidgets.readthedocs.io/en/8.0.2/examples/Widget%20Events.html#Debouncing
    """

    def decorator(fn: Callable):
        timer = None

        def debounced(*args, **kwargs):
            nonlocal timer

            def call_it():
                fn(*args, **kwargs)

            if timer is not None:
                timer.cancel()
            timer = Timer(wait, call_it)
            timer.start()

        return debounced

    return decorator


class Cut3dTool(ipw.HBox):
    """
    A tool that provides a slider to extract a plane of points in a three-dimensional
    scatter plot, and add it to the scene as an opaque cut. The slider controls the
    position of the slice. When the slider is dragged, the red outline of the cut is
    moved at the same time, while the actual point cloud gets updated less frequently
    using a debounce mechanism.

    The tool also has two buttons +/- to increase/decrease the thickness of the cut.

    Parameters
    ----------
    view:
        The 3d figure that contains the point clouds to be cut.
    nodes:
        The nodes that contain the original data to be cut.
    limits:
        The spatial extent of the points in the 3d figure in the XYZ directions.
    direction:
        The direction normal to the slice.
    value:
        Set the cut to active upon creation if ``True``.
    color:
        Color of the cut's outline.
    linewidth:
        Width of the line delineating the outline.
    **kwargs:
        The kwargs are forwarded to the ToggleButton from ``ipywidgets``.
    """

    def __init__(
        self,
        view: View,
        nodes: List[Node],
        limits: Tuple[sc.Variable, sc.Variable, sc.Variable],
        direction: Literal['x', 'y', 'z'],
        value: bool = True,
        color: str = 'red',
        linewidth: float = 1.5,
        disabled: bool = False,
        **kwargs,
    ):
        import pythreejs as p3

        self._limits = limits
        self._direction = direction
        axis = 'xyz'.index(self._direction)
        self._dim = self._limits[axis].dim
        self._unit = self._limits[axis].unit
        self._view = view
        self.disabled = disabled

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
            # self.outline.rotateY(0.5 * np.pi)
        if self._direction == 'y':
            for outline in self.outlines:
                outline.rotateX(0.5 * np.pi)
            # self.outline.rotateX(0.5 * np.pi)

        # dx =
        center = [var.mean().value for var in self._limits]

        # self.button = ipw.ToggleButton(value=value, **kwargs)
        # self.checkbox = ipw.Checkbox(
        #     value=True, indent=False, tooltip='Hide/Show', layout={"width": "initial"}
        # )
        self.cut_visible = ipw.Button(
            icon='eye-slash',
            tooltip='Hide cut',
            layout={'width': '15px', 'padding': '0px'},
            disabled=self.disabled,
        )
        self.border_visible = ipw.Button(
            icon='border-style',
            tooltip='Toggle border',
            layout={'width': '15px', 'padding': '0px'},
            disabled=self.disabled,
        )
        self.slider = ipw.FloatRangeSlider(
            min=limits[axis][0].value,
            max=limits[axis][1].value,
            # value=center[axis],
            description=direction.upper(),
            style={'description_width': 'initial'},
            layout={'width': '450px', 'padding': '0px'},
            disabled=self.disabled,
            # readout=False,
        )
        dx = self.slider.max - self.slider.min
        # self.slider.step = dx * 0.01
        delta = 0.05 * dx
        self.slider.value = [center[axis] - delta, center[axis] + delta]

        for outline, val in zip(self.outlines, self.slider.value):
            pos = list(center)
            pos[axis] = val
            outline.position = pos
            outline.visible = not self.disabled

        # self.thickness = 0.01
        # self._thickness_step = self.thickness * 0.25

        # self.button = ipw.ToggleButton(value=value, **kwargs)
        # self.slider = ipw.FloatRangeSlider(
        #     min=limits[axis][0].value,
        #     max=limits[axis][1].value,
        #     value=center[axis],
        #     layout={'width': '150px', 'padding': '0px'},
        #     disabled=not value,
        #     readout=False,
        # )
        # self.slider.step = (self.slider.max - self.slider.min) * self.thickness * 0.5
        # self.readout = ipw.FloatText(
        #     layout={'width': '70px'}, step=self.slider.step, disabled=not value
        # )
        self.unit_label = ipw.Label(f'[{self._unit}]')
        # ipw.jslink((self.slider, "value"), (self.readout, "value"))

        # self.plus_minus = PlusMinusTool(
        #     plus={
        #         'callback': self.increase_thickness,
        #         'tooltip': 'Increase cut thickness',
        #         'disabled': not value,
        #     },
        #     minus={
        #         'callback': self.decrease_thickness,
        #         'tooltip': 'Decrease cut thickness',
        #         'disabled': not value,
        #     },
        # )

        self.cut_visible.on_click(self.toggle)
        self.border_visible.on_click(self.toggle_border)
        self.slider.observe(self.move, names='value')
        self.slider.observe(self.update_cut, names='value')

        self._nodes = nodes
        self.select_nodes = {}

        # super().__init__(
        #     [
        #         # ipw.VBox([self.button, self.plus_minus]),
        #         ipw.VBox([self.button]),
        #         ipw.VBox(
        #             # [self.slider, ipw.HBox([self.readout, self.unit_label])],
        #             [self.slider, ipw.HBox([self.unit_label])],
        #             layout={'align_items': 'center'},
        #         ),
        #     ]
        # )
        # self._add_cut()
        super().__init__(
            [
                self.slider,
                ipw.Label(f'[{self._unit}]'),
                self.cut_visible,
                self.border_visible,
            ]
        )

    def toggle(self, owner):
        """
        Toggle the tool on and off.
        """
        value = bool(self.select_nodes)
        for outline in self.outlines:
            outline.visible = not value
        # self.outline.visible = change['new']
        # for widget in (self.slider, self.plus_minus, self.readout):
        self.slider.disabled = value
        if not value:
            self._add_cut()
        else:
            self._remove_cut()
        owner.icon = 'eye' if value else 'eye'
        owner.tooltip = 'Show cut' if value else 'Hide cut'

    def toggle_border(self, owner):
        """
        Toggle the border visbility.
        """
        value = self.outlines[0].visible
        for outline in self.outlines:
            outline.visible = not value

    def move(self, value: Dict[str, Any]):
        """
        Move the outline of the cut according to new position given by the slider.
        """
        for outline, val in zip(self.outlines, value['new']):
            pos = list(outline.position)
            axis = 'xyz'.index(self._direction)
            pos[axis] = val
            outline.position = pos
        # pos = list(self.outline.position)
        # axis = 'xyz'.index(self._direction)
        # pos[axis] = value['new']
        # self.outline.position = pos
        self._remove_cut()

    def _add_cut(self):
        """
        Add a point cloud representing the points that intersect the cut plane.
        """

        def select(da, s):
            return da[s]

        for n in self._nodes:
            da = n.request_data()
            # delta = sc.scalar(
            #     (self.slider.max - self.slider.min) * self.thickness, unit=self._unit
            # )
            # pos = sc.scalar(self.slider.value, unit=self._unit)
            # selection = sc.abs(da.coords[self._dim] - pos) < delta
            selection = (
                da.coords[self._dim] > sc.scalar(self.slider.value[0], unit=self._unit)
            ) & (
                da.coords[self._dim] < sc.scalar(self.slider.value[1], unit=self._unit)
            )
            if selection.sum().value > 0:
                self.select_nodes[n.id] = node(partial(select, s=selection))(da=n)
                self.select_nodes[n.id].add_view(self._view)
                self._view.update(
                    self.select_nodes[n.id].request_data(),
                    key=self.select_nodes[n.id].id,
                )

    def _remove_cut(self):
        """
        Remove a cut point the scene.
        """
        for n in self.select_nodes.values():
            self._view.remove(n.id)
            n.remove()
        self.select_nodes.clear()

    @debounce(0.3)
    def update_cut(self, _):
        """
        Update the position of the point cloud. This uses the debounce mechanism to
        avoid updating the cloud too often, and instead rely on simply moving the
        outline, which is cheap.
        """
        # if self.value:
        self._add_cut()

    # @property
    # def value(self):
    #     """
    #     Return the state of the ToggleButton.
    #     """
    #     return self.button.value

    # def increase_thickness(self):
    #     """
    #     Increase the thickness of the cut.
    #     """
    #     self.thickness = self.thickness + self._thickness_step
    #     self._remove_cut()
    #     self._add_cut()

    # def decrease_thickness(self):
    #     """
    #     Decrease the thickness of the cut.
    #     """
    #     self.thickness = max(self.thickness - self._thickness_step, 0)
    #     self._remove_cut()
    #     self._add_cut()


class TriCutTool(ipw.HBox):
    """
    A collection of :class:`Cut3dTool` to make spatial cuts in the X, Y, and Z
    directions on a three-dimensional scatter plot.

    Parameters
    ----------
    fig:
        The 3d figure that contains the point clouds to be cut.
    """

    def __init__(self, fig: View):
        self._fig = fig
        self._limits = self._fig.get_limits()
        self.cuts = []
        # self.cuts_container = ipw.VBox([])

        self.tabs = ipw.Tab()
        # tab.children = children
        # tab.titles = [str(i) for i in range(len(children))]

        self._original_nodes = list(self._fig.graph_nodes.values())

        self.add_cut_label = ipw.Label('Add cut:')
        self.add_x_cut = ipw.Button(
            description='X',
            icon='plus',
            tooltip='Add X cut',
            **BUTTON_LAYOUT,
        )
        self.add_y_cut = ipw.Button(
            description='Y',
            icon='plus',
            tooltip='Add Y cut',
            **BUTTON_LAYOUT,
        )
        self.add_z_cut = ipw.Button(
            description='Z',
            icon='plus',
            tooltip='Add Z cut',
            **BUTTON_LAYOUT,
        )
        self.add_x_cut.on_click(lambda _: self._add_cut('x'))
        self.add_y_cut.on_click(lambda _: self._add_cut('y'))
        self.add_z_cut.on_click(lambda _: self._add_cut('z'))

        # self.cut_x = Cut3dTool(
        #     view=self._fig,
        #     direction='x',
        #     limits=limits,
        #     description='X',
        #     icon='cube',
        #     **BUTTON_LAYOUT,
        # )
        # self.cut_y = Cut3dTool(
        #     view=self._fig,
        #     direction='y',
        #     limits=limits,
        #     description='Y',
        #     icon='cube',
        #     **BUTTON_LAYOUT,
        # )
        # self.cut_z = Cut3dTool(
        #     view=self._fig,
        #     direction='z',
        #     limits=limits,
        #     description='Z',
        #     icon='cube',
        #     **BUTTON_LAYOUT,
        # )

        # self._fig.canvas.add(
        #     self.cut_x.outlines + self.cut_y.outlines + self.cut_z.outlines
        # )

        self.opacity = ipw.BoundedFloatText(
            min=0,
            max=0.5,
            step=0.01,
            disabled=True,
            value=0.03,
            description='Opacity:',
            style={'description_width': 'initial'},
            layout={'width': '120px', 'padding': '0px 0px 0px 0px'},
        )
        self.opacity.observe(self._set_opacity, names='value')

        self.delete_cut = ipw.Button(
            description='Delete cut',
            icon='trash',
            layout={'width': '120px', 'padding': '0px 0px 0px 0px'},
        )
        self.delete_cut.on_click(self._remove_cut)

        # self.cut_x.button.observe(self._toggle_opacity, names='value')
        # self.cut_y.button.observe(self._toggle_opacity, names='value')
        # self.cut_z.button.observe(self._toggle_opacity, names='value')

        # self.tabs.children = [
        #     ipw.HBox(
        #         [
        #             ipw.FloatRangeSlider(disabled=True),
        #             # self.add_x_cut,
        #             # self.add_y_cut,
        #             # self.add_z_cut,
        #             # self.opacity,
        #         ]
        #     )
        # ]
        self._add_cut('x')

        super().__init__(
            [
                self.tabs,
                ipw.VBox(
                    [
                        ipw.HBox([self.add_x_cut, self.add_y_cut, self.add_z_cut]),
                        self.opacity,
                        self.delete_cut,
                    ]
                ),
            ]
        )

        # super().__init__(
        #     [
        #         ipw.HBox(
        #             [
        #                 self.add_cut_label,
        #                 self.add_x_cut,
        #                 self.add_y_cut,
        #                 self.add_z_cut,
        #                 self.opacity,
        #             ]
        #         ),
        #         self.cuts_container,
        #     ]
        # )

        # space = ipw.HBox([], layout={'width': '10px'})
        # super().__init__(
        #     [
        #         self.cut_x,
        #         space,
        #         self.cut_y,
        #         space,
        #         self.cut_z,
        #         space,
        #         ipw.VBox([ipw.Label('Opacity:'), self.opacity]),
        #     ]
        # )
        self.layout.display = 'none'

    def _add_cut(self, direction: Literal['x', 'y', 'z']):
        """
        Add a cut in the specified direction.
        """
        disabled = len(self.cuts) == 0
        print('add cut', direction, disabled)
        cut = Cut3dTool(
            view=self._fig,
            nodes=self._original_nodes,
            direction=direction,
            limits=self._limits,
            description=direction.upper(),
            # value=True,
            disabled=disabled,
        )
        # if not no_current_cuts:
        # self.cuts.append(cut)
        self._fig.canvas.add(cut.outlines)
        self.cuts.append(cut)
        # if len(self.cuts) == 1:
        #     if self.c
        #     self.tabs.children = [cut]
        # else:
        self.tabs.children = list(self.tabs.children) + [cut]
        if (not disabled) and self.cuts[0].disabled:
            self._remove_cut(None)
        else:
            self.update_tabs_titles()
        self._toggle_opacity()

    def _remove_cut(self, _):
        # print(self.tabs.selected_index)
        cut = self.cuts.pop(self.tabs.selected_index)
        cut._remove_cut()
        self._fig.canvas.remove(cut.outlines)
        self.tabs.children = self.cuts
        self.update_tabs_titles()
        print('len(self.cuts)', len(self.cuts))
        if len(self.cuts) == 0:
            self._add_cut('x')

    def update_tabs_titles(self):
        self.tabs.titles = [cut._direction.upper() for cut in self.cuts]

    def _toggle_opacity(self):
        """
        If any cut is active, set the opacity of the original children (not the cuts) to
        a low value. If all cuts are inactive, set the opacity back to 1.
        """
        # active_cut = any([self.cut_x.value, self.cut_y.value, self.cut_z.value])
        active_cut = any(1 for cut in self.cuts if not cut.disabled)
        # active_cut = len(self.cuts) > 0
        self.opacity.disabled = not active_cut
        opacity = self.opacity.value if active_cut else 1.0
        self._set_opacity({'new': opacity})

    def _set_opacity(self, change: Dict[str, Any]):
        """
        Set the opacity of the original point clouds in the figure, not the cuts.
        """
        self._fig.set_opacity(change['new'])

    def toggle_visibility(self):
        """
        Toggle the visibility of the control buttons for making the cuts.
        """
        self.layout.display = None if self.layout.display == 'none' else 'none'
