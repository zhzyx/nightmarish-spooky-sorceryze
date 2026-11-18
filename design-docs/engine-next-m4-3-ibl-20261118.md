# Engine Next environment importance sampling

This increment belongs to Issue #1343 and follows the material implementation merged at `23d4e05bac6d469250327c8eaa1149021cff7ba0`. It addresses the isolated bright samples observed in the material environment benchmark.

## Distribution and storage

The CPU builds a Vose alias table from the same six linear HDR images uploaded as environment mip zero. Each texel receives Rec.709 luminance multiplied by its exact cubemap rectangle solid angle. The alias constructor uses double intermediates and reconstructs the actual marginal probabilities after storing binary32 thresholds.

Each GPU entry contains a float threshold, uint alias, float marginal probability and uint metadata. Metadata stores face size shifted left by one and the uniform-fallback flag in bit zero. The shader validates stride, count and encoded size before sampling. An all-black map uses a uniform-sphere proposal with density `1/(4π)`.

The 64-square source produces 24,576 entries and a 393,216-byte immutable GPU buffer. Creation shares the existing scene upload command list and upload budget. The upload allocation retires after the scene-upload graphics fence. The resident buffer remains alive with the scene. Its shader-resource state permits both pixel and compute readers.

The global descriptor follows the existing three environment descriptors. All material receivers access it at `t15`. Frame constants retain their existing 3,120-byte layout. Materials with normalized zero extension strengths keep the existing rendering route.

## Sampling and material response

The alias sample chooses a texel and then a uniform position within its UV rectangle. The directional PDF includes the cubemap Jacobian. The arbitrary-direction query uses the same face convention and marginal probability. Finite boundary points that round into an adjacent texel resolve to the selected cell center.

Each diffuse, base-specular and clearcoat lobe uses its own balance estimate against the common environment proposal. Every contribution contains the denominator `nBrdf*pBrdf + nEnvironment*pEnvironment`. The caller sums contributions directly. It performs no additional division by the total count.

The active lighting budget is 16 base, 8 coat, 8 diffuse and 24 environment samples. Zero coat and metallic diffuse lobes omit their unused draws. One environment sample supplies all applicable lobe contributions. The shared functions evaluate the existing material lobes directly.

Screen-space reflections use the same base and coat estimates with 24 shared environment samples. Each sampled direction traces once. The hit radiance and environment radiance receive each lobe's existing roughness confidence separately. Diffuse remains in the lighting pass. Environment radiance receives pre-exposure once and screen-space hit radiance already has that exposure.

## Deterministic sequence correction

The first integrated candidate exposed a grid collision that random Monte Carlo tests did not exercise. A 24-sample midpoint sequence multiplied by a 24,576-entry table produced an integer for every sample. Its alias coin stayed zero throughout the sequence.

The environment coordinate now applies a deterministic hashed offset inside each of its 24 strata. The remaining UV coordinates use base-two and base-three digit reversal. Tests retain the exact midpoint collision as a regression and verify the stratified proposal over independent deterministic seeds. The original alias thresholds and reconstructed probabilities remain unchanged.

## Build boundary

The CPU table constructor and upload lifecycle belong to the native rendering module. Shared shader math and the four active material shader permutations belong to the offline shader bundle. The remaining 28 shader outputs matched the material baseline byte for byte during initial verification.

The existing default and explicitly zero material configurations continue to use the earlier shader route. Source packages, decoded materials, normal-map semantics, texture alpha policy and asset identities remain unchanged.

## Verification status

The initial candidate passed the nine existing material scenes, 168 total frames and zero GPU validation errors. Default and zero overrides produced identical pixels. Three same-binary RenderDoc runs captured the initial importance estimate, the earlier 32/16/8 estimate and the 512/256/128 NDF reference. The actual alias buffer and all six environment mip-zero faces matched the CPU source bytes.

The initial importance estimate reduced the isolated-pixel count but its measured mean exposed the deterministic alias-coin collision. The corrected sequence passed the same-binary comparison. All nine GBuffer/depth outputs, frame constants, the actual alias buffer and six source cube faces matched. The original estimate had 24 isolated bright pixels in the 31,052-pixel interior mask. The corrected estimate and the denser reference each had zero. RGB RMS against that reference fell from 0.09136585 to 0.03211194. Mean luminance was 0.22131614 against the reference 0.22154542. The denser NDF image retains its own finite-sampling error.

The corrected runtime also passed the nine-scene 168-frame matrix and a 12-frame hidden 3840×2160 render-target check with TAA, Bloom and SSR. GPU validation reported zero errors. These checks exercise the material increment. They do not establish physical display output or the full M4 performance target.

Full native-4K display output, Unreal Engine scene comparisons and the remaining M4 acceptance criteria remain with the parent milestone.
