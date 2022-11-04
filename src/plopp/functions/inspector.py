# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2022 Scipp contributors (https://github.com/scipp)

from .common import require_interactive_backend, preprocess
from .figure import figure1d, figure2d
from ..core import input_node, node, Node, View
from ..core.utils import coord_as_bin_edges

import scipp as sc
from numpy import ndarray
from typing import Any, Union, Dict, Literal


class InspectorEventHandler:
    """
    Class that handles the events triggered by the :class:`PointsTool` tool.
    This defines the actions to perform when:

      - a point is added to the 2D figure
      - a point is dragged on the 2D figure
      - a point is removed from the 2D figure
    """

    def __init__(self, data_array: sc.DataArray, root_node: Node, fig1d: View,
                 fig2d: View):
        self._data_array = data_array
        self._root_node = root_node
        self._fig1d = fig1d
        self._event_nodes = {}
        self._xdim = fig2d.dims['x']
        self._ydim = fig2d.dims['y']

    def make_node(self, change: Dict[str, Any]):
        from ..widgets import slice_dims
        event = change['event']
        event_node = Node(
            func=lambda: {
                self._xdim:
                sc.scalar(event.xdata, unit=self._data_array.meta[self._xdim].unit),
                self._ydim:
                sc.scalar(event.ydata, unit=self._data_array.meta[self._ydim].unit)
            })
        self._event_nodes[event_node.id] = event_node
        change['artist'].nodeid = event_node.id
        inspect_node = slice_dims(self._root_node, event_node)
        inspect_node.add_view(self._fig1d)
        self._fig1d.update(new_values=inspect_node.request_data(), key=inspect_node.id)

    def update_node(self, change: Dict[str, Any]):
        event = change['event']
        n = self._event_nodes[change['artist'].nodeid]
        n.func = lambda: {
            self._xdim: sc.scalar(event.xdata,
                                  unit=self._data_array.meta[self._xdim].unit),
            self._ydim: sc.scalar(event.ydata,
                                  unit=self._data_array.meta[self._ydim].unit)
        }
        n.notify_children(change)

    def remove_node(self, change: Dict[str, Any]):
        n = self._event_nodes[change['artist'].nodeid]
        pnode = n.children[0]
        self._fig1d.artists[pnode.id].remove()
        self._fig1d.canvas.draw()
        pnode.remove()
        n.remove()


def inspector(obj: Union[ndarray, sc.Variable, sc.DataArray],
              dim: str = None,
              *,
              operation: Literal['sum', 'mean', 'min', 'max'] = 'sum',
              orientation: Literal['horizontal', 'vertical'] = 'horizontal',
              crop: Dict[str, Dict[str, sc.Variable]] = None,
              **kwargs):
    """
    Inspector takes in a three-dimensional input and applies a reduction operation
    (``sum`` by default) along one of the dimensions specified by ``dim``.
    It displays the result as a two-dimensional image.
    In addition, an 'inspection' tool is available in the toolbar which allows to place
    markers on the image which perform slicing at that position to retain only the third
    dimension and displays the resulting one-dimensional slice on the right hand side
    figure.

    Controls:
    - Click to make new point
    - Drag existing point to move it
    - Middle-click to delete point

    Parameters
    ----------
    obj:
        The object to be plotted.
    dim:
        The dimension along which to apply the reduction operation. This will also be
        the dimension that remains in the one-dimensional slices generated by adding
        markers on the image. If no dim is provided, the last (inner) dim of the input
        data will be used.
    operation:
        The operation to apply along the third (undisplayed) dimension specified by
        ``dim``.
    orientation:
        Display the two panels side-by-side ('horizontal') or one below the other
        ('vertical').
    crop:
        Set the axis limits. Limits should be given as a dict with one entry per
        dimension to be cropped. Each entry should be a nested dict containing scalar
        values for ``'min'`` and/or ``'max'``. Example:
        ``da.plot(crop={'time': {'min': 2 * sc.Unit('s'), 'max': 40 * sc.Unit('s')}})``
    **kwargs:
        See :py:func:`plopp.plot` for the full list of figure customization arguments.

    Returns
    -------
    :
        A :class:`Box` which will contain two :class:`Figure` and one slider widget.
    """
    from ..widgets import PointsTool

    if obj.ndim != 3:
        raise ValueError('The inspector plot currently only work with '
                         f'three-dimensional data, found {obj.ndim} dims.')
    require_interactive_backend('inspector')

    da = preprocess(obj, crop=crop, ignore_size=True)
    a = input_node(da)
    if dim is None:
        dim = da.dims[-1]

    # Convert dimension coords to bin edges
    for d in set(da.dims) - {dim}:
        da.coords[d] = coord_as_bin_edges(da, d)

    op_node = node(getattr(sc, operation), dim=dim)(a)
    f2d = figure2d(op_node, **{**{'crop': crop}, **kwargs})
    f1d = figure1d()
    ev_handler = InspectorEventHandler(data_array=da, root_node=a, fig1d=f1d, fig2d=f2d)
    pts = PointsTool(ax=f2d.canvas.ax, tooltip='Add inspector points')
    pts.points.on_create = ev_handler.make_node
    pts.points.on_vertex_move = ev_handler.update_node
    pts.points.on_remove = ev_handler.remove_node
    f2d.toolbar['inspect'] = pts
    from ..widgets import Box
    out = [f2d, f1d]
    if orientation == 'horizontal':
        out = [out]
    return Box(out)
