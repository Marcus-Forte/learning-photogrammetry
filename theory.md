# Photogrammetry Theory and COLMAP Pipeline

This document explains the practical steps in a typical COLMAP workflow and the theory behind each step. The focus is on the standard pipeline used in this repository:

1. Feature extraction
2. Feature matching
3. Sparse reconstruction with Structure from Motion
4. Image undistortion
5. Dense stereo reconstruction
6. Depth map fusion
7. Optional meshing

The overall goal of photogrammetry is to recover 3D structure from multiple overlapping 2D images. COLMAP does this in two major phases:

- Sparse reconstruction: estimate camera poses and a sparse set of 3D points.
- Dense reconstruction: estimate depth for most visible pixels and fuse them into a dense point cloud.

## 1. Input Images and Capture Assumptions

Before any command is run, the image set itself determines how well the reconstruction can succeed.

### What matters in practice

- High overlap between neighboring images, typically 60% to 80% or more.
- Consistent exposure and limited motion blur.
- A scene with visible texture. Flat white walls or reflective surfaces are difficult.
- Camera motion that changes viewpoint, not only rotation in place.

### Theory

Photogrammetry relies on triangulation. A 3D point can only be estimated well if it is seen from at least two distinct viewpoints. If camera centers are nearly identical, the angle between viewing rays is too small and depth becomes unstable.

If a 3D point $X$ is observed by two cameras with centers $C_1$ and $C_2$, reconstruction quality depends strongly on the baseline $\|C_2 - C_1\|$ and the angle between the rays from the cameras to $X$.

Small baseline means high uncertainty in depth.

## 2. Feature Extraction

### Practical step

COLMAP first detects interest points in each image and computes a descriptor for each one. In many setups, this is SIFT-based.

Example command already used in this repository:

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap feature_extractor --database_path /data/database.db --image_path /data/imgs/
```

This stores detected keypoints and descriptors in `database.db`.

### Theory

The problem is to find image locations that are:

- repeatable across viewpoint and lighting changes
- distinctive enough to be matched later

#### Keypoints

A keypoint is a visually stable image location, such as a corner or blob. SIFT detects extrema in scale space, not just in the raw image.

The scale-space representation of an image $I(x, y)$ is built by convolving with a Gaussian:

$$
L(x, y, \sigma) = G(x, y, \sigma) * I(x, y)
$$

where $G$ is a Gaussian kernel with scale $\sigma$.

SIFT approximates scale-normalized blob detection using the Difference of Gaussians:

$$
D(x, y, \sigma) = L(x, y, k\sigma) - L(x, y, \sigma)
$$

Extrema of $D$ across space and scale become candidate keypoints.

#### Descriptors

Around each keypoint, COLMAP computes a descriptor that summarizes local gradient structure. In SIFT, local image gradients are accumulated into orientation histograms. This gives robustness to small viewpoint and illumination changes.

Conceptually, the descriptor is a vector:

$$
f_i \in \mathbb{R}^d
$$

where $d = 128$ for classic SIFT.

The descriptor should satisfy:

- descriptors from the same physical point are close in feature space
- descriptors from different points are far apart

## 3. Feature Matching

### Practical step

Once descriptors are available, the next step is to match features across image pairs.

For smaller image sets, COLMAP commonly uses exhaustive matching:

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap exhaustive_matcher --database_path /data/database.db
```

For larger or ordered datasets, alternatives such as sequential or vocabulary-tree matching are more efficient.

### Theory

Feature matching tries to identify which keypoint in image A corresponds to which keypoint in image B.

Given descriptors $f_i$ from one image and $g_j$ from another, a basic strategy is nearest-neighbor matching under Euclidean distance:

$$
j^* = \arg\min_j \|f_i - g_j\|_2
$$

But nearest neighbor alone is noisy, so robust pipelines use the ratio test. If $d_1$ and $d_2$ are the distances to the best and second-best matches, accept the match only if:

$$
\frac{d_1}{d_2} < \tau
$$

with a threshold $\tau$ often around $0.7$ to $0.8$.

This suppresses ambiguous matches.

### Geometric verification

Descriptor similarity is not enough. True correspondences must also satisfy epipolar geometry.

For a point $x$ in image 1 and corresponding point $x'$ in image 2, the fundamental matrix $F$ satisfies:

$$
x'^T F x = 0
$$

If camera intrinsics are known, normalized coordinates satisfy the essential matrix constraint:

$$
\tilde{x}'^T E \tilde{x} = 0
$$

where:

$$
E = [t]_\times R
$$

Here $R$ is the relative rotation and $t$ is the relative translation between cameras.

COLMAP uses robust estimators such as RANSAC to fit this geometry while rejecting outliers. That is critical: a few bad matches can derail later pose estimation.

## 4. Sparse Reconstruction: Structure from Motion

### Practical step

After verified matches exist, COLMAP estimates camera poses and triangulates a sparse 3D point cloud.

Typical command:

```bash
mkdir -p sparse
docker run --rm --gpus all -v .:/data colmap/colmap colmap mapper --database_path /data/database.db --image_path /data/imgs --output_path /data/sparse
```

This creates one or more sparse models in the `sparse/` directory.

### Theory

Structure from Motion jointly solves two unknowns:

- camera poses
- 3D scene points

This starts from image correspondences.

### Camera model

A 3D point $X = [X, Y, Z, 1]^T$ projects into an image point $x = [u, v, 1]^T$ through:

$$
x \sim K [R \mid t] X
$$

where:

- $K$ is the intrinsic calibration matrix
- $R, t$ are the camera extrinsics

A common form for $K$ is:

$$
K =
\begin{bmatrix}
f_x & 0 & c_x \\
0 & f_y & c_y \\
0 & 0 & 1
\end{bmatrix}
$$

### Relative pose estimation

From verified correspondences between two images, COLMAP estimates relative pose. If intrinsics are known or estimated, the essential matrix provides $R$ and the direction of $t$.

This initializes a reconstruction from a good image pair.

### Triangulation

Once two camera poses are known, matched image points define rays in 3D. The 3D point is estimated at the intersection of these rays, or more realistically the point minimizing reprojection error.

In ideal geometry, a point seen in two cameras satisfies:

$$
x_1 \sim P_1 X, \quad x_2 \sim P_2 X
$$

where $P_1$ and $P_2$ are projection matrices.

Because measurements are noisy, rays rarely intersect exactly. Triangulation computes the best approximate 3D point.

### Incremental SfM

COLMAP typically uses incremental SfM:

1. Start from an initial image pair with strong geometry.
2. Estimate their relative pose.
3. Triangulate initial 3D points.
4. Add one new image at a time.
5. Solve camera pose from 2D-3D correspondences.
6. Triangulate new points.
7. Re-optimize everything.

The pose of a new image is usually estimated with a Perspective-n-Point method. Given known 3D points and their 2D observations, solve for $R$ and $t$.

## 5. Bundle Adjustment

### Practical role

Bundle adjustment is the core refinement step inside sparse reconstruction. It is not always a separate command in the basic pipeline because COLMAP runs it internally during mapping.

### Theory

Bundle adjustment solves a large nonlinear least-squares problem. It refines camera parameters and 3D points to minimize reprojection error.

If $x_{ij}$ is the observed image location of 3D point $X_j$ in camera $i$, and $\pi(P_i, X_j)$ is the projected point under camera parameters $P_i$, the objective is:

$$
\min_{\{P_i\}, \{X_j\}} \sum_{i,j} \rho\left(\|x_{ij} - \pi(P_i, X_j)\|^2\right)
$$

where $\rho$ is often a robust loss to reduce sensitivity to outliers.

This is one of the main reasons photogrammetry works well: the entire reconstruction is globally refined rather than left as a chain of local estimates.

Typical solvers use variants of Levenberg-Marquardt and exploit the sparse block structure of the Jacobian.

## 6. Sparse Model Output and Scale Ambiguity

### What you get

The sparse model contains:

- estimated camera intrinsics
- camera poses
- a sparse set of 3D points

### Theory

Without external metric information, reconstruction from images alone is only determined up to a similarity transform:

- translation
- rotation
- global scale

That means the recovered geometry is correct in shape, but not necessarily in absolute units.

If metric scale is needed, you must add extra information, for example:

- known camera baseline
- surveyed control points
- GPS or IMU data
- object measurements

## 7. Image Undistortion

### Practical step

Before dense stereo, COLMAP often creates undistorted images and a workspace for dense reconstruction:

```bash
mkdir -p dense
docker run --rm --gpus all -v .:/data colmap/colmap colmap image_undistorter --image_path /data/imgs --input_path /data/sparse/0 --output_path /data/dense --output_type COLMAP
```

### Theory

Real lenses introduce distortion, especially radial distortion. A simple radial model is:

$$
x_d = x(1 + k_1 r^2 + k_2 r^4 + \cdots)
$$

$$
y_d = y(1 + k_1 r^2 + k_2 r^4 + \cdots)
$$

where $r^2 = x^2 + y^2$.

Undistortion remaps the images so that the pinhole projection model is a better approximation. Dense stereo assumes consistent projective geometry, so this preprocessing reduces systematic error.

## 8. Dense Stereo Reconstruction

### Practical step

COLMAP estimates a depth map for each image:

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap patch_match_stereo --workspace_path /data/dense --workspace_format COLMAP --PatchMatchStereo.geom_consistency true
```

### Theory

Sparse SfM only reconstructs points where stable features were matched. Dense stereo tries to recover depth for many more pixels.

For each reference image, the algorithm searches for the depth of each pixel by comparing local patches across neighboring images with known camera poses.

### Multi-view stereo intuition

If camera poses are known, a pixel in one image corresponds to a ray in 3D. Each possible depth along that ray gives a candidate 3D point. Reproject that candidate into other images and compare the local appearance. The depth that gives the best photometric agreement is preferred.

### Matching cost

A common similarity measure is normalized cross-correlation or a related photometric score over patches.

In simplified form, one seeks:

$$
d^* = \arg\min_d C(d)
$$

where $C(d)$ is the photometric inconsistency of the patch induced by depth $d$.

### PatchMatch idea

PatchMatch Stereo avoids brute-force search over all depths. Instead it propagates good depth hypotheses between neighboring pixels and refines them randomly. This is efficient because depth usually varies smoothly across local regions except at discontinuities.

### Geometric consistency

When geometric consistency is enabled, COLMAP checks that depth estimates agree across views. That means if a pixel in image A predicts a 3D point, the corresponding projection in image B should predict the same geometry when traced back.

This suppresses many false depth estimates on weakly textured or occluded regions.

## 9. Stereo Fusion

### Practical step

Each image now has a depth map. These are fused into a single dense point cloud:

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap stereo_fusion --workspace_path /data/dense --workspace_format COLMAP --input_type geometric --output_path /data/dense/fused.ply
```

### Theory

Depth maps are view-specific. Fusion combines them into a global 3D representation.

For each valid depth pixel, COLMAP back-projects the pixel into 3D. If a pixel at image coordinates $(u, v)$ has depth $z$, then in camera coordinates the point is approximately:

$$
X_c = z K^{-1}
\begin{bmatrix}
u \\
v \\
1
\end{bmatrix}
$$

Then transform from camera coordinates to world coordinates using the camera pose.

Fusion merges redundant observations and rejects inconsistent points. The result is a dense point cloud with much richer geometry than the sparse SfM output.

## 10. Optional Meshing

### Practical step

After dense fusion, you can convert the dense point cloud into a mesh.

Common options include Poisson meshing and Delaunay meshing.

Example commands:

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap poisson_mesher --input_path /data/dense/fused.ply --output_path /data/dense/meshed-poisson.ply
```

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap delaunay_mesher --input_path /data/dense --output_path /data/dense/meshed-delaunay.ply
```

### Theory

The dense point cloud is still just a set of samples. Meshing estimates a continuous surface.

#### Poisson meshing

Poisson reconstruction interprets oriented points as samples of an implicit surface and solves for a smooth function whose gradient matches the observed normals. The mesh is extracted as an iso-surface of that function.

This often gives smooth, watertight results, but it may oversmooth fine structure.

#### Delaunay meshing

Delaunay-based methods use visibility and geometric consistency to build a triangulated surface that better preserves discontinuities in some scenes.

## 11. Sources of Error

Photogrammetry is sensitive to several failure modes.

### Weak texture

If a region has little texture, descriptors are unstable and dense matching is ambiguous.

### Repeated patterns

Repeated windows, tiles, or fence patterns can create false correspondences.

### Specular and transparent surfaces

These violate the brightness constancy assumption. The same physical point does not appear consistently across views.

### Motion blur and rolling shutter

Blur destroys local detail. Rolling shutter breaks the assumption that one image corresponds to a single rigid camera pose.

### Small baseline

If viewpoints are too similar, triangulation becomes poorly conditioned.

### Poor calibration

If intrinsics or distortion are inaccurate, both sparse and dense reconstruction degrade.

## 12. Why the Pipeline Is Ordered This Way

The order is not arbitrary.

1. Feature extraction creates stable image evidence.
2. Feature matching links that evidence across views.
3. SfM estimates camera geometry and a sparse model.
4. Undistortion prepares images for dense geometry.
5. Dense stereo estimates per-image depth.
6. Fusion combines depth into a global dense cloud.
7. Meshing converts samples into a surface.

Each stage depends on the geometry estimated by the previous one. If matching is poor, SfM fails. If SfM camera poses are inaccurate, dense stereo will also be inaccurate.

## 13. Minimal Command Sequence for This Repository

Assuming feature extraction has already been completed, a practical next sequence is:

```bash
docker run --rm --gpus all -v .:/data colmap/colmap colmap exhaustive_matcher --database_path /data/database.db

mkdir -p sparse
docker run --rm --gpus all -v .:/data colmap/colmap colmap mapper --database_path /data/database.db --image_path /data/imgs --output_path /data/sparse

mkdir -p dense
docker run --rm --gpus all -v .:/data colmap/colmap colmap image_undistorter --image_path /data/imgs --input_path /data/sparse/0 --output_path /data/dense --output_type COLMAP

docker run --rm --gpus all -v .:/data colmap/colmap colmap patch_match_stereo --workspace_path /data/dense --workspace_format COLMAP --PatchMatchStereo.geom_consistency true

docker run --rm --gpus all -v .:/data colmap/colmap colmap stereo_fusion --workspace_path /data/dense --workspace_format COLMAP --input_type geometric --output_path /data/dense/fused.ply
```

If `sparse/0` does not exist, inspect the `sparse/` directory because COLMAP may output a different model index.

## 14. Mental Model Summary

The shortest useful mental model is:

- Features answer: what image points are distinctive?
- Matching answers: which points correspond across images?
- SfM answers: where were the cameras, and where are some 3D points?
- Bundle adjustment answers: what configuration best explains all observations jointly?
- Dense stereo answers: what is the depth of most pixels?
- Fusion answers: how do all those depth maps become one 3D model?
- Meshing answers: what continuous surface best explains the dense samples?

That is the full bridge from pixels to 3D geometry.