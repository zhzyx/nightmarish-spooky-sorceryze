# Engine Next v4 encoded texture Cook — CPU delivery

Request: `engine-next-visual-runtime-m4-4-20261118`, Issue #1506.

This stage adds explicit encoded mip storage, deterministic CPU Cook and verified page reads. It does not implement GPU upload, texture residency, coverage feedback or streaming. The existing visual runtime deliberately rejects v4 with `gpu_texture_unsupported` until the subsequent GPU integration. v1/v2/v3 and their default commands retain their original layouts.

## Source and build contract

The selected implementation is the unmodified C++ subset of [bc7enc_rdo](https://github.com/richgel999/bc7enc_rdo) at `b9438627eef73a1157e84201b6fa6eb2ffd6d9f0`: bc7enc, rgbcx and bc7decomp, including the referenced rgbcx tables. `engine_next/thirdparty/bc7enc/UPSTREAM.json` records each source digest. Alternative A of its dual license is MIT; the complete upstream license is retained and packaged. No Unreal source, binary, shader, ISPC compiler, RDO frontend or image loader is included. The first-party adapter uses C++17 without exceptions. The build keeps warnings fatal, with narrow diagnostics for unmodified upstream anonymous unions and unused helper/constants; adapter header exceptions end immediately after the third-party includes.

Recipe `bc7enc-b9438627eef73a1157e84201b6fa6eb2ffd6d9f0-u4-bc5hq3-semantic-v1` fixes BC7 search level 4, 64 partitions and upstream default mode mask/least-squares/filterbank, sRGB perceptual weights, equal linear/normal weights, and BC5 HQ radius 3/all endpoint modes. Tables initialize through `std::call_once`; block calls only read them. Fast math is not enabled. Byte-equivalence is tested between Windows x64 MSVC and clang-cl; this is not evidence for untested producer architectures or compilers.

## Format and semantics

`DecodedImage` / `MipLevel::arrRgba8` remain RGBA8. `EncodedTextureMip` instead holds width, height, `TextureFormat` and byte payload. A v4 variant uses only `arrEncodedMips`, retaining its original image index, alpha policy, and `ImageSemantic`. Serialized format values are RGBA8=0, BC7=1, BC5=2. Normal encoding is Cartesian=0 or PositiveZ=1. The whole chain has one GPU format.

The existing semantic mip filter runs before compression: sRGB filtering in linear light with straight-alpha handling, linear scalar filtering, normalized normal filtering. Existing opaque/emissive alpha-ignore rules still apply. BC7 stores color/emissive sRGB bytes or scalar/normal linear bytes; sRGB transfer remains an explicit view semantic rather than a second compression. MASK/BLEND alpha remains part of the BC7 block, subject to lossy quantization.

BC5 stores normal X in R and Y in G. Every source mip must have alpha 255 and positive-Z reconstruction within 2/255 of its stored Z. Otherwise normal RGB uses BC7, retaining the negative hemisphere/non-unit input. PositiveZ reconstruction is `sqrt(max(0, 1 - x*x - y*y))`; no Y flip is introduced. A base image whose dimensions are not multiples of four uses exact RGBA8 for its entire chain, without resizing. BC tails may be smaller than four texels. Edge blocks replicate the last valid row/column.

Dimensions are 1..8192, complete chains end at 1x1, and allocation/layout is bounded before compression. BC7/BC5 use 16 bytes per 4x4 block: tight row bytes `ceil(width/4)*16`, row count `ceil(height/4)`. RGBA8 uses width*4 bytes per row. The later GPU uploader must copy block rows through API footprints rather than reusing an RGBA8 height-row loop.

## Package and validation

v4 reuses the paged manifest, geometry hierarchy, immutable no-replace publication, SHA-256 page verification and source identity. A mandatory `texture_recipe` binds the exact recipe. Page kind 4 is an encoded texture mip; kind 3 retains its v3 RGBA8 meaning. Format/normal metadata lives in the bounded binary metadata, with no inline mip payload. Geometry and original image payloads retain their prior representations.

`LoadGpuPageIndex` opens bounded v3/v4 metadata and checks the directory without loading texture pages. `ReadGpuTextureMip` seeks and verifies one real page, leaving output unchanged on failure. `VerifyPagedScene` recooks from the validated original M3 scene, including semantic mip filtering and encoding for v4, then compares canonical metadata, hierarchy and every declared payload digest. It does not trust a claimed source hash or a self-consistent foreign manifest alone. Changed recipe, bad block length, wrong format/normal association, corrupt payload, wrong source and source-derived mismatch fail closed. `LoadVerifiedEncodedGpuPackage` uses the same implementation as the compatibility loader with v4 explicitly allowed, and retains transactional output.

CLI: `next_asset gpu-cook-v4 --package SOURCE.enpak --output TARGET.engpu`, followed by `gpu-validate --package TARGET.engpu --source-package SOURCE.enpak`. Validation reports the actual encoded formats, mip counts and bytes. `--source-digest` alone is not full v4 source verification.

## Current verification boundary

CPU regression covers concurrent initialization and repeatability, real BC7/BC5 encoding and decode, block/row layout bounds, negative Z and alpha fallback, exact odd/tiny RGBA fallback, malformed input and transactional failure, all four package versions, real partial page reads, source/recipe/payload tampering, and immutable publication reconciliation. A self-authored fixture exercises color, MASK alpha, scalar, positive-Z and negative-Z normal, emissive and odd-size images using the actual CLI.

BC7 is lossy. The synthetic 16x16 two-axis color ramp measured base-mip RGBA RMS 4.18..5.98 code values; its coarse 4x4 mip spans the full ramp inside one block and reaches RMS 22.01/max channel error 36. Regression bounds explicitly preserve that observed limitation instead of claiming lossless or general image quality. A separate varying-normal BC5 fixture checks a two-degree angular bound. Final scene quality, alpha silhouette behavior, GPU memory reduction and runtime streaming remain to be measured after GPU integration.
