def can_build(env, platform):
    return not env["disable_3d"]


def configure(env):
    env.module_add_dependencies("terrain_3d", ["noise"])
    if env.editor_build:
        env.module_add_dependencies("terrain_3d", ["gdscript", "svg", "tinyexr"])


def get_doc_classes():
    return [
        "Terrain3D",
        "Terrain3DAssetResource",
        "Terrain3DAssets",
        "Terrain3DCollision",
        "Terrain3DData",
        "Terrain3DEditor",
        "Terrain3DInstancer",
        "Terrain3DMaterial",
        "Terrain3DMeshAsset",
        "Terrain3DRegion",
        "Terrain3DTextureAsset",
        "Terrain3DUtil",
    ]


def get_doc_path():
    return "doc_classes"


def get_icons_path():
    return "editor/class_icons"
