/**************************************************************************/
/*  TestGltfDecoder.cpp                                                   */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                  */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining  */
/* a copy of this software and associated documentation files (the        */
/* "Software"), to deal in the Software without restriction, including    */
/* without limitation the rights to use, copy, modify, merge, publish,    */
/* distribute, sublicense, and/or sell copies of the Software, and to     */
/* permit persons to whom the Software is furnished to do so, subject to  */
/* the following conditions:                                              */
/*                                                                        */
/* The above copyright notice and this permission notice shall be         */
/* included in all copies or substantial portions of the Software.        */
/*                                                                        */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,        */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF     */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY   */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,   */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE      */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                 */
/**************************************************************************/

#include "engine_next/Tests/TestFramework.h"
#include "engine_next/Rendering/Cook/GltfDecoder.h"
#include "engine_next/include/EngineNext/Serialization/Json.h"
#include "engine_next/include/EngineNext/Assets/BlobValidator.h"
#include "engine_next/include/EngineNext/Serialization/Sha256.h"
#include "engine_next/include/EngineNext/Rendering/RenderScene.h"
#include "engine_next/Tests/Assets/FixtureSupport.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <utility>
#include <vector>

namespace
{

using EngineNext::Rendering::DecodedMesh;
using EngineNext::Rendering::DecodeGlb;
using EngineNext::Serialization::JsonValue;

void Append32(std::vector<std::uint8_t> &out_arrBytes, std::uint32_t nValue)
{
	for (std::uint32_t nByte = 0; nByte < 4; ++nByte)
	{
		out_arrBytes.push_back(static_cast<std::uint8_t>(nValue >> (nByte * 8U)));
	}
}

void AppendFloat(std::vector<std::uint8_t> &out_arrBytes, float fValue)
{
	std::uint32_t nBits = 0;
	std::memcpy(&nBits, &fValue, sizeof(nBits));
	Append32(out_arrBytes, nBits);
}

struct GlbFixture
{
	JsonValue::Object mapRoot;
	std::vector<std::uint8_t> arrBinary;

	GlbFixture()
	{
		for (float fValue : std::array<float, 9>{ 0, 0, 0, 1, 0, 0, 0, 1, 0 })
		{
			AppendFloat(arrBinary, fValue);
		}
		arrBinary.insert(arrBinary.end(), { 0, 1, 2, 0 });
		mapRoot = JsonValue::Object{
			{ "asset", JsonValue::Object{ { "version", "2.0" } } },
			{ "buffers", JsonValue::List{ JsonValue::Object{ { "byteLength", std::int64_t{ 40 } } } } },
			{ "bufferViews", JsonValue::List{
									 JsonValue::Object{ { "buffer", std::int64_t{ 0 } }, { "byteLength", std::int64_t{ 36 } } },
									 JsonValue::Object{ { "buffer", std::int64_t{ 0 } }, { "byteOffset", std::int64_t{ 36 } }, { "byteLength", std::int64_t{ 3 } } },
							 } },
			{ "accessors", JsonValue::List{
								   JsonValue::Object{ { "bufferView", std::int64_t{ 0 } }, { "componentType", std::int64_t{ 5126 } }, { "count", std::int64_t{ 3 } }, { "type", "VEC3" } },
								   JsonValue::Object{ { "bufferView", std::int64_t{ 1 } }, { "componentType", std::int64_t{ 5121 } }, { "count", std::int64_t{ 3 } }, { "type", "SCALAR" } },
						   } },
			{ "meshes", JsonValue::List{ JsonValue::Object{ { "primitives", JsonValue::List{
																					JsonValue::Object{ { "attributes", JsonValue::Object{ { "POSITION", std::int64_t{ 0 } } } }, { "indices", std::int64_t{ 1 } } },
																			} } } } },
		};
	}

	JsonValue::Object &Primitive()
	{
		return *(*(*mapRoot["meshes"].GetList())[0].GetObject())["primitives"].GetList()->at(0).GetObject();
	}

	std::vector<std::uint8_t> Bytes()
	{
		(*mapRoot["buffers"].GetList())[0].GetObject()->at("byteLength") = JsonValue(static_cast<std::int64_t>(arrBinary.size()));
		std::string strJson;
		ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(JsonValue(mapRoot), strJson));
		while (strJson.size() % 4 != 0)
		{
			strJson.push_back(' ');
		}
		while (arrBinary.size() % 4 != 0)
		{
			arrBinary.push_back(0);
		}
		std::vector<std::uint8_t> arrBytes;
		Append32(arrBytes, 0x46546C67U);
		Append32(arrBytes, 2);
		Append32(arrBytes, static_cast<std::uint32_t>(28 + strJson.size() + arrBinary.size()));
		Append32(arrBytes, static_cast<std::uint32_t>(strJson.size()));
		Append32(arrBytes, 0x4E4F534AU);
		arrBytes.insert(arrBytes.end(), strJson.begin(), strJson.end());
		Append32(arrBytes, static_cast<std::uint32_t>(arrBinary.size()));
		Append32(arrBytes, 0x004E4942U);
		arrBytes.insert(arrBytes.end(), arrBinary.begin(), arrBinary.end());
		return arrBytes;
	}
};

bool Decode(GlbFixture &stFixture, DecodedMesh &out_stMesh)
{
	EngineNext::Assets::Diagnostics arrDiagnostics;
	return DecodeGlb(stFixture.Bytes(), out_stMesh, arrDiagnostics);
}

EngineNext::Assets::PackageData Package(GlbFixture &stFixture)
{
	EngineNext::Assets::PackageData stPackage;
	const std::vector<std::uint8_t> arrBytes = stFixture.Bytes();
	const std::string strDigest = EngineNext::Serialization::Sha256Hex(arrBytes.data(), arrBytes.size());
	stPackage.stScene.strSceneId = "m42.scene";
	stPackage.stScene.strSceneRevision = "r1";
	EngineNext::Assets::SceneEntity stParent;
	stParent.nEntityId = 1;
	stParent.strName = "Parent";
	stParent.strNodeType = "Node3D";
	stParent.strGameplayKind = "static";
	stParent.stTransform.arrTranslation = { 2, 3, 4 };
	stPackage.stScene.arrEntities.push_back(stParent);
	EngineNext::Assets::SceneEntity stChild;
	stChild.nEntityId = 2;
	stChild.nParentEntityId = 1;
	stChild.strName = "Child";
	stChild.strNodeType = "MeshInstance3D";
	stChild.strGameplayKind = "static";
	stChild.stTransform.arrTranslation = { 5, 0, 0 };
	stChild.arrAssets.push_back({ "mesh", { "m42.mesh", "r1", strDigest } });
	stPackage.stScene.arrEntities.push_back(stChild);
	std::string strSceneJson;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(EngineNext::Assets::ToJson(stPackage.stScene), strSceneJson));
	stPackage.stManifest.strSceneId = stPackage.stScene.strSceneId;
	stPackage.stManifest.strSceneRevision = stPackage.stScene.strSceneRevision;
	stPackage.stManifest.strSceneContentSha256 = EngineNext::Serialization::Sha256Hex(strSceneJson);
	EngineNext::Assets::AssetEntry stAsset;
	stAsset.strAssetId = "m42.mesh";
	stAsset.strRevision = "r1";
	stAsset.strContentSha256 = strDigest;
	stAsset.strMediaType = "model/gltf-binary";
	stAsset.strType = "mesh";
	stAsset.nByteSize = arrBytes.size();
	stAsset.stSource.strKind = "godot_whitelist_import";
	stAsset.stSource.strImporterVersion = "1";
	stPackage.stManifest.arrAssets.push_back(stAsset);
	stPackage.mapBlobs[strDigest] = arrBytes;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Assets::ComputePackageDigest(stPackage, arrDiagnostics));
	return stPackage;
}

} // namespace

ENGINE_NEXT_TEST("GLB rendering decoder generates flat normals and a default material")
{
	GlbFixture stFixture;
	DecodedMesh stMesh;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh));
	ENGINE_NEXT_CHECK_EQ(stMesh.arrPrimitives.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrMaterials.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrPrimitives[0].arrIndices.size(), 3U);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrPrimitives[0].nMaterial, 0);
	ENGINE_NEXT_CHECK_FLOAT(stMesh.arrPrimitives[0].arrVertices[0].arrNormal[2], 1.0F);
	ENGINE_NEXT_CHECK_FLOAT(stMesh.arrPrimitives[0].arrVertices[0].arrTangent[0], 1.0F);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances[0].arrTransform[0], 1.0);
}

ENGINE_NEXT_TEST("GLB rendering decoder regenerates tangents when normals are absent")
{
	GlbFixture stFixture;
	for (std::size_t nVertex = 0; nVertex < 3; ++nVertex)
	{
		for (float fComponent : std::array<float, 4>{ 0, 0, 1, -1 })
		{
			AppendFloat(stFixture.arrBinary, fComponent);
		}
	}
	stFixture.mapRoot["bufferViews"].GetList()->push_back(JsonValue::Object{ { "buffer", std::int64_t{ 0 } }, { "byteOffset", std::int64_t{ 40 } }, { "byteLength", std::int64_t{ 48 } } });
	stFixture.mapRoot["accessors"].GetList()->push_back(JsonValue::Object{ { "bufferView", std::int64_t{ 2 } }, { "componentType", std::int64_t{ 5126 } }, { "count", std::int64_t{ 3 } }, { "type", "VEC4" } });
	(*stFixture.Primitive()["attributes"].GetObject())["TANGENT"] = std::int64_t{ 2 };
	DecodedMesh stMesh;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh));
	if (stMesh.arrPrimitives.empty())
	{
		return;
	}
	for (const EngineNext::Rendering::MeshVertex &stVertex : stMesh.arrPrimitives[0].arrVertices)
	{
		ENGINE_NEXT_CHECK_FLOAT(stVertex.arrNormal[2], 1.0F);
		ENGINE_NEXT_CHECK_FLOAT(stVertex.arrTangent[0], 1.0F);
		ENGINE_NEXT_CHECK_FLOAT(stVertex.arrTangent[2], 0.0F);
		ENGINE_NEXT_CHECK_FLOAT(stVertex.arrTangent[3], 1.0F);
	}
}

ENGINE_NEXT_TEST("GLB rendering decoder preserves supported PBR material semantics")
{
	GlbFixture stFixture;
	stFixture.mapRoot["materials"] = JsonValue::List{ JsonValue::Object{
			{ "pbrMetallicRoughness", JsonValue::Object{ { "baseColorFactor", JsonValue::List{ 0.25, 0.5, 0.75, 0.8 } }, { "metallicFactor", 0.7 }, { "roughnessFactor", 0.3 } } },
			{ "emissiveFactor", JsonValue::List{ 0.1, 0.2, 0.3 } },
			{ "alphaMode", "MASK" },
			{ "alphaCutoff", 0.4 },
			{ "doubleSided", true },
	} };
	stFixture.Primitive()["material"] = std::int64_t{ 0 };
	DecodedMesh stMesh;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh));
	ENGINE_NEXT_CHECK_EQ(stMesh.arrMaterials.size(), 2U);
	const EngineNext::Rendering::MaterialData &stMaterial = stMesh.arrMaterials[0];
	ENGINE_NEXT_CHECK_FLOAT(stMaterial.arrBaseColor[2], 0.75F);
	ENGINE_NEXT_CHECK_FLOAT(stMaterial.fMetallic, 0.7F);
	ENGINE_NEXT_CHECK_FLOAT(stMaterial.fRoughness, 0.3F);
	ENGINE_NEXT_CHECK_FLOAT(stMaterial.fAlphaCutoff, 0.4F);
	ENGINE_NEXT_CHECK(stMaterial.bDoubleSided);
	ENGINE_NEXT_CHECK_EQ(stMaterial.eAlphaMode, EngineNext::Rendering::AlphaMode::Mask);
}

ENGINE_NEXT_TEST("GLB rendering decoder composes nested transforms and selects the default scene")
{
	GlbFixture stFixture;
	stFixture.mapRoot["nodes"] = JsonValue::List{
		JsonValue::Object{ { "translation", JsonValue::List{ 2.0, 3.0, 4.0 } }, { "children", JsonValue::List{ std::int64_t{ 1 } } } },
		JsonValue::Object{ { "mesh", std::int64_t{ 0 } }, { "translation", JsonValue::List{ 1.0, 0.0, 0.0 } }, { "scale", JsonValue::List{ -2.0, 1.0, 1.0 } } },
		JsonValue::Object{ { "mesh", std::int64_t{ 0 } }, { "translation", JsonValue::List{ 99.0, 0.0, 0.0 } } },
	};
	stFixture.mapRoot["scenes"] = JsonValue::List{
		JsonValue::Object{ { "nodes", JsonValue::List{ std::int64_t{ 2 } } } },
		JsonValue::Object{ { "nodes", JsonValue::List{ std::int64_t{ 0 } } } },
	};
	stFixture.mapRoot["scene"] = std::int64_t{ 1 };
	DecodedMesh stMesh;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh));
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances[0].nNode, 1U);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances[0].arrTransform[12], 3.0);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances[0].arrTransform[13], 3.0);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances[0].arrTransform[0], -2.0);
}

ENGINE_NEXT_TEST("GLB rendering decoder rejects hierarchy cycles and multiple parents")
{
	GlbFixture stFixture;
	stFixture.mapRoot["nodes"] = JsonValue::List{
		JsonValue::Object{ { "children", JsonValue::List{ std::int64_t{ 1 } } } },
		JsonValue::Object{ { "mesh", std::int64_t{ 0 } }, { "children", JsonValue::List{ std::int64_t{ 0 } } } },
	};
	DecodedMesh stMesh;
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
	stFixture.mapRoot["nodes"] = JsonValue::List{
		JsonValue::Object{ { "children", JsonValue::List{ std::int64_t{ 2 } } } },
		JsonValue::Object{ { "children", JsonValue::List{ std::int64_t{ 2 } } } },
		JsonValue::Object{ { "mesh", std::int64_t{ 0 } } },
	};
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
}

ENGINE_NEXT_TEST("GLB rendering decoder rejects unsupported required extensions and animated geometry")
{
	GlbFixture stFixture;
	DecodedMesh stMesh;
	stFixture.mapRoot["extensionsRequired"] = JsonValue::List{ "KHR_materials_clearcoat" };
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
	stFixture.mapRoot.erase("extensionsRequired");
	stFixture.mapRoot["animations"] = JsonValue::List{ JsonValue::Object{} };
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
	stFixture.mapRoot.erase("animations");
	stFixture.Primitive()["targets"] = JsonValue::List{};
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
	stFixture.Primitive().erase("targets");
	stFixture.mapRoot["extensions"] = JsonValue::Object{ { "unknown", JsonValue::Object{} } };
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
}

ENGINE_NEXT_TEST("GLB rendering decoder validates binary padding against declared buffer length")
{
	GlbFixture stFixture;
	std::vector<std::uint8_t> arrBytes = stFixture.Bytes();
	const std::size_t nJsonLength = static_cast<std::size_t>(arrBytes[12]) | (static_cast<std::size_t>(arrBytes[13]) << 8U) |
			(static_cast<std::size_t>(arrBytes[14]) << 16U) | (static_cast<std::size_t>(arrBytes[15]) << 24U);
	const std::size_t nBinaryHeader = 20 + nJsonLength;
	const std::size_t nOriginalLength = arrBytes.size();
	arrBytes.insert(arrBytes.end(), 4, 0);
	for (std::uint32_t nByte = 0; nByte < 4; ++nByte)
	{
		arrBytes[8 + nByte] = static_cast<std::uint8_t>((nOriginalLength + 4) >> (nByte * 8U));
		arrBytes[nBinaryHeader + nByte] = static_cast<std::uint8_t>((stFixture.arrBinary.size() + 4) >> (nByte * 8U));
	}
	EngineNext::Assets::BlobInfo stInfo;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Assets::ValidateBlob("model/gltf-binary", arrBytes, stInfo, arrDiagnostics));
	DecodedMesh stMesh;
	ENGINE_NEXT_CHECK(!DecodeGlb(arrBytes, stMesh, arrDiagnostics));
	arrBytes = stFixture.Bytes();
	const std::size_t nJsonStart = 20;
	const std::string strLength = "\"byteLength\":40";
	const std::vector<std::uint8_t>::iterator itLength = std::search(arrBytes.begin() + nJsonStart, arrBytes.begin() + nBinaryHeader, strLength.begin(), strLength.end());
	ENGINE_NEXT_CHECK(itLength != arrBytes.begin() + nBinaryHeader);
	if (itLength == arrBytes.begin() + nBinaryHeader)
	{
		return;
	}
	*(itLength + static_cast<std::ptrdiff_t>(strLength.size() - 2)) = '3';
	*(itLength + static_cast<std::ptrdiff_t>(strLength.size() - 1)) = '9';
	ENGINE_NEXT_CHECK(DecodeGlb(arrBytes, stMesh, arrDiagnostics));
	arrBytes.back() = 1;
	ENGINE_NEXT_CHECK(EngineNext::Assets::ValidateBlob("model/gltf-binary", arrBytes, stInfo, arrDiagnostics));
	ENGINE_NEXT_CHECK(!DecodeGlb(arrBytes, stMesh, arrDiagnostics));
}

ENGINE_NEXT_TEST("GLB rendering decoder validates asset version and explicit primitive references")
{
	GlbFixture stFixture;
	DecodedMesh stMesh;
	(*stFixture.mapRoot["asset"].GetObject())["minVersion"] = "2.1";
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
	stFixture.mapRoot["asset"].GetObject()->erase("minVersion");
	stFixture.Primitive()["indices"] = std::int64_t{ -1 };
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
	stFixture.Primitive().erase("indices");
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh));
	ENGINE_NEXT_CHECK_EQ(stMesh.arrPrimitives[0].arrIndices, std::vector<std::uint32_t>({ 0, 1, 2 }));
}

ENGINE_NEXT_TEST("GLB rendering decoder selects scene zero and supports matrix nodes")
{
	GlbFixture stFixture;
	stFixture.mapRoot["nodes"] = JsonValue::List{
		JsonValue::Object{ { "mesh", std::int64_t{ 0 } }, { "matrix", JsonValue::List{ 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 12.0, 0.0, 0.0, 1.0 } } },
		JsonValue::Object{ { "mesh", std::int64_t{ 0 } }, { "translation", JsonValue::List{ 99.0, 0.0, 0.0 } } },
	};
	stFixture.mapRoot["scenes"] = JsonValue::List{
		JsonValue::Object{ { "nodes", JsonValue::List{ std::int64_t{ 0 } } } },
		JsonValue::Object{ { "nodes", JsonValue::List{ std::int64_t{ 1 } } } },
	};
	DecodedMesh stMesh;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh));
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances[0].arrTransform[12], 12.0);
	(*stFixture.mapRoot["nodes"].GetList())[0].GetObject()->emplace("translation", JsonValue::List{ 1.0, 0.0, 0.0 });
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
}

ENGINE_NEXT_TEST("GLB rendering decoder canonicalizes tolerated affine matrix noise")
{
	GlbFixture stFixture;
	stFixture.mapRoot["nodes"] = JsonValue::List{
		JsonValue::Object{ { "mesh", std::int64_t{ 0 } }, { "matrix", JsonValue::List{ 1.0, 0.0, 0.0, 1.0e-12, 0.0, 1.0, 0.0, -1.0e-12, 0.0, 0.0, 1.0, 0.0, 2.0, 3.0, 4.0, 1.0 + 1.0e-12 } } }
	};
	DecodedMesh stMesh;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh));
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances[0].arrTransform[3], 0.0);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances[0].arrTransform[7], 0.0);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances[0].arrTransform[11], 0.0);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances[0].arrTransform[15], 1.0);
}

ENGINE_NEXT_TEST("GLB rendering decoder rejects nonfinite vertices without modifying prior output")
{
	GlbFixture stFixture;
	DecodedMesh stMesh;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh));
	const std::uint32_t nNan = 0x7FC00000U;
	for (std::uint32_t nByte = 0; nByte < 4; ++nByte)
	{
		stFixture.arrBinary[nByte] = static_cast<std::uint8_t>(nNan >> (nByte * 8U));
	}
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(!DecodeGlb(stFixture.Bytes(), stMesh, arrDiagnostics));
	ENGINE_NEXT_CHECK(!arrDiagnostics.empty());
	ENGINE_NEXT_CHECK_EQ(stMesh.arrInstances.size(), 1U);
	ENGINE_NEXT_CHECK_FLOAT(stMesh.arrPrimitives[0].arrVertices[0].arrPosition[0], 0.0F);
}

ENGINE_NEXT_TEST("GLB rendering decoder rejects malformed materials, transforms and attribute references")
{
	GlbFixture stFixture;
	DecodedMesh stMesh;
	stFixture.mapRoot["materials"] = JsonValue::List{ JsonValue::Object{ { "roughnessFactor", 0.5 }, { "doubleSided", "yes" } } };
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
	stFixture.mapRoot.erase("materials");
	stFixture.Primitive()["material"] = std::int64_t{ 0 };
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
	stFixture.Primitive().erase("material");
	(*stFixture.Primitive()["attributes"].GetObject())["NORMAL"] = std::int64_t{ 20 };
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
	stFixture.Primitive()["attributes"].GetObject()->erase("NORMAL");
	stFixture.mapRoot["nodes"] = JsonValue::List{ JsonValue::Object{ { "mesh", std::int64_t{ 0 } }, { "scale", JsonValue::List{ 0.0, 1.0, 1.0 } } } };
	ENGINE_NEXT_CHECK(!Decode(stFixture, stMesh));
}

ENGINE_NEXT_TEST("GLB rendering decoder decodes normalized UV and signed normals")
{
	GlbFixture stFixture;
	stFixture.arrBinary.insert(stFixture.arrBinary.end(), { 0, 0, 255, 0, 0, 255, 0, 0 });
	stFixture.arrBinary.insert(stFixture.arrBinary.end(), { 0, 0, 127, 0, 0, 0, 127, 0, 0, 0, 127, 0 });
	stFixture.mapRoot["bufferViews"].GetList()->push_back(JsonValue::Object{ { "buffer", std::int64_t{ 0 } }, { "byteOffset", std::int64_t{ 40 } }, { "byteLength", std::int64_t{ 6 } } });
	stFixture.mapRoot["bufferViews"].GetList()->push_back(JsonValue::Object{ { "buffer", std::int64_t{ 0 } }, { "byteOffset", std::int64_t{ 48 } }, { "byteLength", std::int64_t{ 12 } }, { "byteStride", std::int64_t{ 4 } } });
	stFixture.mapRoot["accessors"].GetList()->push_back(JsonValue::Object{ { "bufferView", std::int64_t{ 2 } }, { "componentType", std::int64_t{ 5121 } }, { "count", std::int64_t{ 3 } }, { "type", "VEC2" }, { "normalized", true } });
	stFixture.mapRoot["accessors"].GetList()->push_back(JsonValue::Object{ { "bufferView", std::int64_t{ 3 } }, { "componentType", std::int64_t{ 5120 } }, { "count", std::int64_t{ 3 } }, { "type", "VEC3" }, { "normalized", true } });
	(*stFixture.Primitive()["attributes"].GetObject())["TEXCOORD_0"] = std::int64_t{ 2 };
	(*stFixture.Primitive()["attributes"].GetObject())["NORMAL"] = std::int64_t{ 3 };
	DecodedMesh stMesh;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh));
	ENGINE_NEXT_CHECK_FLOAT(stMesh.arrPrimitives[0].arrVertices[1].arrTexcoord[0], 1.0F);
	ENGINE_NEXT_CHECK_FLOAT(stMesh.arrPrimitives[0].arrVertices[2].arrTexcoord[1], 1.0F);
	ENGINE_NEXT_CHECK_FLOAT(stMesh.arrPrimitives[0].arrVertices[0].arrNormal[2], 1.0F);
	ENGINE_NEXT_CHECK_FLOAT(stMesh.arrPrimitives[0].arrVertices[0].arrTangent[0], 1.0F);
}

ENGINE_NEXT_TEST("GLB rendering decoder preserves embedded image bytes and sampler settings")
{
	GlbFixture stFixture;
	const std::vector<std::uint8_t> arrImage = EngineNext::Tests::Assets::ReadFixture("valid.png");
	ENGINE_NEXT_CHECK(!arrImage.empty());
	stFixture.arrBinary.insert(stFixture.arrBinary.end(), arrImage.begin(), arrImage.end());
	stFixture.mapRoot["bufferViews"].GetList()->push_back(JsonValue::Object{ { "buffer", std::int64_t{ 0 } }, { "byteOffset", std::int64_t{ 40 } }, { "byteLength", static_cast<std::int64_t>(arrImage.size()) } });
	stFixture.mapRoot["images"] = JsonValue::List{ JsonValue::Object{ { "bufferView", std::int64_t{ 2 } }, { "mimeType", "image/png" } } };
	stFixture.mapRoot["samplers"] = JsonValue::List{ JsonValue::Object{ { "magFilter", std::int64_t{ 9728 } }, { "minFilter", std::int64_t{ 9987 } }, { "wrapS", std::int64_t{ 33071 } } } };
	stFixture.mapRoot["textures"] = JsonValue::List{ JsonValue::Object{ { "source", std::int64_t{ 0 } }, { "sampler", std::int64_t{ 0 } } } };
	DecodedMesh stMesh;
	ENGINE_NEXT_CHECK(Decode(stFixture, stMesh));
	ENGINE_NEXT_CHECK_EQ(stMesh.arrImages[0].arrBytes, arrImage);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrTextures[0].nImage, 0U);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrTextures[0].nWrapS, 33071);
	ENGINE_NEXT_CHECK_EQ(stMesh.arrTextures[0].nMinFilter, 9987);
}

ENGINE_NEXT_TEST("RenderScene preserves M3 identities and composes entity and GLB node transforms")
{
	GlbFixture stFixture;
	stFixture.mapRoot["nodes"] = JsonValue::List{ JsonValue::Object{ { "mesh", std::int64_t{ 0 } }, { "translation", JsonValue::List{ 7.0, 0.0, 0.0 } } } };
	const EngineNext::Assets::PackageData stPackage = Package(stFixture);
	EngineNext::Rendering::RenderScene stScene;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildRenderScene(stPackage, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stScene.arrInstances.size(), 1U);
	ENGINE_NEXT_CHECK_EQ(stScene.arrInstances[0].nEntityId, 2U);
	ENGINE_NEXT_CHECK_EQ(stScene.arrInstances[0].arrTransform[12], 14.0);
	ENGINE_NEXT_CHECK_EQ(stScene.arrInstances[0].arrTransform[13], 3.0);
	ENGINE_NEXT_CHECK_EQ(stScene.arrAssets[0].stIdentity.strAssetId, "m42.mesh");
	ENGINE_NEXT_CHECK_EQ(stScene.arrAssets[0].stIdentity.strRevision, "r1");
	ENGINE_NEXT_CHECK_EQ(stScene.strPackageDigest, stPackage.strPackageDigest);
}

ENGINE_NEXT_TEST("RenderScene rejects missing and changed blobs without replacing prior scene")
{
	GlbFixture stFixture;
	EngineNext::Assets::PackageData stPackage = Package(stFixture);
	EngineNext::Rendering::RenderScene stScene;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildRenderScene(stPackage, stScene, arrDiagnostics));
	// Change valid vertex data, leaving GLB syntax intact and its old hash stale.
	const std::uint32_t nJsonBytes = static_cast<std::uint32_t>(stPackage.mapBlobs.begin()->second[12]) | (static_cast<std::uint32_t>(stPackage.mapBlobs.begin()->second[13]) << 8U) |
			(static_cast<std::uint32_t>(stPackage.mapBlobs.begin()->second[14]) << 16U) | (static_cast<std::uint32_t>(stPackage.mapBlobs.begin()->second[15]) << 24U);
	stPackage.mapBlobs.begin()->second[28 + nJsonBytes] ^= 1;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildRenderScene(stPackage, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stScene.arrInstances.size(), 1U);
	stPackage.mapBlobs.clear();
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildRenderScene(stPackage, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stScene.arrAssets[0].stIdentity.strAssetId, "m42.mesh");
}

ENGINE_NEXT_TEST("RenderScene rejects a stale package identity without replacing prior output")
{
	GlbFixture stFixture;
	EngineNext::Assets::PackageData stPackage = Package(stFixture);
	EngineNext::Rendering::RenderScene stScene;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildRenderScene(stPackage, stScene, arrDiagnostics));
	const std::string strAccepted = stScene.strPackageDigest;
	stPackage.strPackageDigest = std::string(64, 'a');
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildRenderScene(stPackage, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stScene.strPackageDigest, strAccepted);
	ENGINE_NEXT_CHECK_EQ(stScene.arrInstances.size(), 1U);
}

ENGINE_NEXT_TEST("RenderScene rejects invalid scene identities and cycles before world traversal")
{
	GlbFixture stFixture;
	EngineNext::Assets::PackageData stPackage = Package(stFixture);
	EngineNext::Rendering::RenderScene stScene;
	EngineNext::Assets::Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::BuildRenderScene(stPackage, stScene, arrDiagnostics));
	stPackage.stScene.arrEntities[0].nEntityId = -1;
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildRenderScene(stPackage, stScene, arrDiagnostics));
	stPackage = Package(stFixture);
	stPackage.stScene.arrEntities[0].nParentEntityId = 2;
	std::string strSceneJson;
	ENGINE_NEXT_CHECK(EngineNext::Serialization::CanonicalJson(EngineNext::Assets::ToJson(stPackage.stScene), strSceneJson));
	stPackage.stManifest.strSceneContentSha256 = EngineNext::Serialization::Sha256Hex(strSceneJson);
	stPackage.strManifestJson.clear();
	stPackage.strSceneJson.clear();
	ENGINE_NEXT_CHECK(EngineNext::Assets::ComputePackageDigest(stPackage, arrDiagnostics));
	ENGINE_NEXT_CHECK(!EngineNext::Rendering::BuildRenderScene(stPackage, stScene, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stScene.arrInstances[0].nEntityId, 2U);
}
