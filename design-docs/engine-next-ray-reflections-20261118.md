# M4.5 ray reflections

Issue: #1505. Parent: #1323. This is a specular-lighting increment; it does not complete the M4.5 visual-quality or performance acceptance.

## Selection and compatibility

`reflections.ray_tracing.enabled` defaults to false. The original disabled and screen-space reflection routes remain selectable. Enabling ray tracing requires `reflections.enabled`. The runtime allocates material parameter/tangent targets for this path even when there are no material overrides.

Settings are `resolution_divisor` (1 or 2), `samples_per_lobe` (1–4), `spatial_passes` (0–3), `max_history` (1–64), `history_weight` (0–0.98), relative `depth_threshold`, `normal_threshold`, `roughness_threshold`, and `max_gpu_bytes`. Invalid settings are rejected even when disabled. Dimensions use ceiling division, including odd viewports. The backend checks committed resource allocation sizes against the budget, including its own acceleration structure when GI does not already own one.

## Transport

The primary receiver is the opaque/MASK GBuffer. Each base-specular and clearcoat lobe uses a stratified pair of its existing GGX distribution and the environment importance distribution per sample setting. The mixture PDF is evaluated for both proposals with half weight each, so pairing does not double the estimated energy. Lobe energies and their coat transmission use the shared material BRDF, and both lobe estimates replace the existing environment-specular term exactly once. Direct, diffuse GI and emissive lighting in the base HDR remain intact.

A confident screen hit may supply the current screen radiance. A screen miss, edge rejection or rough ray can query the complete scene with DXR 1.1 `RayQuery`. Closest-hit shading uses the canonical vertex/index/draw/material buffers, texture UVs, normal maps, mirrored tangent handedness, emission, direct light visibility and diffuse GI or environment fallback. Secondary metals retain environment specular. MASK uses the source alpha cutoff; secondary BLEND intersections use stochastic coverage. Forward transparent primary receivers and refractive transmission remain separate work.

Direct-light visibility at an offscreen hit uses geometry queries, rather than assuming that the camera's shadow maps contain that receiver. Trace distance and candidate traversal are bounded. This increment shades one secondary surface; it does not claim recursive specular transport.

## History and filtering

The ray grid is unjittered; a consistent current raster pixel supplies surface attributes and motion. Base and coat have independent RGB history, sample counts and luminance moments. A central specular geometry witness supplies stable hit identity/distance independently of stochastic radiance proposals. History taps individually validate stable object ID, positive previous view depth, normal, roughness and witness compatibility. Rejected taps do not contaminate bilinear reconstruction. Current-neighborhood clipping and variance-aware spatial filtering reduce stochastic noise. Near-perfect mirrors avoid spatial mixing.

Histories use unexposed binary32 radiance, avoiding half-format loss of small values and exposure-dependent history scale. Seven images in each of two history groups, three raw images and two spatial scratch images require 248 payload bytes per ray pixel. Actual D3D12 alignment and frame uploads/readback are additional budgeted allocations. Full-resolution composition validates surface metadata while upsampling; unmatched pixels retain the original environment term.

## GPU ownership

`GpuRayReflections` uses one owner thread and the host's DIRECT queue/fence domain. When GI is enabled it borrows the existing `RayTracingScene`; GI remains its sole build and submission owner. Otherwise reflections own the scene. All descriptors for each stage are distinct within a frame, and frame slots are rewritten only after retirement. Views 232–459 are reserved; AO views 184–189 and geometry views 192–231 are retained.

Frame-graph work 68–74 covers scene construction, counter preparation, trace, temporal reconstruction, spatial passes, composition and readback. The graph declares UAV/read transitions and returns reusable images to Common. History roles and epoch advance only after a successful queue signal. Discarded command lists do not commit history. Resize, camera cut and reconnect invalidate history; resize recreates size-dependent allocations after retirement.

## Validation status

The initial integrated candidates compile all four strict `cs_6_5` entries and pass shared CPU math, configuration and graph regression tests. R2/R3 execute real scene queries without GPU validation errors. R3 mature readback exposed unstable stochastic hit metadata: approximately 73% of the selected reflection region still had history count one in a static scene. Those images and captures remain failure evidence; paired proposals and the independent witness address this in the next candidate. Offscreen/occluder movement, disocclusion, clearcoat separation and visual convergence still require candidate-specific GPU evidence. No performance or final visual-parity claim follows from compilation or GPU validation alone.
