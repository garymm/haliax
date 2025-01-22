from typing import Callable

import jax.numpy as jnp
import pytest
from jax.random import PRNGKey

import haliax as hax
from haliax import Axis, NamedArray


def test_trace():
    Width = Axis("Width", 3)
    Depth = Axis("Depth", 4)
    named1 = hax.random.uniform(PRNGKey(0), (Width, Depth))
    trace1 = hax.trace(named1, Width, Depth)
    assert jnp.all(jnp.isclose(trace1.array, jnp.trace(named1.array)))
    assert len(trace1.axes) == 0

    trace1 = hax.trace(named1, "Width", "Depth")
    assert jnp.all(jnp.isclose(trace1.array, jnp.trace(named1.array)))
    assert len(trace1.axes) == 0

    Height = Axis("Height", 10)
    named2 = hax.random.uniform(PRNGKey(0), (Height, Width, Depth))
    trace2 = hax.trace(named2, Width, Depth)
    assert jnp.all(jnp.isclose(trace2.array, jnp.trace(named2.array, axis1=1, axis2=2)))
    assert trace2.axes == (Height,)

    trace2 = hax.trace(named2, "Width", "Depth")
    assert jnp.all(jnp.isclose(trace2.array, jnp.trace(named2.array, axis1=1, axis2=2)))
    assert trace2.axes == (Height,)


def test_add():
    Height = Axis("Height", 10)
    Width = Axis("Width", 3)
    Depth = Axis("Depth", 4)

    named1 = hax.random.uniform(PRNGKey(0), (Height, Width, Depth))
    named2 = hax.random.uniform(PRNGKey(1), (Height, Width, Depth))

    named3 = named1 + named2
    assert jnp.all(jnp.isclose(named3.array, named1.array + named2.array))

    named2_reorder = named2.rearrange((Width, Height, Depth))
    named4 = named1 + named2_reorder
    named4 = named4.rearrange((Height, Width, Depth))
    assert jnp.all(jnp.isclose(named4.array, named1.array + named2.array))


def test_add_broadcasting():
    Height = Axis("Height", 10)
    Width = Axis("Width", 3)
    Depth = Axis("Depth", 4)

    named1 = hax.random.uniform(PRNGKey(0), (Height, Width, Depth))
    named2 = hax.random.uniform(PRNGKey(1), (Width, Depth))

    named3 = named1 + named2
    assert jnp.all(jnp.isclose(named3.array, named1.array + named2.array))

    named2_reorder = named2.rearrange((Depth, Width))
    named4 = named1 + named2_reorder
    named4 = named4.rearrange((Height, Width, Depth))

    assert jnp.all(jnp.isclose(named4.array, named1.array + named2.array))

    # now for the broadcasting we don't like
    named5 = hax.random.uniform(PRNGKey(1), (Height, Depth))
    named6 = hax.random.uniform(PRNGKey(2), (Width, Depth))

    with pytest.raises(ValueError):
        _ = named5 + named6


def test_add_scalar():
    Height = Axis("Height", 10)
    Width = Axis("Width", 3)
    Depth = Axis("Depth", 4)

    named1 = hax.random.uniform(PRNGKey(0), (Height, Width, Depth))
    named2 = named1 + 1.0
    assert jnp.all(jnp.isclose(named2.array, named1.array + 1.0))

    named3 = 1.0 + named1
    assert jnp.all(jnp.isclose(named3.array, named1.array + 1.0))


def test_add_no_overlap():
    Height = Axis("Height", 10)
    Width = Axis("Width", 3)
    Depth = Axis("Depth", 4)

    named1: NamedArray = hax.random.uniform(PRNGKey(0), (Height))
    named2 = hax.random.uniform(PRNGKey(1), (Width, Depth))

    with pytest.raises(ValueError):
        _ = named1 + named2

    named3 = named1.broadcast_to((Height, Width, Depth)) + named2

    assert jnp.all(
        jnp.isclose(named3.array, named1.array.reshape((-1, 1, 1)) + named2.array.reshape((1,) + named2.array.shape))
    )


# TODO: tests for other ops:


@pytest.mark.parametrize("use_jit", [False, True])
def test_where(use_jit):
    Height = Axis("Height", 10)
    Width = Axis("Width", 3)
    Depth = Axis("Depth", 4)

    hax_where: Callable = hax.where
    if use_jit:
        hax_where = hax.named_jit(hax_where)

    named1 = hax.random.uniform(PRNGKey(0), (Height, Width, Depth))
    named2 = hax.random.uniform(PRNGKey(1), (Height, Width, Depth))

    hax_where(0.0, named1, 0.0)

    named3 = hax_where(named1 > named2, named1, named2)

    assert jnp.all(jnp.isclose(named3.array, jnp.where(named1.array > named2.array, named1.array, named2.array)))

    named2_reorder = named2.rearrange((Width, Height, Depth))
    named4 = hax_where(named1 > named2_reorder, named1, named2_reorder)
    named4 = named4.rearrange((Height, Width, Depth))
    assert jnp.all(jnp.isclose(named4.array, jnp.where(named1.array > named2.array, named1.array, named2.array)))

    # now some broadcasting
    named5 = hax.random.uniform(PRNGKey(1), (Height, Width))
    named6 = hax.random.uniform(PRNGKey(2), Width)

    named7 = hax_where(named5 > named6, named5, named6)
    named7 = named7.rearrange((Height, Width))
    assert jnp.all(jnp.isclose(named7.array, jnp.where(named5.array > named6.array, named5.array, named6.array)))

    # now for the broadcasting we don't like
    named5 = hax.random.uniform(PRNGKey(1), (Height, Depth))
    named6 = hax.random.uniform(PRNGKey(2), (Width, Depth))

    with pytest.raises(ValueError):
        _ = hax_where(named5 > named6, named5, named6)

    # now single argument mode
    Volume = hax.Axis("Volume", Height.size * Width.size * Depth.size)
    named7 = hax.random.uniform(PRNGKey(0), (Height, Width, Depth))
    named8, named9, named10 = hax_where(named7 > 0.5, fill_value=-1, new_axis=Volume)
    assert jnp.all((named7[{"Height": named8, "Width": named9, "Depth": named10}] > 0.5).array)


def test_clip():
    Height = Axis("Height", 10)
    Width = Axis("Width", 3)
    Depth = Axis("Depth", 4)

    named1 = hax.random.uniform(PRNGKey(0), (Height, Width, Depth))
    named2 = hax.clip(named1, 0.3, 0.7)
    assert jnp.all(jnp.isclose(named2.array, jnp.clip(named1.array, 0.3, 0.7)))

    named2_reorder = named2.rearrange((Width, Height, Depth))
    named3 = hax.clip(named2_reorder, 0.3, 0.7)
    named3 = named3.rearrange((Height, Width, Depth))
    assert jnp.all(jnp.isclose(named3.array, jnp.clip(named2.array, 0.3, 0.7)))

    # now some interesting broadcasting
    lower = hax.full((Height, Width), 0.3)
    upper = hax.full((Width, Depth), 0.7)
    named4 = hax.clip(named1, lower, upper)
    named4 = named4.rearrange((Height, Width, Depth))

    assert jnp.all(
        jnp.isclose(
            named4.array,
            jnp.clip(
                named1.array,
                lower.array.reshape((Height.size, Width.size, 1)),
                upper.array.reshape((1, Width.size, Depth.size)),
            ),
        )
    )


def test_tril_triu():
    Height = Axis("Height", 10)
    Width = Axis("Width", 3)
    Depth = Axis("Depth", 4)

    for hax_fn, jnp_fn in [(hax.tril, jnp.tril), (hax.triu, jnp.triu)]:
        named1 = hax.random.uniform(PRNGKey(0), (Height, Width, Depth))
        named2 = hax_fn(named1, Width, Depth)
        assert jnp.all(jnp.isclose(named2.array, jnp_fn(named1.array)))

        named3 = hax_fn(named1, Width, Depth, k=1)
        assert jnp.all(jnp.isclose(named3.array, jnp_fn(named1.array, k=1)))

        named4 = hax_fn(named1, Width, Depth, k=-1)
        assert jnp.all(jnp.isclose(named4.array, jnp_fn(named1.array, k=-1)))

        named5 = hax_fn(named1, Height, Depth)
        expected5 = jnp_fn(named1.array.transpose([1, 0, 2]))
        assert jnp.all(jnp.isclose(named5.array, expected5))


def test_mean_respects_where():
    Height = Axis("Height", 10)
    Width = Axis("Width", 3)

    named1 = hax.random.uniform(PRNGKey(0), (Height, Width))
    where = hax.random.uniform(PRNGKey(1), (Height, Width)) > 0.5

    assert not jnp.all(jnp.isclose(hax.mean(named1), hax.mean(named1, where=where)))
    assert jnp.all(jnp.isclose(hax.mean(named1, where=where), jnp.mean(named1.array, where=where.array)))

    # check broadcasting
    where = hax.random.uniform(PRNGKey(2), (Height,)) > 0.5
    assert not jnp.all(jnp.isclose(hax.mean(named1), hax.mean(named1, where=where)))
    assert jnp.all(
        jnp.isclose(hax.mean(named1, where=where), jnp.mean(named1.array, where=where.array.reshape((-1, 1))))
    )


def test_reductions_produce_scalar_named_arrays_when_None_axis():
    Height = Axis("Height", 10)
    Width = Axis("Width", 3)

    named1 = hax.random.uniform(PRNGKey(0), (Height, Width))

    assert isinstance(hax.mean(named1, axis=None), NamedArray)

    # But if we specify axes, we always get a NamedArray, even if it's a scalar
    assert isinstance(hax.mean(named1, axis=("Height", "Width")), NamedArray)
    assert hax.mean(named1, axis=("Height", "Width")).axes == ()


def test_unique():
    # named version of this test:
    # >>> M = jnp.array([[1, 2],
    # ...                [2, 3],
    # ...                [1, 2]])
    # >>> jnp.unique(M)
    # Array([1, 2, 3], dtype=int32)

    Height = Axis("Height", 3)
    Width = Axis("Width", 2)

    named1 = hax.named([[1, 2], [2, 3], [1, 2]], (Height, Width))

    U = Axis("U", 3)

    named2 = hax.unique(named1, U)

    assert jnp.all(jnp.equal(named2.array, jnp.array([1, 2, 3])))

    #     If you pass an ``axis`` keyword, you can find unique *slices* of the array along
    #     that axis:
    #
    #     >>> jnp.unique(M, axis=0)
    #     Array([[1, 2],
    #            [2, 3]], dtype=int32)

    U2 = Axis("U2", 2)
    named3 = hax.unique(named1, U2, axis=Height)
    assert jnp.all(jnp.equal(named3.array, jnp.array([[1, 2], [2, 3]])))

    #     >>> x = jnp.array([3, 4, 1, 3, 1])
    #     >>> values, indices = jnp.unique(x, return_index=True)
    #     >>> print(values)
    #     [1 3 4]
    #     >>> print(indices)
    #     [2 0 1]
    #     >>> jnp.all(values == x[indices])
    #     Array(True, dtype=bool)

    x = hax.named([3, 4, 1, 3, 1], ("Height",))
    U3 = Axis("U3", 3)
    values, indices = hax.unique(x, U3, return_index=True)

    assert jnp.all(jnp.equal(values.array, jnp.array([1, 3, 4])))
    assert jnp.all(jnp.equal(indices.array, jnp.array([2, 0, 1])))

    assert jnp.all(jnp.equal(values.array, x[{"Height": indices}].array))

    #   If you set ``return_inverse=True``, then ``unique`` returns the indices within the
    #     unique values for every entry in the input array:
    #
    #     >>> x = jnp.array([3, 4, 1, 3, 1])
    #     >>> values, inverse = jnp.unique(x, return_inverse=True)
    #     >>> print(values)
    #     [1 3 4]
    #     >>> print(inverse)
    #     [1 2 0 1 0]
    #     >>> jnp.all(values[inverse] == x)
    #     Array(True, dtype=bool)

    values, inverse = hax.unique(x, U3, return_inverse=True)

    assert jnp.all(jnp.equal(values.array, jnp.array([1, 3, 4])))
    assert jnp.all(jnp.equal(inverse.array, jnp.array([1, 2, 0, 1, 0])))

    #     In multiple dimensions, the input can be reconstructed using
    #     :func:`jax.numpy.take`:
    #
    #     >>> values, inverse = jnp.unique(M, axis=0, return_inverse=True)
    #     >>> jnp.all(jnp.take(values, inverse, axis=0) == M)
    #     Array(True, dtype=bool)
    #

    values, inverse = hax.unique(named1, U3, axis=Height, return_inverse=True)

    assert jnp.all((values[{"U3": inverse}] == named1).array)

    #     **Returning counts**
    #  If you set ``return_counts=True``, then ``unique`` returns the number of occurrences
    #     within the input for every unique value:
    #
    #     >>> x = jnp.array([3, 4, 1, 3, 1])
    #     >>> values, counts = jnp.unique(x, return_counts=True)
    #     >>> print(values)
    #     [1 3 4]
    #     >>> print(counts)
    #     [2 2 1]
    #
    #     For multi-dimensional arrays, this also returns a 1D array of counts
    #     indicating number of occurrences along the specified axis:
    #
    #     >>> values, counts = jnp.unique(M, axis=0, return_counts=True)
    #     >>> print(values)
    #     [[1 2]
    #      [2 3]]
    #     >>> print(counts)
    #     [2 1]

    values, counts = hax.unique(x, U3, return_counts=True)

    assert jnp.all(jnp.equal(values.array, jnp.array([1, 3, 4])))
    assert jnp.all(jnp.equal(counts.array, jnp.array([2, 2, 1])))

    values, counts = hax.unique(named1, U2, axis=Height, return_counts=True)

    assert jnp.all(jnp.equal(values.array, jnp.array([[1, 2], [2, 3]])))
    assert jnp.all(jnp.equal(counts.array, jnp.array([2, 1])))
