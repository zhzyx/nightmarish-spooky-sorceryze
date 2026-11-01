namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>StreamedTexture2D is a texture type that supports dynamic mipmap streaming. When texture streaming is enabled in the Project Settings (<c>ProjectSettings.rendering/textures/streaming/enabled</c>), these textures can have their mipmap levels dynamically loaded and unloaded based on usage.</para>
/// <para>The texture streaming system monitors which textures are visible in each frame and at what resolution they're being displayed. Textures that are far from the camera or not currently visible have their higher-resolution mipmap levels unloaded to save VRAM, while textures being displayed up close are loaded at higher resolutions.</para>
/// <para>This texture type is automatically created when importing images with the streaming-compatible importer.</para>
/// </summary>
public partial class StreamedTexture2D : Texture2D
{
    /// <summary>
    /// <para>The <see cref="Godot.StreamedTexture2D"/>'s file path to a <c>.stex</c> file.</para>
    /// </summary>
    public string LoadPath
    {
        get
        {
            return GetLoadPath();
        }
        set
        {
            Load(value);
        }
    }

    /// <summary>
    /// <para>Overrides the maximum LOD (mipmap level) that can be loaded for this specific texture. Lower values allow higher resolution. A value of <c>0</c> uses the global setting from <c>ProjectSettings.rendering/textures/streaming/max_lod</c>. Values <c>1</c> to <c>14</c> correspond to LOD levels <c>0</c> to <c>13</c>.</para>
    /// </summary>
    public int MaxLodOverride
    {
        get
        {
            return GetMaxLodOverride();
        }
        set
        {
            SetMaxLodOverride(value);
        }
    }

    /// <summary>
    /// <para>Overrides the minimum LOD (mipmap level) this texture starts at when loaded. Higher values result in lower initial resolution. A value of <c>0</c> uses the global setting from <c>ProjectSettings.rendering/textures/streaming/min_lod</c>. Values <c>1</c> to <c>14</c> correspond to LOD levels <c>0</c> to <c>13</c>.</para>
    /// </summary>
    public int MinLodOverride
    {
        get
        {
            return GetMinLodOverride();
        }
        set
        {
            SetMinLodOverride(value);
        }
    }

    private static readonly System.Type CachedType = typeof(StreamedTexture2D);

    private static readonly StringName NativeName = "StreamedTexture2D";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public StreamedTexture2D() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal StreamedTexture2D(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal StreamedTexture2D(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.Load, 166001499ul);

    /// <summary>
    /// <para>Loads the texture from the specified <paramref name="path"/>.</para>
    /// </summary>
    [EditorBrowsable(EditorBrowsableState.Never)]
    public Error Load(string path)
    {
        Error ret = (Error)NativeCalls.godot_icall_1_159(MethodBind0, GodotObject.GetPtr(this), path);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetLoadPath, 201670096ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public string GetLoadPath()
    {
        string ret = NativeCalls.godot_icall_0_58(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMaxLodOverride, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMaxLodOverride(int maxLod)
    {
        NativeCalls.godot_icall_1_38(MethodBind2, GodotObject.GetPtr(this), maxLod);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMaxLodOverride, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetMaxLodOverride()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMinLodOverride, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMinLodOverride(int minLod)
    {
        NativeCalls.godot_icall_1_38(MethodBind4, GodotObject.GetPtr(this), minLod);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMinLodOverride, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetMinLodOverride()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind5, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    /// <summary>
    /// Invokes the method with the given name, using the given arguments.
    /// This method is used by Godot to invoke methods from the engine side.
    /// Do not call or override this method.
    /// </summary>
    /// <param name="method">Name of the method to invoke.</param>
    /// <param name="args">Arguments to use with the invoked method.</param>
    /// <param name="ret">Value returned by the invoked method.</param>
#pragma warning disable CS0618 // Member is obsolete
    protected internal override bool InvokeGodotClassMethod(in godot_string_name method, NativeVariantPtrArgs args, out godot_variant ret)
    {
        return base.InvokeGodotClassMethod(method, args, out ret);
    }
#pragma warning restore CS0618

    /// <summary>
    /// Check if the type contains a method with the given name.
    /// This method is used by Godot to check if a method exists before invoking it.
    /// Do not call or override this method.
    /// </summary>
    /// <param name="method">Name of the method to check for.</param>

    protected internal override bool HasGodotClassMethod(in godot_string_name method)
    {
        return base.HasGodotClassMethod(method);
    }

    /// <summary>
    /// Check if the type contains a signal with the given name.
    /// This method is used by Godot to check if a signal exists before raising it.
    /// Do not call or override this method.
    /// </summary>
    /// <param name="signal">Name of the signal to check for.</param>

    protected internal override bool HasGodotClassSignal(in godot_string_name signal)
    {
        return base.HasGodotClassSignal(signal);
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public new class PropertyName : Texture2D.PropertyName
    {
        /// <summary>
        /// Cached name for the 'load_path' property.
        /// </summary>
        public static readonly StringName LoadPath = "load_path";
        /// <summary>
        /// Cached name for the 'max_lod_override' property.
        /// </summary>
        public static readonly StringName MaxLodOverride = "max_lod_override";
        /// <summary>
        /// Cached name for the 'min_lod_override' property.
        /// </summary>
        public static readonly StringName MinLodOverride = "min_lod_override";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : Texture2D.MethodName
    {
        /// <summary>
        /// Cached name for the 'load' method.
        /// </summary>
        public static readonly StringName Load = "load";
        /// <summary>
        /// Cached name for the 'get_load_path' method.
        /// </summary>
        public static readonly StringName GetLoadPath = "get_load_path";
        /// <summary>
        /// Cached name for the 'set_max_lod_override' method.
        /// </summary>
        public static readonly StringName SetMaxLodOverride = "set_max_lod_override";
        /// <summary>
        /// Cached name for the 'get_max_lod_override' method.
        /// </summary>
        public static readonly StringName GetMaxLodOverride = "get_max_lod_override";
        /// <summary>
        /// Cached name for the 'set_min_lod_override' method.
        /// </summary>
        public static readonly StringName SetMinLodOverride = "set_min_lod_override";
        /// <summary>
        /// Cached name for the 'get_min_lod_override' method.
        /// </summary>
        public static readonly StringName GetMinLodOverride = "get_min_lod_override";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : Texture2D.SignalName
    {
    }
}
