# learning-photogrammetry

This repository contains practical examples of how to use [colmap](https://colmap.github.io/), an open-source general general-purpose Structure-from-Motion (SfM) and Multi-View Stereo (MVS) pipeline with docker.

## Extracting features

Attention to the GPU flag. If you have a GPU, set it to 1, otherwise set it to 0.

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap feature_extractor --database_path /data/database.db --image_path /data/imgs/
``` 

## Matching features

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap exhaustive_matcher --database_path /data/database.db
```

## Sparse reconstruction

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap mapper --database_path /data/database.db --image_path /data/imgs/ --output_path /data/sparse/
```

## Image undistortion

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap image_undistorter --image_path /data/imgs --input_path /data/sparse/0 --output_path /data/dense --output_type COLMAP --max_image_size 2000
```

## Dense reconstruction

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap patch_match_stereo --workspace_path /data/dense --workspace_format COLMAP --PatchMatchStereo.geom_consistency true
```

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap stereo_fusion --workspace_path /data/dense --workspace_format COLMAP --input_type geometric --output_path /data/dense/fused.ply
``` 

