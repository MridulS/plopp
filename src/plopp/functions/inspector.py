# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)

from typing import Dict, Literal, Union

import scipp as sc
from numpy import ndarray

from ..core import Node
from ..core.utils import coord_as_bin_edges
from ..graphics import figure1d, figure2d
from .common import preprocess, require_interactive_backend


def _slice_xy(da, xy):
    x = xy['x']
    y = xy['y']
    return da[y['dim'], y['value']][x['dim'], x['value']]


def _apply_op(da, op, dim):
    out = getattr(sc, op)(da, dim=dim)
    if out.name:
        out.name = f'{op} of {out.name}'
    return out


def inspector(
    obj: Union[ndarray, sc.Variable, sc.DataArray],
    dim: str = None,
    *,
    operation: Literal['sum', 'mean', 'min', 'max'] = 'sum',
    orientation: Literal['horizontal', 'vertical'] = 'horizontal',
    crop: Dict[str, Dict[str, sc.Variable]] = None,
    **kwargs,
):
    """
    Inspector takes in a three-dimensional input and applies a reduction operation
    (``'sum'`` by default) along one of the dimensions specified by ``dim``.
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
    if obj.ndim != 3:
        raise ValueError(
            'The inspector plot currently only work with '
            f'three-dimensional data, found {obj.ndim} dims.'
        )
    require_interactive_backend('inspector')

    da = preprocess(obj, crop=crop, ignore_size=True)
    in_node = Node(da)
    if dim is None:
        dim = da.dims[-1]

    # Convert dimension coords to bin edges
    for d in set(da.dims) - {dim}:
        da.coords[d] = coord_as_bin_edges(da, d)

    op_node = Node(_apply_op, da=in_node, op=operation, dim=dim)
    f2d = figure2d(op_node, **{**{'crop': crop}, **kwargs})
    f1d = figure1d()

    from ..widgets import Box, PointsTool

    pts = PointsTool(
        figure=f2d,
        input_node=in_node,
        func=_slice_xy,
        destination=f1d,
        tooltip="Activate inspector tool",
    )
    f2d.toolbar['inspect'] = pts
    out = [f2d, f1d]
    if orientation == 'horizontal':
        out = [out]
    return Box(out)
