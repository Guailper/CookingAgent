"""Shared compute device selection helpers."""


def resolve_compute_device() -> str:
    """Return `cuda` when PyTorch can use CUDA, otherwise return `cpu`."""

    try:
        import torch
    except ImportError:
        return "cpu"

    return "cuda" if torch.cuda.is_available() else "cpu"

