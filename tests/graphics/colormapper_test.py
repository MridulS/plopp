# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)

from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import partial
from typing import Callable

import numpy as np
import pytest
import scipp as sc
from matplotlib.colors import LogNorm, Normalize

from plopp import Node, imagefigure, scatter3dfigure
from plopp.data.testing import data_array, scatter
from plopp.graphics.colormapper import ColorMapper


def string_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


class DummyChild:
    def __init__(self, data):
        self._data = data
        self._colors = None

    def set_colors(self, colors):
        self._colors = colors

    def update(self, data):
        self._data = data

    @property
    def data(self):
        return self._data


def test_creation():
    mapper = ColorMapper(
        cmap='magma',
        mask_cmap='jet',
        norm='linear',
        vmin=sc.scalar(1, unit='K'),
        vmax=sc.scalar(10, unit='K'),
    )
    assert mapper.cmap.name == 'magma'
    assert mapper.mask_cmap.name == 'jet'
    assert mapper.norm == 'linear'
    assert sc.identical(mapper.user_vmin, sc.scalar(1, unit='K'))
    assert sc.identical(mapper.user_vmax, sc.scalar(10, unit='K'))


def test_norm():
    mapper = ColorMapper(norm='log')
    assert mapper.norm == 'log'


def test_autoscale():
    da = data_array(ndim=2, unit='K')
    mapper = ColorMapper()
    artist = DummyChild(da)
    mapper['data'] = artist

    mapper.update(data=da)
    mapper.autoscale()
    assert mapper.vmin == da.min().value
    assert mapper.vmax == da.max().value

    # Limits grow
    const = 2.3
    artist.update(da * const)
    mapper.update(data=da * const)
    mapper.autoscale()
    assert mapper.vmin == (da.min() * const).value
    assert mapper.vmax == (da.max() * const).value

    # Limits shrink
    const = 0.5
    artist.update(da * const)
    mapper.update(data=da * const)
    mapper.autoscale()
    assert mapper.vmin == da.min().value * const
    assert mapper.vmax == da.max().value * const


def test_update_without_autoscale_does_not_change_limits():
    da = data_array(ndim=2, unit='K')
    mapper = ColorMapper()
    artist = DummyChild(da)
    mapper['data'] = artist

    mapper.update(data=da)
    mapper.autoscale()
    assert mapper.vmin == da.min().value
    assert mapper.vmax == da.max().value

    backup = mapper.vmin, mapper.vmax

    # Limits grow
    const = 2.3
    artist.update(da * const)
    mapper.update(data=da * const)
    assert mapper.vmin != (da.min() * const).value
    assert mapper.vmin == backup[0]
    assert mapper.vmax != (da.max() * const).value
    assert mapper.vmax == backup[1]

    # Limits shrink
    const = 0.5
    artist.update(da * const)
    mapper.update(data=da * const)
    assert mapper.vmin != da.min().value * const
    assert mapper.vmin == backup[0]
    assert mapper.vmax != da.max().value * const
    assert mapper.vmax == backup[1]


# def test_auto_rescale_limits_can_shrink():
#     da = data_array(ndim=2, unit='K')
#     mapper = ColorMapper(autoscale='auto')
#     artist = DummyChild(da)
#     mapper['data'] = artist

#     mapper.update(data=da)
#     assert mapper.vmin == da.min().value
#     assert mapper.vmax == da.max().value

#     const = 0.5
#     artist.update(da * const)
#     mapper.update(data=da * const)
#     assert mapper.vmin == da.min().value * const
#     assert mapper.vmax == da.max().value * const


# def test_grow_rescale_limits_do_not_shrink():
#     da = data_array(ndim=2, unit='K')
#     mapper = ColorMapper(autoscale='grow')
#     artist = DummyChild(da)
#     mapper['data'] = artist

#     mapper.update(data=da)
#     assert mapper.vmin == da.min().value
#     assert mapper.vmax == da.max().value

#     const = 0.5
#     artist.update(da * const)
#     mapper.update(data=da * const)
#     assert mapper.vmin == da.min().value
#     assert mapper.vmax == da.max().value


def test_correct_normalizer_limits():
    da = sc.DataArray(data=sc.array(dims=['y', 'x'], values=[[1, 2], [3, 4]]))
    mapper = ColorMapper()
    artist = DummyChild(da)
    mapper['data'] = artist
    mapper.update(data=da)
    mapper.autoscale()
    assert mapper.vmin == da.min().value
    assert mapper.vmax == da.max().value
    # The normalizer initially has limits [0, 1].
    # In Matplotlib, if we set the normalizer vmin value (1) equal to the current vmax,
    # it will silently set it to something smaller, e.g. 0.9.
    # Our implementation needs to work around this.
    assert mapper.normalizer.vmin == da.min().value
    assert mapper.normalizer.vmax == da.max().value


def test_vmin_vmax():
    da = data_array(ndim=2, unit='K') * 100.0
    vmin = sc.scalar(-0.1, unit='K')
    vmax = sc.scalar(3.5, unit='K')
    mapper = ColorMapper(vmin=vmin, vmax=vmax)
    artist = DummyChild(da)
    mapper['data'] = artist
    mapper.update(data=da)
    mapper.autoscale()
    assert mapper.user_vmin == vmin.value
    assert mapper.user_vmax == vmax.value
    assert mapper.vmin == vmin.value
    assert mapper.vmax == vmax.value


def test_vmin_vmax_no_variable():
    da = data_array(ndim=2, unit='K') * 100.0
    vmin = -0.1
    vmax = 3.5
    mapper = ColorMapper(vmin=vmin, vmax=vmax)
    artist = DummyChild(da)
    mapper['data'] = artist
    mapper.update(data=da)
    mapper.autoscale()
    assert mapper.user_vmin == vmin
    assert mapper.user_vmax == vmax
    assert mapper.vmin == vmin
    assert mapper.vmax == vmax


def test_toggle_norm():
    mapper = ColorMapper()
    da = data_array(ndim=2, unit='K')
    mapper['child1'] = DummyChild(da)
    mapper.update(child1=da)
    mapper.autoscale()
    assert mapper.norm == 'linear'
    assert isinstance(mapper.normalizer, Normalize)
    assert mapper.vmin == da.min().value
    assert mapper.vmax == da.max().value

    mapper.toggle_norm()
    assert mapper.norm == 'log'
    assert isinstance(mapper.normalizer, LogNorm)
    assert mapper.vmin > 0
    assert mapper.vmax == da.max().value


def test_update_changes_limits():
    da = data_array(ndim=2, unit='K')
    mapper = ColorMapper()
    artist = DummyChild(da)
    mapper['data'] = artist

    mapper.update(data=da)
    mapper.autoscale()
    assert mapper.normalizer.vmin == da.min().value
    assert mapper.normalizer.vmax == da.max().value

    const = 2.3
    artist.update(da * const)
    mapper.update(data=da * const)
    mapper.autoscale()
    assert mapper.normalizer.vmin == (da.min() * const).value
    assert mapper.normalizer.vmax == (da.max() * const).value


def test_rgba():
    da = data_array(ndim=2, unit='K')
    mapper = ColorMapper()
    colors = mapper.rgba(da)
    assert colors.shape == (*da.data.shape, 4)


def test_rgba_with_masks():
    da1 = data_array(ndim=2, unit='K')
    da2 = data_array(ndim=2, unit='K', masks=True)
    mapper = ColorMapper()
    assert not np.allclose(mapper.rgba(da1), mapper.rgba(da2))


def test_colorbar_updated_on_rescale():
    da = data_array(ndim=2, unit='K')
    mapper = ColorMapper()
    artist = DummyChild(da)
    key = 'data'
    mapper[key] = artist

    mapper.update(data=da)
    mapper.autoscale()
    _ = mapper.to_widget()
    old_image = mapper.widget.value
    old_image_array = old_image

    # Update with the same values should not make a new colorbar image
    artist.update(da)
    mapper.update(data=da)
    mapper.autoscale()
    assert string_similarity(old_image_array, mapper.widget.value) > 0.9

    # Update with a smaller range should make a new colorbar image
    const = 0.8
    artist.update(da * const)
    mapper.update(data=da * const)
    mapper.autoscale()
    assert string_similarity(old_image_array, mapper.widget.value) < 0.9

    # Update with larger range should make a new colorbar image
    const = 2.3
    artist.update(da * const)
    mapper.update(data=da * const)
    mapper.autoscale()
    assert string_similarity(old_image_array, mapper.widget.value) < 0.9


def test_colorbar_does_not_update_if_no_autoscale():
    da = data_array(ndim=2, unit='K')
    mapper = ColorMapper()
    artist = DummyChild(da)
    key = 'data'
    mapper[key] = artist

    mapper.update(data=da)
    mapper.autoscale()
    _ = mapper.to_widget()
    old_image = mapper.widget.value
    old_image_array = old_image

    # Update with the same values
    artist.update(da)
    mapper.update(data=da)
    assert old_image is mapper.widget.value

    # Update with a smaller range
    const = 0.8
    artist.update(da * const)
    mapper.update(data=da * const)
    assert old_image is mapper.widget.value

    # Update with larger range
    const = 2.3
    artist.update(da * const)
    mapper.update(data=da * const)
    assert old_image_array is mapper.widget.value


def test_colorbar_is_not_created_if_cbar_false():
    mapper = ColorMapper(cbar=False)
    assert mapper.colorbar is None
    assert mapper.cax is None


def test_colorbar_cbar_false_overrides_cax():
    @dataclass
    class Canvas:
        cax: int

    mapper = ColorMapper(cbar=False, canvas=Canvas(cax=0))
    assert mapper.colorbar is None


def test_autoscale_vmin_set():
    da = data_array(ndim=2, unit='K')
    mapper = ColorMapper(vmin=-0.5)
    artist = DummyChild(da)
    key = 'data'
    mapper[key] = artist
    mapper.update(data=da)
    mapper.autoscale()
    assert mapper.vmin == -0.5
    assert mapper.vmax == da.max().value
    # Make sure it handles when da.max() is greater than vmin
    mapper.update(data=da - sc.scalar(5.0, unit='K'))
    mapper.autoscale()
    assert mapper.vmin == -0.5
    assert mapper.vmin < mapper.vmax


def test_autoscale_vmax_set():
    da = data_array(ndim=2, unit='K')
    mapper = ColorMapper(vmax=0.5)
    artist = DummyChild(da)
    key = 'data'
    mapper[key] = artist
    mapper.update(data=da)
    mapper.autoscale()
    assert mapper.vmax == 0.5
    assert mapper.vmin == da.min().value
    # Make sure it handles when da.min() is greater than vmax
    mapper.update(data=da + sc.scalar(5.0, unit='K'))
    mapper.autoscale()
    assert mapper.vmax == 0.5
    assert mapper.vmin < mapper.vmax


@dataclass
class FigureAndData:
    figure: Callable
    data: Callable


PLOTCASES = [
    FigureAndData(partial(imagefigure, cbar=True), partial(data_array, ndim=2)),
    FigureAndData(partial(scatter3dfigure, x='x', y='y', z='z', cbar=True), scatter),
]


@pytest.mark.usefixtures('_use_ipympl')
@pytest.mark.parametrize('case', PLOTCASES)
def test_toolbar_log_norm_button_state_agrees_with_kwarg(case):
    da = case.data()
    fig = case.figure(Node(da))
    assert not fig.toolbar['lognorm'].value
    assert fig.view.colormapper.norm == 'linear'
    fig = case.figure(Node(da), norm='log')
    assert fig.toolbar['lognorm'].value
    assert fig.view.colormapper.norm == 'log'


@pytest.mark.usefixtures('_use_ipympl')
@pytest.mark.parametrize('case', PLOTCASES)
def test_toolbar_log_norm_button_toggles_colormapper_norm(case):
    da = case.data()
    fig = case.figure(Node(da))
    assert fig.view.colormapper.norm == 'linear'
    fig.toolbar['lognorm'].value = True
    assert fig.view.colormapper.norm == 'log'


@pytest.mark.parametrize('case', PLOTCASES)
def test_colorbar_label_has_no_name_with_multiple_artists(case):
    a = case.data(unit='K')
    b = 3.3 * a
    a.name = 'A data'
    b.name = 'B data'
    fig = case.figure(Node(a), Node(b))
    assert fig.view.colormapper.cax.get_ylabel() == '[K]'
