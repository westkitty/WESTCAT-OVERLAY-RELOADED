"""Animation utilities for the WESTCAT cat."""

from .cluster_sync import (
    Animator,
    ClusterSpec,
    FrameInfo,
    STATE_TO_CLUSTER,
    default_cluster_config,
    load_clusters,
    try_load_or_default,
)

__all__ = [
    "Animator",
    "ClusterSpec",
    "FrameInfo",
    "STATE_TO_CLUSTER",
    "default_cluster_config",
    "load_clusters",
    "try_load_or_default",
]
