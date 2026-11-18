/**************************************************************************/
/*  TestLodSelection.cpp                                                  */
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

#include "engine_next/include/EngineNext/Rendering/GeometryLod.h"
#include "engine_next/Tests/TestFramework.h"

#include <array>
#include <cmath>
#include <limits>
#include <vector>

namespace
{
using EngineNext::Assets::Diagnostics;
using EngineNext::Rendering::LodNode;
using EngineNext::Rendering::LodSelection;
using EngineNext::Rendering::LodView;
using EngineNext::Rendering::SelectLodCut;
std::vector<LodNode> Tree()
{
	std::vector<LodNode> arrNodes(7);
	for (std::uint32_t nIndex = 0; nIndex < arrNodes.size(); ++nIndex)
	{
		arrNodes[nIndex].arrMinimum = { -1, -1, -1 };
		arrNodes[nIndex].arrMaximum = { 1, 1, 1 };
		arrNodes[nIndex].nPage = nIndex;
	}
	arrNodes[0].nFirstChild = 1;
	arrNodes[0].nChildCount = 2;
	arrNodes[0].dGeometricErrorBound = 2;
	arrNodes[1].nFirstChild = 3;
	arrNodes[1].nChildCount = 2;
	arrNodes[1].dGeometricErrorBound = 1;
	arrNodes[2].nFirstChild = 5;
	arrNodes[2].nChildCount = 2;
	arrNodes[2].dGeometricErrorBound = 1;
	return arrNodes;
}
LodView View()
{
	LodView stView;
	stView.arrPosition = { 0, 0, 10 };
	stView.dProjectionPixels = 100;
	stView.dMaximumErrorPixels = 5;
	return stView;
}
void Cover(std::uint32_t nNode, const std::vector<LodNode> &arrNodes, std::array<std::uint32_t, 7> &out_arrCover)
{
	const LodNode &stNode = arrNodes[nNode];
	if (stNode.nChildCount == 0)
	{
		++out_arrCover[nNode];
		return;
	}
	for (std::uint32_t nChild = stNode.nFirstChild; nChild < stNode.nFirstChild + stNode.nChildCount; ++nChild)
	{
		Cover(nChild, arrNodes, out_arrCover);
	}
}
} //namespace
ENGINE_NEXT_TEST("LOD projected error selects a complete stable cut")
{
	const std::vector<LodNode> arrNodes = Tree();
	LodSelection stOutput;
	Diagnostics arrDiagnostics;
	LodView stView = View();
	ENGINE_NEXT_CHECK(SelectLodCut(arrNodes, { 0 }, std::vector<std::uint8_t>(7, 1), stView, 7, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrNodes, (std::vector<std::uint32_t>{ 3, 4, 5, 6 }));
	ENGINE_NEXT_CHECK_EQ(stOutput.dMaximumSelectedErrorPixels, 0.0);
	stView.arrPosition[2] = 1000;
	ENGINE_NEXT_CHECK(SelectLodCut(arrNodes, { 0 }, std::vector<std::uint8_t>(7, 1), stView, 7, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrNodes, (std::vector<std::uint32_t>{ 0 }));
	ENGINE_NEXT_CHECK(stOutput.dMaximumSelectedErrorPixels < stView.dMaximumErrorPixels);
	stView.arrPosition = { 0, 0, 0 };
	ENGINE_NEXT_CHECK(SelectLodCut(arrNodes, { 0 }, std::vector<std::uint8_t>(7, 1), stView, 7, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrNodes, (std::vector<std::uint32_t>{ 3, 4, 5, 6 }));
}
ENGINE_NEXT_TEST("LOD missing child pages retain the resident parent")
{
	const std::vector<LodNode> arrNodes = Tree();
	std::vector<std::uint8_t> arrResident(7, 1);
	arrResident[1] = 0;
	LodSelection stOutput;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(SelectLodCut(arrNodes, { 0 }, arrResident, View(), 7, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrNodes, (std::vector<std::uint32_t>{ 0 }));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrRequestedPages, (std::vector<std::uint32_t>{ 1 }));
	ENGINE_NEXT_CHECK(stOutput.bResidencyLimited);
	arrResident[1] = 1;
	arrResident[4] = 0;
	ENGINE_NEXT_CHECK(SelectLodCut(arrNodes, { 0 }, arrResident, View(), 7, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrNodes, (std::vector<std::uint32_t>{ 1, 5, 6 }));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrRequestedPages, (std::vector<std::uint32_t>{ 4 }));
}
ENGINE_NEXT_TEST("LOD capacity uses full parent fallback and deterministic priority")
{
	LodSelection stOutput;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(SelectLodCut(Tree(), { 0 }, std::vector<std::uint8_t>(7, 1), View(), 1, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrNodes, (std::vector<std::uint32_t>{ 0 }));
	ENGINE_NEXT_CHECK(stOutput.bCapacityLimited);
	ENGINE_NEXT_CHECK(SelectLodCut(Tree(), { 0 }, std::vector<std::uint8_t>(7, 1), View(), 3, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrNodes, (std::vector<std::uint32_t>{ 2, 3, 4 }));
	ENGINE_NEXT_CHECK(stOutput.bCapacityLimited);
}
ENGINE_NEXT_TEST("LOD every residency and capacity case covers each leaf once")
{
	const std::vector<LodNode> arrNodes = Tree();
	Diagnostics arrDiagnostics;
	for (std::uint32_t nMask = 0; nMask < 64; ++nMask)
	{
		std::vector<std::uint8_t> arrResident(7, 1);
		for (std::uint32_t nIndex = 1; nIndex < 7; ++nIndex)
		{
			arrResident[nIndex] = static_cast<std::uint8_t>((nMask >> (nIndex - 1)) & 1);
		}
		for (std::uint32_t nCapacity = 1; nCapacity <= 7; ++nCapacity)
		{
			LodSelection stFirst, stSecond;
			ENGINE_NEXT_CHECK(SelectLodCut(arrNodes, { 0 }, arrResident, View(), nCapacity, stFirst, arrDiagnostics));
			ENGINE_NEXT_CHECK(SelectLodCut(arrNodes, { 0 }, arrResident, View(), nCapacity, stSecond, arrDiagnostics));
			ENGINE_NEXT_CHECK_EQ(stFirst.arrNodes, stSecond.arrNodes);
			ENGINE_NEXT_CHECK_EQ(stFirst.arrRequestedPages, stSecond.arrRequestedPages);
			ENGINE_NEXT_CHECK(stFirst.arrNodes.size() <= nCapacity);
			std::array<std::uint32_t, 7> arrCover{};
			for (std::uint32_t nNode : stFirst.arrNodes)
			{
				ENGINE_NEXT_CHECK(arrResident[arrNodes[nNode].nPage] != 0);
				Cover(nNode, arrNodes, arrCover);
			}
			for (std::uint32_t nLeaf = 3; nLeaf < 7; ++nLeaf)
			{
				ENGINE_NEXT_CHECK_EQ(arrCover[nLeaf], 1U);
			}
			for (std::uint32_t nPage : stFirst.arrRequestedPages)
			{
				ENGINE_NEXT_CHECK_EQ(arrResident[nPage], 0U);
			}
		}
	}
}
ENGINE_NEXT_TEST("LOD invalid forest and inputs preserve output")
{
	LodSelection stOutput;
	stOutput.arrNodes = { 99 };
	Diagnostics arrDiagnostics;
	std::vector<LodNode> arrNodes = Tree();
	std::vector<std::uint8_t> arrResident(7, 1);
	arrNodes[2].nFirstChild = 3;
	ENGINE_NEXT_CHECK(!SelectLodCut(arrNodes, { 0 }, arrResident, View(), 7, stOutput, arrDiagnostics));
	arrNodes = Tree();
	arrNodes[0].nFirstChild = 0;
	arrNodes[0].nChildCount = 1;
	ENGINE_NEXT_CHECK(!SelectLodCut(arrNodes, { 0 }, arrResident, View(), 7, stOutput, arrDiagnostics));
	arrNodes = Tree();
	arrNodes[1].dGeometricErrorBound = 3;
	ENGINE_NEXT_CHECK(!SelectLodCut(arrNodes, { 0 }, arrResident, View(), 7, stOutput, arrDiagnostics));
	arrNodes = Tree();
	arrNodes[6].arrMaximum[0] = 2;
	ENGINE_NEXT_CHECK(!SelectLodCut(arrNodes, { 0 }, arrResident, View(), 7, stOutput, arrDiagnostics));
	arrNodes = Tree();
	arrNodes[6].dGeometricErrorBound = std::numeric_limits<double>::infinity();
	ENGINE_NEXT_CHECK(!SelectLodCut(arrNodes, { 0 }, arrResident, View(), 7, stOutput, arrDiagnostics));
	arrNodes = Tree();
	arrResident[0] = 0;
	ENGINE_NEXT_CHECK(!SelectLodCut(arrNodes, { 0 }, arrResident, View(), 7, stOutput, arrDiagnostics));
	arrResident[0] = 2;
	ENGINE_NEXT_CHECK(!SelectLodCut(arrNodes, { 0 }, arrResident, View(), 7, stOutput, arrDiagnostics));
	arrResident[0] = 1;
	ENGINE_NEXT_CHECK(!SelectLodCut(arrNodes, { 0 }, arrResident, View(), 0, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrNodes, (std::vector<std::uint32_t>{ 99 }));
}

ENGINE_NEXT_TEST("LOD projected error avoids intermediate underflow")
{
	std::vector<LodNode> arrNodes = Tree();
	arrNodes[0].dGeometricErrorBound = 1e-300;
	arrNodes[1].dGeometricErrorBound = 5e-301;
	arrNodes[2].dGeometricErrorBound = 5e-301;
	LodView stView = View();
	stView.arrPosition[2] = 1e38;
	stView.dProjectionPixels = 1e300;
	stView.dMaximumErrorPixels = 1e-40;
	LodSelection stOutput;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(SelectLodCut(arrNodes, { 0 }, std::vector<std::uint8_t>(7, 1), stView, 7, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrNodes, (std::vector<std::uint32_t>{ 3, 4, 5, 6 }));
}

ENGINE_NEXT_TEST("LOD perspective bound includes off-axis denominator motion")
{
	std::vector<LodNode> arrNodes = Tree();
	for (LodNode &stNode : arrNodes)
	{
		stNode.arrMinimum = { 1.7, -.1, -2.1 };
		stNode.arrMaximum = { 1.9, .1, -1.9 };
	}
	arrNodes[0].dGeometricErrorBound = .01;
	arrNodes[1].dGeometricErrorBound = .005;
	arrNodes[2].dGeometricErrorBound = .005;
	LodView stView = View();
	stView.arrPosition = { 0, 0, 0 };
	stView.dProjectionPixels = 1000;
	stView.dMaximumErrorPixels = 5;
	LodSelection stOutput;
	Diagnostics arrDiagnostics;
	ENGINE_NEXT_CHECK(SelectLodCut(arrNodes, { 0 }, std::vector<std::uint8_t>(7, 1), stView, 7, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrNodes, (std::vector<std::uint32_t>{ 3, 4, 5, 6 }));
	stView.arrForward = { 0, 0, 0 };
	ENGINE_NEXT_CHECK(!SelectLodCut(arrNodes, { 0 }, std::vector<std::uint8_t>(7, 1), stView, 7, stOutput, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stOutput.arrNodes, (std::vector<std::uint32_t>{ 3, 4, 5, 6 }));
}

ENGINE_NEXT_TEST("LOD perspective error bounds direct projected perturbations")
{
	std::vector<LodNode> arrNodes = Tree();
	for (LodNode &stNode : arrNodes)
	{
		stNode.arrMinimum = { 1, -1, -6 };
		stNode.arrMaximum = { 3, 1, -4 };
		stNode.dGeometricErrorBound = 0;
	}
	arrNodes[0].dGeometricErrorBound = .025;
	Diagnostics arrDiagnostics;
	for (double dCameraX : { 0.0, 10.0, 100.0 })
	{
		LodView stView;
		stView.arrPosition = { dCameraX, 0, 0 };
		stView.dProjectionPixels = 1500;
		stView.dMaximumErrorPixels = 1e-300;
		LodSelection stOutput;
		ENGINE_NEXT_CHECK(SelectLodCut(arrNodes, { 0 }, std::vector<std::uint8_t>(7, 1), stView, 1, stOutput, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stOutput.arrNodes, (std::vector<std::uint32_t>{ 0 }));
		for (double dX : { 1.0, 2.0, 3.0 })
		{
			for (double dY : { -1.0, 0.0, 1.0 })
			{
				for (double dZ : { -6.0, -5.0, -4.0 })
				{
					for (double dDx : { -1.0, 0.0, 1.0 })
					{
						for (double dDy : { -1.0, 0.0, 1.0 })
						{
							for (double dDz : { -1.0, 0.0, 1.0 })
							{
								const double dLength = std::hypot(dDx, dDy, dDz);
								if (dLength == 0)
								{
									continue;
								}
								const double dScale = arrNodes[0].dGeometricErrorBound / dLength;
								const double dOriginalX = (dX - dCameraX) / -dZ;
								const double dOriginalY = dY / -dZ;
								const double dChangedX = (dX + dDx * dScale - dCameraX) / -(dZ + dDz * dScale);
								const double dChangedY = (dY + dDy * dScale) / -(dZ + dDz * dScale);
								const double dErrorPixels = stView.dProjectionPixels * std::hypot(dChangedX - dOriginalX, dChangedY - dOriginalY);
								ENGINE_NEXT_CHECK(dErrorPixels <= stOutput.dMaximumSelectedErrorPixels);
							}
						}
					}
				}
			}
		}
	}
}

ENGINE_NEXT_TEST("LOD hysteresis keeps a committed cut inside its dead band")
{
	std::vector<LodNode> arrNodes(3);
	arrNodes[0].nFirstChild = 1;
	arrNodes[0].nChildCount = 2;
	arrNodes[0].dGeometricErrorBound = 1;
	for (std::uint32_t nNode = 0; nNode < 3; ++nNode)
	{
		arrNodes[nNode].nPage = nNode;
	}
	LodView stView = View();
	stView.dMaximumErrorPixels = 25;
	LodSelection stCut;
	Diagnostics arrDiagnostics;
	const std::vector<std::uint8_t> arrResident(3, 1);
	ENGINE_NEXT_CHECK(EngineNext::Rendering::SelectLodCutWithHistory(arrNodes, { 0 }, arrResident, stView, 3, { 0 }, .1, stCut, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCut.arrNodes, (std::vector<std::uint32_t>{ 0 }));
	ENGINE_NEXT_CHECK(EngineNext::Rendering::SelectLodCutWithHistory(arrNodes, { 0 }, arrResident, stView, 3, { 1, 2 }, .1, stCut, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCut.arrNodes, (std::vector<std::uint32_t>{ 1, 2 }));
	stView.arrPosition[2] = 100;
	ENGINE_NEXT_CHECK(EngineNext::Rendering::SelectLodCutWithHistory(arrNodes, { 0 }, arrResident, stView, 3, { 1, 2 }, .1, stCut, arrDiagnostics));
	ENGINE_NEXT_CHECK_EQ(stCut.arrNodes, (std::vector<std::uint32_t>{ 0 }));
}

ENGINE_NEXT_TEST("LOD hysteresis rejects incomplete or overlapping previous cuts transactionally")
{
	const std::vector<LodNode> arrNodes = Tree();
	LodSelection stCut;
	stCut.arrNodes = { 99 };
	Diagnostics arrDiagnostics;
	for (const std::vector<std::uint32_t> &arrPrevious : { std::vector<std::uint32_t>{ 0, 1 }, { 1 }, { 99 }, { 0, 0 } })
	{
		ENGINE_NEXT_CHECK(!EngineNext::Rendering::SelectLodCutWithHistory(arrNodes, { 0 }, std::vector<std::uint8_t>(7, 1), View(), 7, arrPrevious, .1, stCut, arrDiagnostics));
		ENGINE_NEXT_CHECK_EQ(stCut.arrNodes, (std::vector<std::uint32_t>{ 99 }));
	}
}
