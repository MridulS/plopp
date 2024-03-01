# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)

import uuid
from functools import partial
from typing import Literal, Optional, Tuple, Union

import scipp as sc

from ..core.typing import PlottableMulti
from .common import check_not_binned, from_compatible_lib, input_to_nodes


def _preprocess_scatter(
    obj: PlottableMulti,
    x: str,
    y: str,
    size: Optional[str],
    name: Optional[str] = None,
):
    da = from_compatible_lib(obj)
    check_not_binned(da)

    cnames = [x, y]
    if size is not None:
        cnames.append(size)
    coords = {k: da.coords[k] for k in cnames}
    out = sc.DataArray(data=da.data, masks=da.masks, coords=coords)
    if out.ndim != 1:
        out = out.flatten(to=uuid.uuid4().hex)
    if name is not None:
        out.name = name
    return out


def scatter(
    obj: PlottableMulti,
    *,
    x: str = 'x',
    y: str = 'y',
    size: Optional[Union[str, float]] = None,
    figsize: Tuple[float, float] = None,
    norm: Literal['linear', 'log'] = 'linear',
    title: str = None,
    vmin: Union[sc.Variable, int, float] = None,
    vmax: Union[sc.Variable, int, float] = None,
    cbar: bool = False,
    cmap: str = 'viridis',
    **kwargs,
):
    """
    Make a two-dimensional scatter plot.

    .. versionadded:: 24.03.0

    Parameters
    ----------
    obj:
        The object to be plotted.
    x:
        The name of the coordinate that is to be used for the X positions.
    y:
        The name of the coordinate that is to be used for the Y positions.
    size:
        The size of the marker. If a float is supplied, all markers will have the same
        size. If a string is supplied, it will be the name of the coordinate that is to
        be used for the size of the markers.
    figsize:
        The width and height of the figure, in inches.
    norm:
        Set to ``'log'`` for a logarithmic colorscale (only applicable if ``cbar`` is
        ``True``).
    title:
        The figure title.
    vmin:
        Lower bound for the colorscale for (only applicable if ``cbar`` is ``True``).
    vmax:
        Upper bound for the colorscale for (only applicable if ``cbar`` is ``True``).
    cbar:
        Show colorbar if ``True``. If ``cbar`` is ``True``, the marker will be colored
        using the data values in the supplied data array.
    cmap:
        The colormap to be used for the colorscale.
    **kwargs:
        All other kwargs are forwarded the underlying plotting library.
    """
    from ..graphics import scatterfigure

    nodes = input_to_nodes(
        obj, processor=partial(_preprocess_scatter, x=x, y=y, size=size)
    )

    return scatterfigure(
        *nodes,
        x=x,
        y=y,
        size=size,
        figsize=figsize,
        norm=norm,
        title=title,
        vmin=vmin,
        vmax=vmax,
        cmap=cmap,
        cbar=cbar,
        **kwargs,
    )
