# learning-photogrammetry

This repository contains practical examples of how to use [colmap](https://colmap.github.io/), an open-source general general-purpose Structure-from-Motion (SfM) and Multi-View Stereo (MVS) pipeline with docker.

## Extracting features

Attention to the GPU flag. If you have a GPU, set it to 1, otherwise set it to 0.

```bash
docker run --init --rm --gpus all -v .:/data colmap/colmap colmap feature_extractor --database_path /data/database.db --image_path /data/imgs/
``` 

## Matching features

```bash
docker run --init --rm --gpus all -v .:/data colmap/colmap colmap exhaustive_matcher --database_path /data/database.db
```

```bash
docker run --init --rm --gpus all -v .:/data colmap/colmap colmap sequential_matcher --database_path /data/database.db
```

## Sparse reconstruction

```bash
mkdir -p sparse
docker run --init --rm --gpus all -v .:/data colmap/colmap colmap mapper --database_path /data/database.db --image_path /data/imgs/ --output_path /data/sparse/
```

## Sparse PLY conversion (Not needed for further steps) 

```bash
docker run --init --rm --gpus all -v .:/data colmap/colmap colmap model_converter --input_path /data/sparse/0 --output_path /data/sparse/0/sparse.ply --output_type PLY
```

## Image undistortion

```bash
docker run --init --rm --gpus all -v .:/data colmap/colmap colmap image_undistorter --image_path /data/imgs --input_path /data/sparse/0 --output_path /data/dense --output_type COLMAP --max_image_size 8192
```

## Dense reconstruction (+GPU)

```bash
docker run --init --rm --gpus all -v .:/data colmap/colmap colmap patch_match_stereo --workspace_path /data/dense --workspace_format COLMAP --PatchMatchStereo.geom_consistency true
```

```bash
docker run --init --rm --gpus all -v .:/data colmap/colmap colmap stereo_fusion --workspace_path /data/dense --workspace_format COLMAP --input_type geometric --output_path /data/dense/fused.ply
``` 

## Visualization

```bash
uv run open_ply.py --ply <path_to_ply>
```