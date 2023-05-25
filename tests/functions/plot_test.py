# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)

import os
import tempfile

import numpy as np
import pytest
import scipp as sc

import plopp as pp
from plopp.data.testing import data_array, dataset


def test_plot_ndarray():
    pp.plot(np.arange(50.0))


def test_plot_list():
    pp.plot([1, 2, 3, 4, 5])


def test_plot_variable():
    pp.plot(sc.arange('x', 50.0))


def test_plot_data_array():
    pp.plot(data_array(ndim=1))
    da = data_array(ndim=2)
    pp.plot(da)
    pp.plot(da)


def test_plot_data_array_missing_coords():
    da = sc.data.table_xyz(100)
    pp.plot(da)
    assert 'row' not in da.coords


def test_plot_dataset():
    ds = dataset(ndim=1)
    pp.plot(ds)


def test_plot_dict_of_ndarrays():
    pp.plot({'a': np.arange(50.0), 'b': np.arange(60.0)})


def test_plot_dict_of_lists():
    pp.plot({'a': [1, 2, 3, 4], 'b': [4, 5, 6, 7]})


def test_plot_dict_of_variables():
    pp.plot({'a': sc.arange('x', 50.0), 'b': sc.arange('x', 60.0)})


def test_plot_dict_of_data_arrays():
    ds = dataset(ndim=1)
    pp.plot({'a': ds['a'], 'b': ds['b']})


def test_plot_data_array_2d_with_one_missing_coord_and_binedges():
    da = sc.data.table_xyz(100).bin(x=10, y=12).bins.mean()
    del da.coords['x']
    pp.plot(da)


def test_plot_coord_with_no_unit():
    da = sc.data.table_xyz(100).bin(x=10).bins.mean()
    da.coords['x'].unit = None
    pp.plot(da)


def test_plot_rejects_large_input():
    error_match = "may take very long or use an excessive amount of memory"
    with pytest.raises(ValueError, match=error_match):
        pp.plot(np.random.random(1_100_000))
    with pytest.raises(ValueError, match=error_match):
        pp.plot(np.random.random((3000, 2500)))


def test_plot_ignore_size_disables_size_check():
    pp.plot(np.random.random(1_100_000), ignore_size=True)


def test_plot_with_non_dimensional_unsorted_coord_does_not_warn():
    da = data_array(ndim=1)
    da.coords['aux'] = sc.sin(sc.arange(da.dim, 50.0, unit='rad'))
    pp.plot(da)


def test_plot_2d_coord():
    da = data_array(ndim=2, ragged=True)
    pp.plot(da)
    pp.plot(da.transpose())


def test_plot_2d_coord_with_mask():
    da = data_array(ndim=2, ragged=True)
    da.masks['negative'] = da.data < sc.scalar(0, unit='m/s')
    pp.plot(da)


def _get_artist(fig, n=0):
    artists = fig.artists
    keys = list(artists.keys())
    return artists[keys[n]]


def _get_line(fig, n=0):
    return _get_artist(fig=fig, n=n)._line


def test_kwarg_linecolor():
    da = data_array(ndim=1)
    p = pp.plot(da, color='r')
    assert _get_line(p).get_color() == 'r'
    p = pp.plot(da, c='b')
    assert _get_line(p).get_color() == 'b'


def test_kwarg_linestyle():
    da = data_array(ndim=1)
    p = pp.plot(da, linestyle='solid')
    assert _get_line(p).get_linestyle() == '-'
    p = pp.plot(da, ls='dashed')
    assert _get_line(p).get_linestyle() == '--'


def test_kwarg_linewidth():
    da = data_array(ndim=1)
    p = pp.plot(da, linewidth=3)
    assert _get_line(p).get_linewidth() == 3
    p = pp.plot(da, lw=5)
    assert _get_line(p).get_linewidth() == 5


def test_kwarg_marker():
    da = data_array(ndim=1)
    p = pp.plot(da, marker='+')
    assert _get_line(p).get_marker() == '+'


def test_kwarg_norm():
    da = data_array(ndim=1)
    p = pp.plot(da, norm='log')
    assert p.canvas.ax.get_yscale() == 'log'


def test_kwarg_scale():
    da = data_array(ndim=1)
    p = pp.plot(da, scale={'xx': 'log'})
    assert p.canvas.ax.get_xscale() == 'log'
    assert p.canvas.ax.get_yscale() == 'linear'


def test_kwarg_cmap():
    da = data_array(ndim=2)
    p = pp.plot(da, cmap='magma')
    assert p._fig.colormapper.cmap.name == 'magma'


def test_kwarg_scale_2d():
    da = data_array(ndim=2)
    p = pp.plot(da, scale={'xx': 'log', 'yy': 'log'})
    assert p.canvas.ax.get_xscale() == 'log'
    assert p.canvas.ax.get_yscale() == 'log'


def test_kwarg_crop_1d_min_max():
    da = data_array(ndim=1)
    p = pp.plot(
        da,
        crop={'xx': {'min': sc.scalar(20, unit='m'), 'max': sc.scalar(40, unit='m')}},
    )
    assert np.array_equal(p.canvas.ax.get_xlim(), [20, 40])


def test_kwarg_crop_1d_min_only():
    da = data_array(ndim=1)
    p = pp.plot(da, crop={'xx': {'min': sc.scalar(20, unit='m')}})
    assert p.canvas.ax.get_xlim()[0] == 20


def test_kwarg_crop_1d_min_conversion():
    da = data_array(ndim=1)
    p = pp.plot(da, crop={'xx': {'min': sc.scalar(200, unit='cm')}})
    assert p.canvas.ax.get_xlim()[0] == 2


def test_kwarg_crop_1d_with_no_unit():
    da = data_array(ndim=1)
    p = pp.plot(da, crop={'xx': {'min': 20}})
    assert p.canvas.ax.get_xlim()[0] == 20
    p = pp.plot(da, crop={'xx': {'min': 20.5}})
    assert p.canvas.ax.get_xlim()[0] == 20.5


def test_kwarg_crop_2d():
    da = data_array(ndim=2)
    p = pp.plot(
        da,
        crop={
            'xx': {'min': sc.scalar(20, unit='m')},
            'yy': {'min': sc.scalar(10, unit='m'), 'max': sc.scalar(4000, unit='cm')},
        },
    )
    assert p.canvas.ax.get_xlim()[0] == 20
    assert np.array_equal(p.canvas.ax.get_ylim(), [10, 40])


def test_kwarg_for_two_lines():
    ds = dataset(ndim=1)
    p = pp.plot(ds, color='r')
    assert _get_line(p, 0).get_color() == 'r'
    assert _get_line(p, 1).get_color() == 'r'


def test_kwarg_as_dict():
    ds = dataset(ndim=1)
    p = pp.plot(ds, color={'a': 'red', 'b': 'black'})
    assert _get_line(p, 0).get_color() == 'red'
    assert _get_line(p, 1).get_color() == 'black'
    da = data_array(ndim=1)
    p = pp.plot({'a': da, 'b': 0.2 * da}, color={'a': 'red', 'b': 'black'})
    assert _get_line(p, 0).get_color() == 'red'
    assert _get_line(p, 1).get_color() == 'black'


def test_raises_ValueError_when_given_binned_data():
    da = sc.data.table_xyz(100).bin(x=10, y=20)
    with pytest.raises(ValueError, match='Cannot plot binned data'):
        pp.plot(da)


def test_raises_ValueError_when_given_unsupported_data_type():
    a = data_array(ndim=1)
    b = a * 2.0
    c = a * 3.0
    d = a * 4.0
    nested_dict = {'group1': {'a': a, 'b': b}, 'group2': {'c': c, 'd': d}}
    with pytest.raises(ValueError, match='Cannot convert input of type'):
        pp.plot(nested_dict)


def test_use_non_dimension_coords():
    da = data_array(ndim=2, binedges=True)
    da.coords['xx2'] = 7.5 * da.coords['xx']
    da.coords['yy2'] = 3.3 * da.coords['yy']
    p = pp.plot(da, coords=['xx2', 'yy2'])
    assert p._fig.dims['x'] == 'xx2'
    assert p._fig.dims['y'] == 'yy2'
    assert p.canvas._xmax == 7.5 * da.coords['xx'].max().value
    assert p.canvas._ymax == 3.3 * da.coords['yy'].max().value


def test_use_non_dimension_coords_dataset():
    ds = dataset(ndim=1)
    ds.coords['xx2'] = 6.6 * ds.coords['xx']
    p = pp.plot(ds, coords=['xx2'])
    assert p._fig.dims['x'] == 'xx2'
    assert p.canvas._xmax > 6.6 * ds.coords['xx'].max().value


@pytest.mark.parametrize('ext', ['jpg', 'png', 'pdf', 'svg'])
def test_save_to_disk_1d(ext):
    da = data_array(ndim=1)
    fig = pp.plot(da)
    with tempfile.TemporaryDirectory() as path:
        fname = os.path.join(path, f'plopp_fig1d.{ext}')
        fig.save(filename=fname)
        assert os.path.isfile(fname)


@pytest.mark.parametrize('ext', ['jpg', 'png', 'pdf', 'svg'])
def test_save_to_disk_2d(ext):
    da = data_array(ndim=2)
    fig = pp.plot(da)
    with tempfile.TemporaryDirectory() as path:
        fname = os.path.join(path, f'plopp_fig2d.{ext}')
        fig.save(filename=fname)
        assert os.path.isfile(fname)


def test_save_to_disk_with_bad_extension_raises():
    da = data_array(ndim=2)
    fig = pp.plot(da)
    with pytest.raises(ValueError):
        fig.save(filename='plopp_fig2d.txt')


def test_plot_raises_with_multiple_2d_inputs():
    a = data_array(ndim=2)
    b = 3.3 * a
    with pytest.raises(
        ValueError, match='The plot function can only plot a single 2d data entry'
    ):
        pp.plot({'a': a, 'b': b})


def test_plot_xarray_data_array_1d():
    import xarray as xr

    N = 50
    data = np.random.random(N)
    time = np.arange(float(N))
    da = xr.DataArray(data, coords={'time': time}, dims=['time'])
    p = pp.plot(da)
    assert p._fig.dims['x'] == 'time'
    assert p.canvas.xunit == 'dimensionless'
    assert p.canvas.yunit == 'dimensionless'


def test_plot_xarray_data_array_2d():
    import xarray as xr

    N = 50
    M = 40
    data = np.random.random([M, N])
    time = np.arange(float(N))
    space = np.arange(float(M))
    da = xr.DataArray(
        data, coords={'space': space, 'time': time}, dims=['space', 'time']
    )
    p = pp.plot(da)
    assert p._fig.dims['x'] == 'time'
    assert p._fig.dims['y'] == 'space'
    assert p.canvas.xunit == 'dimensionless'
    assert p.canvas.yunit == 'dimensionless'


def test_plot_xarray_dataset():
    import xarray as xr

    N = 50
    temp = 15 + 8 * np.random.random(N)
    precip = 10 * np.random.random(N)
    ds = xr.Dataset(
        {
            "temperature": (["time"], temp),
            "precipitation": (["time"], precip),
        },
        coords={"time": np.arange(50)},
    )
    p = pp.plot(ds)
    assert p._fig.dims['x'] == 'time'
    assert p.canvas.xunit == 'dimensionless'
    assert p.canvas.yunit == 'dimensionless'
    assert len(p._fig.artists) == 2


def test_plot_pandas_series():
    import pandas as pd

    s = pd.Series(np.arange(100.0), name='MyDataSeries')
    p = pp.plot(s)
    assert p._fig.dims['x'] == 'row'
    assert p.canvas.xunit == 'dimensionless'
    assert p.canvas.yunit == 'dimensionless'
    assert list(p._fig.artists.values())[0].label == 'MyDataSeries'


def test_plot_pandas_dataframe():
    import pandas as pd

    df = pd.DataFrame(
        {
            'A': np.arange(50.0),
            'B': 1.5 * np.arange(50),
            'C': np.random.random(50),
            'D': np.random.normal(size=50),
        }
    )
    p = pp.plot(df)
    assert p._fig.dims['x'] == 'row'
    assert p.canvas.xunit == 'dimensionless'
    assert p.canvas.yunit == 'dimensionless'
    assert len(p._fig.artists) == 4
