from app.anim.cluster_sync import Animator, ClusterSpec


def _make_anim(loop: bool = True) -> Animator:
    frames = [f"frame_{i}.png" for i in range(6)]
    clusters = {"test": ClusterSpec("test", frames, fps=12, loop=loop)}
    return Animator(clusters)


def test_looping_cluster_wraps() -> None:
    anim = _make_anim(loop=True)
    anim.set_cluster("test", now_ms=0)
    info = anim.tick(now_ms=500)
    assert info is not None
    assert 0 <= info.frame_idx < 6


def test_one_shot_holds_last_frame() -> None:
    frames = [f"snap_{i}.png" for i in range(4)]
    clusters = {"oneshot": ClusterSpec("oneshot", frames, fps=8, loop=False)}
    anim = Animator(clusters)
    anim.set_cluster("oneshot", now_ms=0)
    info = anim.tick(now_ms=10_000)
    assert info is not None
    assert info.frame_idx == len(frames) - 1
