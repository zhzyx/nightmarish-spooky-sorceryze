# Bounded directional virtual shadow pages

Status: implementation in progress. This document is a design, not acceptance evidence.

## Scope and references

The M4 requirement calls for directional cascades, local shadows, PCF/PCSS, a high-detail virtual shadow map or equivalent, dynamic updates, caching, and visible evidence of precision and stability. The existing four-cascade and point/spot paths remain the default. The optional directional virtual path adds higher-resolution receiver pages and retains the complete conventional cascade as a valid fallback for every unmapped page. It does not disable local shadows, alpha-tested casters, animation, or original M3 geometry.

Read-only architectural references are UE 5.8.3 `VirtualShadowMapArray.h` (physical pool and page-table separation), `VirtualShadowMapCacheManager.h` (retained cache and primitive invalidation), and `VirtualShadowMapClipmap.cpp` (projection and light changes invalidate cached entries). No UE implementation, shader, or asset is copied. The first implementation uses the existing self-authored cascade layout rather than claiming UE's clipmap, Nanite rasterizer, or complete VSM feature equivalence.

## Allocation and addressing

- Virtual resolution: 8192 texels per cascade by default, configurable powers of two from 2048 through 16384.
- Pages: 128 useful texels with a two-texel raster border. A physical page is a 132 by 132 depth slice.
- Pool: 512 physical slices by default, configurable from 16 through 2048. The checked allocation budget includes the pool, page tables, staging, feedback, constants, and readback.
- A logical address consists of cascade, page X, and page Y. A GPU page-table record holds the physical slice plus one and the depth transform used when that physical page was rendered. Zero means use the conventional shadow.
- Feedback is generated from the actual opaque depth buffer. It counts receiver coverage and neighboring pages needed by filtering and cascade transitions. Retired feedback is collected only after its owning frame fence completes.
- Feedback from a translated/scaled projection is conservatively mapped to the current cascade projection. A changed light basis rejects stale feedback. Coverage entering the view can use the complete conventional fallback until new feedback retires.

## Cache correctness

CPU cache preparation produces an isolated candidate. Submission commits mappings, ages, per-page depth transforms, and caster history together; cancellation preserves prior committed state. The shared depth pool is read and written on the same DIRECT queue. Per-frame upload, page tables, descriptors, and readback are never overwritten before their fence retires.

The optional `cache` switch defaults to true. False requests a fresh rasterization of each selected page and the conventional fallback every frame, permitting a same-scene cached/uncached image comparison. Both paths use the same physical pool and deterministic coverage priority.

Changing cascade XY projection invalidates that cascade's physical mappings. Initial implementation deliberately rerenders these pages instead of claiming clipmap scrolling reuse. A changed depth span alone does not invalidate a static page: its table record retains the exact depth transform used to rasterize it, and the receiver compares in that same transform. This avoids making every breathing animation invalidate every page merely by extending the scene depth span.

Moving rigid casters invalidate pages intersecting both old and new projected bounds. Animated casters also supply explicit changed-draw IDs, so deformation inside unchanged outer bounds still invalidates affected pages. This history is independent of screen TAA history. Light-direction changes invalidate all affected projections. Scene topology/identity changes invalidate the entire cache. Exact material/alpha revisions require explicit invalidation; the current runtime loads immutable material resources.

Pages requested this frame are protected from eviction. Remaining slots use deterministic least-recently-requested eviction. If requested coverage exceeds the pool or update budget, the missing region uses complete conventional shadows; it never samples a stale mapping. The allocator and GPU table expose requested, resident, reused, rendered, invalidated, evicted, deferred, and unmatched-feedback counts.

## Rendering and integration

New frame descriptors are reserved at 460 through 467, after the RT block. New pass identifiers are reserved at 80 through 83: upload/clear, page rendering, receiver feedback, and feedback readback. Deferred and transparent receivers use optional t32/t33 and b5; t31 remains available for AO. Feature-disabled permutations preserve existing shader bindings.

Each dirty physical slice is cleared and rasterized with a cropped directional projection. Existing shadow material sampling, winding, double-sided handling, deformed VB0, and all original triangle indices are reused. Conservative page-frustum tests omit only casters proven outside the page. Filtering uses the existing receiver-plane depth correction at virtual texel spacing and the page's own stored depth transform. Cascade blending remains in the common directional receiver path.

Static local bounds are computed once. Animated local bounds use the current posed vertices; both pass through the existing GPU-conservative world-bound transform. Page-frustum arithmetic expands by the absolute sum of projection products, preserving uncertainty from large-coordinate cancellation instead of basing its margin only on the small final coordinate.

The coarse per-frame shadow allocation can itself be reused only when its full projection and caster content signature match. Otherwise it is fully updated before any fallback receiver reads it.

## Required validation

CPU tests cover bounded allocation, deterministic eviction, all-pinned overflow, invalid input transactions, page borders, reversed axes, conservative feedback reprojection, old/new caster invalidation, unchanged-bounds deformation, depth-only projection changes, cancellation, and commit.

Real GPU tests must compare feature off, enabled uncached, and cached results; exercise a static view, camera translation, changing light direction, moving rigid and skinned casters, alpha cutout, tiny pool overflow, resize/projection resets, and rollback. Actual depth pool/table/feedback bytes and draw dispatches must be read from captures. Static reuse must demonstrate reduced page draws without changing the image. High-detail imagery and pool pressure must be shown separately from any final 4K performance or UE quality conclusion.
