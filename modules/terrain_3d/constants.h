// Copyright © 2023-2026 Cory Petkovsek, Roope Palmroos, and Contributors.

#ifndef CONSTANTS_CLASS_H
#define CONSTANTS_CLASS_H

#include <functional>
#include <array>
#include "core/math/math_funcs_binary.h"
#include "core/object/callable_mp.h"
#include "core/variant/typed_array.h"
#include "core/string/print_string.h"
#include "core/object/class_db.h"
#include "core/variant/variant_utility.h"

#include "core/io/image.h"
#include "core/math/color.h"
#include "core/math/vector2.h"
#include "core/math/vector2i.h"
#include "core/math/vector3.h"



template <typename... Args>
inline String VformatTerrainArgs(const Args &...stArgs)
{
	Variant arrParts[] = { Variant(stArgs)... };
	return stringify_variants(Span(arrParts));
}

// Engine Shortcuts
#define TERRAIN_RS RenderingServer::get_singleton()
#define TERRAIN_PS PhysicsServer3D::get_singleton()
#define IS_EDITOR Engine::get_singleton()->is_editor_hint()

// Constants
static const Color COLOR_NAN{ NAN, NAN, NAN, NAN };
static const Color COLOR_WHITE{ 1.0f, 1.0f, 1.0f, 1.0f };
#define COLOR_BLACK Color(0.0f, 0.0f, 0.0f, 1.0f)
#define COLOR_ROUGHNESS Color(1.0f, 1.0f, 1.0f, 0.5f)
#define COLOR_CHECKED Color(1.f, 1.f, 1.0f, -1.0f)
#define COLOR_NORMAL Color(0.5f, 0.5f, 1.0f, 1.0f)
#define COLOR_CONTROL Color(as_float(enc_auto(true)), 0.f, 0.f, 1.0f)

// Enums

enum CompressMode {
	COMPRESS_NONE = Image::COMPRESS_MAX,
	COMPRESS_S3TC = Image::COMPRESS_S3TC,
	COMPRESS_BPTC = Image::COMPRESS_BPTC,
	COMPRESS_ETC = Image::COMPRESS_ETC,
	COMPRESS_ETC2 = Image::COMPRESS_ETC2,
	COMPRESS_ASTC = Image::COMPRESS_ASTC,
};
VARIANT_ENUM_CAST(CompressMode);

// For consistency between MSVC, gcc, clang
#ifndef FLT_MAX
#define FLT_MAX __FLT_MAX__
#endif

// Terrain3D::_warnings is uint8_t
#define WARN_MISMATCHED_SIZE 0x01
#define WARN_MISMATCHED_FORMAT 0x02
#define WARN_MISMATCHED_MIPMAPS 0x04
#define WARN_ALL 0xFF

// Global Types

#define V2(x) Vector2(x, x)
#define V2I(x) Vector2i(x, x)
#define V3(x) Vector3(x, x, x)
static const Vector2 V2_ZERO{ 0.f, 0.f };
static const Vector2 V2_MAX{ FLT_MAX, FLT_MAX };
static const Vector2i V2I_ZERO{ 0, 0 };
static const Vector2i V2I_MAX{ INT32_MAX, INT32_MAX };
static const Vector2i V2I_MIN{ INT32_MIN, INT32_MIN };
static const Vector3 V3_ZERO{ 0.f, 0.f, 0.f };
static const Vector3 V3_MAX{ FLT_MAX, FLT_MAX, FLT_MAX };
static const Vector3 V3_NAN{ NAN, NAN, NAN };
static const Vector3 V3_UP{ 0.f, 1.f, 0.f };
//static const Vector3 V3_DOWN{ 0.f, -1.f, 0.f };

struct Vector2iHash {
	std::size_t operator()(const Vector2i &v) const {
		std::size_t h1 = std::hash<int>()(v.x);
		std::size_t h2 = std::hash<int>()(v.y);
		return h1 ^ (h2 << 1);
	}
};

struct PairVector2iIntHash {
	std::size_t operator()(const std::pair<Vector2i, int> &p) const {
		std::size_t h1 = Vector2iHash{}(p.first);
		std::size_t h2 = std::hash<int>{}(p.second);
		return h1 ^ (h2 << 1);
	}
};

struct Vector3Hash {
	std::size_t operator()(const Vector3 &v) const {
		std::size_t h1 = std::hash<float>()(v.x);
		std::size_t h2 = std::hash<float>()(v.y);
		std::size_t h3 = std::hash<float>()(v.z);
		return h1 ^ (h2 << 1) ^ (h3 << 2);
	}
};

// Set class name for logger.h

#define CLASS_NAME() const String __class__ = String(get_class_static()) + \
		String("#") + String::num_uint64(get_instance_id()).right(4);

#define CLASS_NAME_STATIC(p_name) static inline const char *__class__ = p_name;

// Validation macros

#define ASSERT(cond, ret) \
	if (!(cond)) { \
		ERR_PRINT(VformatTerrainArgs("Assertion '", #cond, "' failed at ", __FILE__, ":", __LINE__)); \
		return ret; \
	}

#define VOID // a return value for void, to avoid compiler warnings

#define IS_INIT(ret) \
	if (!_terrain) { \
		return ret; \
	}

#define IS_INIT_MESG(mesg, ret) \
	if (!_terrain) { \
		LOG(ERROR, mesg); \
		return ret; \
	}

#define IS_INIT_COND(cond, ret) \
	if (!_terrain || cond) { \
		return ret; \
	}

#define IS_INIT_COND_MESG(cond, mesg, ret) \
	if (!_terrain || cond) { \
		LOG(ERROR, mesg); \
		return ret; \
	}

#define IS_INSTANCER_INIT(ret) \
	if (!_terrain || !_terrain->get_instancer()) { \
		return ret; \
	}

#define IS_INSTANCER_INIT_MESG(mesg, ret) \
	if (!_terrain || !_terrain->get_instancer()) { \
		LOG(ERROR, mesg); \
		return ret; \
	}

#define IS_DATA_INIT(ret) \
	if (!_terrain || !_terrain->get_data()) { \
		return ret; \
	}

#define IS_DATA_INIT_MESG(mesg, ret) \
	if (!_terrain || !_terrain->get_data()) { \
		LOG(ERROR, mesg); \
		return ret; \
	}

#endif // CONSTANTS_CLASS_H