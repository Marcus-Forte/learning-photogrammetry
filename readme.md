# learning-photogrammetry

This repository contains practical examples of how to use [colmap](https://colmap.github.io/), an open-source general general-purpose Structure-from-Motion (SfM) and Multi-View Stereo (MVS) pipeline with docker.

## Extracting features

Attention to the GPU flag. If you have a GPU, set it to 1, otherwise set it to 0.

```bash
docker run --rm -v .:/data colmap/colmap colmap feature_extractor --database_path /data/database.db --image_path /data/imgs/ --FeatureExtraction.use_gpu 0
``` 

