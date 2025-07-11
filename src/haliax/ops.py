import typing
from typing import Mapping, Optional, Union

import jax
import jax.numpy as jnp

from .axis import Axis, AxisSelector, axis_name
from .core import NamedArray, NamedOrNumeric, broadcast_arrays, broadcast_arrays_and_return_axes, named
from .jax_utils import is_scalarish


def trace(array: NamedArray, axis1: AxisSelector, axis2: AxisSelector, offset=0, dtype=None) -> NamedArray:
    """Compute the trace of an array along two named axes."""
    a1_index = array.axis_indices(axis1)
    a2_index = array.axis_indices(axis2)

    if a1_index is None:
        raise ValueError(f"Axis {axis1} not found in array. Available axes: {array.axes}")
    if a2_index is None:
        raise ValueError(f"Axis {axis2} not found in array. Available axes: {array.axes}")

    if a1_index == a2_index:
        raise ValueError(f"Cannot trace along the same axis. Got {axis1} and {axis2}")

    inner = jnp.trace(array.array, offset=offset, axis1=a1_index, axis2=a2_index, dtype=dtype)
    # remove the two indices
    axes = tuple(a for i, a in enumerate(array.axes) if i not in (a1_index, a2_index))
    return NamedArray(inner, axes)


@typing.overload
def where(
    condition: NamedOrNumeric | bool,
    x: NamedOrNumeric,
    y: NamedOrNumeric,
) -> NamedArray:
    ...


@typing.overload
def where(
    condition: NamedArray,
    *,
    fill_value: int,
    new_axis: Axis,
) -> tuple[NamedArray, ...]:
    ...


def where(
    condition: Union[NamedOrNumeric, bool],
    x: Optional[NamedOrNumeric] = None,
    y: Optional[NamedOrNumeric] = None,
    fill_value: Optional[int] = None,
    new_axis: Optional[Axis] = None,
) -> NamedArray | tuple[NamedArray, ...]:
    """Like jnp.where, but with named axes."""

    if (x is None) != (y is None):
        raise ValueError("Must either specify both x and y, or neither")

    # one argument form
    if (x is None) and (y is None):
        if not isinstance(condition, NamedArray):
            raise ValueError(f"condition {condition} must be a NamedArray in single argument mode")
        if fill_value is None or new_axis is None:
            raise ValueError("Must specify both fill_value and new_axis")
        return tuple(
            NamedArray(idx, (new_axis,))
            for idx in jnp.where(condition.array, size=new_axis.size, fill_value=fill_value)
        )

    # if x or y is a NamedArray, the other must be as well. wrap as needed for scalars

    if is_scalarish(condition):
        if x is None or y is None:
            raise ValueError("Must specify x and y when condition is a scalar")

        if isinstance(x, NamedArray) and not isinstance(y, NamedArray):
            if not is_scalarish(y):
                raise ValueError("y must be a NamedArray or scalar if x is a NamedArray")
            y = named(y, ())
        elif isinstance(y, NamedArray) and not isinstance(x, NamedArray):
            if not is_scalarish(x):
                raise ValueError("x must be a NamedArray or scalar if y is a NamedArray")
            x = named(x, ())
        x, y = broadcast_arrays(x, y)
        if isinstance(condition, NamedArray):
            condition = condition.scalar()
        return jax.lax.cond(condition, lambda _: x, lambda _: y, None)

    condition, x, y = broadcast_arrays(condition, x, y)  # type: ignore

    assert isinstance(condition, NamedArray)

    def _array_if_named(x):
        if isinstance(x, NamedArray):
            return x.array
        return x

    raw = jnp.where(condition.array, _array_if_named(x), _array_if_named(y))
    return NamedArray(raw, condition.axes)


def clip(array: NamedOrNumeric, a_min: NamedOrNumeric, a_max: NamedOrNumeric) -> NamedArray:
    """Like jnp.clip, but with named axes. This version currently only accepts the three argument form."""
    (array, a_min, a_max), axes = broadcast_arrays_and_return_axes(array, a_min, a_max)
    array = raw_array_or_scalar(array)
    a_min = raw_array_or_scalar(a_min)
    a_max = raw_array_or_scalar(a_max)

    return NamedArray(jnp.clip(array, a_min, a_max), axes)


def tril(array: NamedArray, axis1: Axis, axis2: Axis, k=0) -> NamedArray:
    """Compute the lower triangular part of an array along two named axes."""
    array = array.rearrange((..., axis1, axis2))

    inner = jnp.tril(array.array, k=k)
    return NamedArray(inner, array.axes)


def triu(array: NamedArray, axis1: Axis, axis2: Axis, k=0) -> NamedArray:
    """Compute the upper triangular part of an array along two named axes."""
    array = array.rearrange((..., axis1, axis2))

    inner = jnp.triu(array.array, k=k)
    return NamedArray(inner, array.axes)


def isclose(a: NamedArray, b: NamedArray, rtol=1e-05, atol=1e-08, equal_nan=False) -> NamedArray:
    """Returns a boolean array where two arrays are element-wise equal within a tolerance."""
    a, b = broadcast_arrays(a, b)
    # TODO: numpy supports an array atol and rtol, but we don't yet
    return NamedArray(jnp.isclose(a.array, b.array, rtol=rtol, atol=atol, equal_nan=equal_nan), a.axes)


def pad_left(array: NamedArray, axis: Axis, new_axis: Axis, value=0) -> NamedArray:
    """Pad an array along named axes."""
    amount_to_pad_to = new_axis.size - axis.size
    if amount_to_pad_to < 0:
        raise ValueError(f"Cannot pad {axis} to {new_axis}")

    idx = array.axis_indices(axis)

    padding = [(0, 0)] * array.ndim
    if idx is None:
        raise ValueError(f"Axis {axis} not found in array. Available axes: {array.axes}")
    padding[idx] = (amount_to_pad_to, 0)

    padded = jnp.pad(array.array, padding, constant_values=value)
    return NamedArray(padded, array.axes[:idx] + (new_axis,) + array.axes[idx + 1 :])


def pad(
    array: NamedArray,
    pad_width: Mapping[AxisSelector, tuple[int, int]],
    *,
    mode: str = "constant",
    constant_values: NamedOrNumeric = 0,
    **kwargs,
) -> NamedArray:
    """Version of ``jax.numpy.pad`` that works with ``NamedArray``.

    ``pad_width`` should be a mapping from axis (or axis name) to a ``(before, after)``
    tuple specifying how much padding to add on each side of that axis. Any axis
    not present in ``pad_width`` will not be padded.
    """

    padding = []
    new_axes = []
    for ax in array.axes:
        left_right = pad_width.get(ax)
        if left_right is None:
            left_right = pad_width.get(axis_name(ax))  # type: ignore[arg-type]
        if left_right is None:
            left_right = (0, 0)
        left, right = left_right
        padding.append((left, right))
        new_axes.append(ax.resize(ax.size + left + right))

    result = jnp.pad(
        array.array,
        padding,
        mode=mode,
        constant_values=raw_array_or_scalar(constant_values),
        **kwargs,
    )

    return NamedArray(result, tuple(new_axes))


def raw_array_or_scalar(x: NamedOrNumeric):
    if isinstance(x, NamedArray):
        return x.array
    return x


__all__ = ["trace", "where", "tril", "triu", "isclose", "pad_left", "pad", "clip"]
