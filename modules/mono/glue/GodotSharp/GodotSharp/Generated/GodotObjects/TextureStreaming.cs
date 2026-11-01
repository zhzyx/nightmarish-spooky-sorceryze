namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>The TextureStreaming singleton manages dynamic loading and unloading of texture mipmap levels based on what is visible in the current frame. This allows projects with many large textures to significantly reduce VRAM usage while maintaining visual quality for visible textures.</para>
/// <para>Texture streaming works by analyzing shader feedback to determine which textures are actively being used and at what resolution they're being displayed. Textures that are far from the camera or not currently visible have their higher-resolution mipmap levels unloaded, while textures being displayed up close are loaded at higher resolutions.</para>
/// <para>The system includes a memory budget feature that automatically manages texture resolutions to stay within a specified VRAM limit. When the budget is exceeded, the system prioritizes textures based on how recently they were used and how much screen space they occupy.</para>
/// <para><b>Note:</b> Texture streaming must be enabled in the Project Settings (<c>ProjectSettings.rendering/textures/streaming/enabled</c>) and textures must be imported with streaming support to use this feature.</para>
/// </summary>
public static partial class TextureStreaming
{
    /// <summary>
    /// <para>Overrides the minimum LOD (mipmap level) that textures start at when loaded. Higher values result in lower initial resolution. Valid values are <c>0</c> (full resolution) to <c>13</c> (lowest resolution). Values outside that range clear the override and use the default from <c>ProjectSettings.rendering/textures/streaming/min_lod</c>; when no override is active this property returns <c>-1</c>.</para>
    /// </summary>
    public static int MinLodOverride
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

    /// <summary>
    /// <para>Overrides the maximum LOD (mipmap level) that can be loaded for streamed textures at runtime. Lower values allow higher resolution textures. Valid values are <c>0</c> (full resolution) to <c>13</c> (lowest resolution). Values outside that range clear the override and use the default from <c>ProjectSettings.rendering/textures/streaming/max_lod</c>; when no override is active this property returns <c>-1</c>.</para>
    /// </summary>
    public static int MaxLodOverride
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
    /// <para>Overrides the memory budget for streamed textures at runtime (in megabytes). When the budget is exceeded, the system reduces texture resolution to stay within the limit. A value of <c>UINT32_MAX</c> (<c>4294967295</c>, the maximum unsigned 32-bit integer) disables the override and uses the default from <c>ProjectSettings.rendering/textures/streaming/memory_budget_mb</c>.</para>
    /// </summary>
    public static uint MemoryBudgetMbOverride
    {
        get
        {
            return GetMemoryBudgetMbOverride();
        }
        set
        {
            SetMemoryBudgetMbOverride(value);
        }
    }

    private static readonly StringName NativeName = "TextureStreaming";

    private static TextureStreamingInstance singleton;

    public static TextureStreamingInstance Singleton =>
        singleton ??= (TextureStreamingInstance)InteropUtils.EngineGetSingleton("TextureStreaming");

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMinLodOverride, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public static int GetMinLodOverride()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind0, GodotObject.GetPtr(Singleton));
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMinLodOverride, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public static void SetMinLodOverride(int minLod)
    {
        NativeCalls.godot_icall_1_38(MethodBind1, GodotObject.GetPtr(Singleton), minLod);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMaxLodOverride, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public static int GetMaxLodOverride()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind2, GodotObject.GetPtr(Singleton));
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMaxLodOverride, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public static void SetMaxLodOverride(int maxLod)
    {
        NativeCalls.godot_icall_1_38(MethodBind3, GodotObject.GetPtr(Singleton), maxLod);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMemoryBudgetMbOverride, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public static uint GetMemoryBudgetMbOverride()
    {
        uint ret = NativeCalls.godot_icall_0_235(MethodBind4, GodotObject.GetPtr(Singleton));
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMemoryBudgetMbOverride, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public static void SetMemoryBudgetMbOverride(uint mb)
    {
        NativeCalls.godot_icall_1_234(MethodBind5, GodotObject.GetPtr(Singleton), mb);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMemoryBudgetBytesUsed, 2455072627ul);

    /// <summary>
    /// <para>Returns the current VRAM usage of streamed textures in bytes. This represents the total memory consumed by all streamed textures at their currently loaded mipmap levels.</para>
    /// </summary>
    public static ulong GetMemoryBudgetBytesUsed()
    {
        ulong ret = NativeCalls.godot_icall_0_162(MethodBind6, GodotObject.GetPtr(Singleton));
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = GodotObject.ClassDB_get_method_with_compatibility(NativeName, MethodName.FlushTextureStreaming, 3218959716ul);

    /// <summary>
    /// <para>Forces all currently queued texture streaming operations to complete immediately, bypassing the normal gradual transition and I/O throttling. This immediately loads or unloads mipmap levels to reach the target resolution for all managed textures, then emits the <see cref="Godot.TextureStreaming.FlushCompleted"/> signal. Useful during loading screens or when teleporting the player to ensure all textures are at their optimal resolution without a visible transition.</para>
    /// </summary>
    public static void FlushTextureStreaming()
    {
        NativeCalls.godot_icall_0_3(MethodBind7, GodotObject.GetPtr(Singleton));
    }

    /// <summary>
    /// <para>Emitted when a texture streaming flush operation finishes, after <see cref="Godot.TextureStreaming.FlushTextureStreaming()"/> has been called and all managed textures have reached their target resolutions.</para>
    /// </summary>
    public static event Action FlushCompleted
    {
        add => Singleton.Connect(SignalName.FlushCompleted, Callable.From(value));
        remove => Singleton.Disconnect(SignalName.FlushCompleted, Callable.From(value));
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public class PropertyName
    {
        /// <summary>
        /// Cached name for the 'min_lod_override' property.
        /// </summary>
        public static readonly StringName MinLodOverride = "min_lod_override";
        /// <summary>
        /// Cached name for the 'max_lod_override' property.
        /// </summary>
        public static readonly StringName MaxLodOverride = "max_lod_override";
        /// <summary>
        /// Cached name for the 'memory_budget_mb_override' property.
        /// </summary>
        public static readonly StringName MemoryBudgetMbOverride = "memory_budget_mb_override";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public class MethodName
    {
        /// <summary>
        /// Cached name for the 'get_min_lod_override' method.
        /// </summary>
        public static readonly StringName GetMinLodOverride = "get_min_lod_override";
        /// <summary>
        /// Cached name for the 'set_min_lod_override' method.
        /// </summary>
        public static readonly StringName SetMinLodOverride = "set_min_lod_override";
        /// <summary>
        /// Cached name for the 'get_max_lod_override' method.
        /// </summary>
        public static readonly StringName GetMaxLodOverride = "get_max_lod_override";
        /// <summary>
        /// Cached name for the 'set_max_lod_override' method.
        /// </summary>
        public static readonly StringName SetMaxLodOverride = "set_max_lod_override";
        /// <summary>
        /// Cached name for the 'get_memory_budget_mb_override' method.
        /// </summary>
        public static readonly StringName GetMemoryBudgetMbOverride = "get_memory_budget_mb_override";
        /// <summary>
        /// Cached name for the 'set_memory_budget_mb_override' method.
        /// </summary>
        public static readonly StringName SetMemoryBudgetMbOverride = "set_memory_budget_mb_override";
        /// <summary>
        /// Cached name for the 'get_memory_budget_bytes_used' method.
        /// </summary>
        public static readonly StringName GetMemoryBudgetBytesUsed = "get_memory_budget_bytes_used";
        /// <summary>
        /// Cached name for the 'flush_texture_streaming' method.
        /// </summary>
        public static readonly StringName FlushTextureStreaming = "flush_texture_streaming";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public class SignalName
    {
        /// <summary>
        /// Cached name for the 'flush_completed' signal.
        /// </summary>
        public static readonly StringName FlushCompleted = "flush_completed";
    }
}
