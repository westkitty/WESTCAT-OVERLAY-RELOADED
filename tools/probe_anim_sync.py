from __future__ import annotations

import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.anim.cluster_sync import Animator, try_load_or_default


def main() -> None:
    clusters = try_load_or_default("assets/cat/clusters.json")
    anim = Animator(clusters)
    os.makedirs("artifacts/sync", exist_ok=True)
    output_path = os.path.join("artifacts", "sync", "probe.tsv")
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("cluster\tms\tp\tframe_idx\tframe_path\n")
        for name in clusters:
            anim.set_cluster(name)
            start = int(time.time() * 1000)
            end = start + 2000
            while int(time.time() * 1000) < end:
                frame = anim.tick()
                if frame:
                    fh.write(
                        f"{frame.cluster}\t{frame.ms_in}\t{frame.p:.4f}\t{frame.frame_idx}\t{frame.frame_path}\n"
                    )
                time.sleep(0.03)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
