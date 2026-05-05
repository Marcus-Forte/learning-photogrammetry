import argparse
from pathlib import Path
import signal

import open3d as o3d


should_exit = False


def handle_sigint(signum: int, frame: object | None) -> None:
    del signum, frame
    global should_exit
    should_exit = True

def main() -> None:
    parser = argparse.ArgumentParser(description="Open a PLY file using Open3D")
    parser.add_argument("--ply", type=Path, help="Path to the PLY file", required=True)
    parser.add_argument(
        "--point-size",
        type=float,
        default=3.0,
        help="Point size used by the Open3D visualizer",
    )
    parser.add_argument(
        "--voxel-size",
        type=float,
        help="Optional voxel size for point-cloud subsampling before visualization",
    )
    args = parser.parse_args()

    if not args.ply.is_file():
        print(f"Error: File '{args.ply}' does not exist.")
        return

    if args.voxel_size is not None and args.voxel_size <= 0:
        print("Error: --voxel-size must be greater than 0.")
        return

    point_cloud = o3d.io.read_point_cloud(str(args.ply))

    if args.voxel_size is not None:
        point_cloud = point_cloud.voxel_down_sample(voxel_size=args.voxel_size)

    origin_axis = o3d.geometry.TriangleMesh.create_coordinate_frame(size=1.0, origin=[0.0, 0.0, 0.0])

    visualizer = o3d.visualization.Visualizer()
    visualizer.create_window(window_name=f"Open PLY - {args.ply.name}", width=1280, height=800)
    visualizer.add_geometry(point_cloud)
    visualizer.add_geometry(origin_axis)

    render_option = visualizer.get_render_option()
    render_option.point_size = args.point_size

    previous_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handle_sigint)

    try:
        while not should_exit and visualizer.poll_events():
            visualizer.update_renderer()
    finally:
        signal.signal(signal.SIGINT, previous_handler)
        visualizer.destroy_window()


if __name__ == "__main__":
    main()