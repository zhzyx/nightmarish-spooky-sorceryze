// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

#pragma once

#include "constants.h"

#include "Terrain3DHeightBounds.h"
#include "core/math/rect2i.h"
#include "core/math/transform_3d.h"

class Terrain3D;
class Terrain3DQuadTree;

// Owns the scene MultiMesh. Forward+ computes the per-view transforms, edge stitching
// and draw count before depth/shadows; material and instance binding stay on the normal mesh path.
class Terrain3DGPUDriven
{
	CLASS_NAME_STATIC("Terrain3DGPUDriven");

private:
	Terrain3D *pTerrain = nullptr;
	RID ridMesh;
	RID ridMultimesh;
	RID ridInstance;
	RID ridNodeTexture;
	RID ridHookRid;
	int nNodeCount = 0;
	int nTexWidth = 0;
	int nCapacity = 0;
	int nBackground = -1;
	Rect2i rectDrawExtent;
	Rect2i rectClipmapBounds;
	PackedFloat32Array arrDescriptors;
	bool bDirty = true;
	float fCullLod0Dist = 256.f;
	int nCullMaxLod = 8;
	float fCullMaxDistance = 0.f;

	void ReleaseGeometry();
	void RebuildGeometry();
	Rect2i GetDrawExtent() const;
	void UpdateDrawBounds();
	void ApplyCullConfig();
	void UpdateMeshBounds();

	// Height virtual texture (SVT page table + physical pool, WORLD_HEIGHT / R32F).
	RID ridHeightRvt;
	bool bVtEnabled = false;
	int nVtLog2 = 6;
	int nVtTile = 64;
	int nVtBorder = 2;
	int nVtPool = 32;
	bool bVtDirty = true;
	bool bVtReady = false;
	int32_t nVtConfigFrame = 0;
	bool bStreamDirty = true;
	float fVtSpacing = 0.f;
	int nVtRegionSize = 0;
	float fGroundHeight = 0.f;
	Vector2 vNoiseRange;
	Terrain3DHeightBounds stHeightBounds;
	Vector2 vBackgroundHeights;
	Rect2i rectVtExtent;

	void ReleaseVt();
	void UpdateHeightResources();
	void BindHeightfield();
	void ApplyVtUniforms();

public:
	Terrain3DGPUDriven()
	{
	}
	~Terrain3DGPUDriven()
	{
		Destroy();
	}

	void Initialize(Terrain3D *in_pTerrain);
	void Destroy();
	// Rebuild the node texture / indirect args after the quadtree changed.
	void Rebuild()
	{
		bDirty = true;
	}
	// Uploads dirty data and keeps the registration in sync. Called from Terrain3D::__physics_process.
	void Update();
	// Cull parameters from the r.Terrain3D.Lod0Distance/MaxLod/MaxDistance CVars.
	void SetCullParams(float fLod0Dist, int nMaxLod, float fMaxDistance);
	// VT configuration from the r.Terrain3D.VT* CVars.
	void SetVtConfig(bool bEnabled, int nLog2, int nTile, int nBorder, int nPool);
	void MarkVtDirty()
	{
		bVtDirty = true;
	}
	void StreamSettingsChanged()
	{
		bStreamDirty = true;
	}

	Vector2 GetBackgroundHeightRange() const
	{
		return vBackgroundHeights;
	}
	void UpdateInstance();
	RID GetHeightVt() const
	{
		return ridHeightRvt;
	}
	RID GetMultimesh() const
	{
		return ridMultimesh;
	}
};
