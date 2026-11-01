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
[GodotClassName("TextureStreaming")]
public partial class TextureStreamingInstance : GodotObject
{
    /// <summary>
    /// <para>Overrides the minimum LOD (mipmap level) that textures start at when loaded. Higher values result in lower initial resolution. Valid values are <c>0</c> (full resolution) to <c>13</c> (lowest resolution). Values outside that range clear the override and use the default from <c>ProjectSettings.rendering/textures/streaming/min_lod</c>; when no override is active this property returns <c>-1</c>.</para>
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

    /// <summary>
    /// <para>Overrides the maximum LOD (mipmap level) that can be loaded for streamed textures at runtime. Lower values allow higher resolution textures. Valid values are <c>0</c> (full resolution) to <c>13</c> (lowest resolution). Values outside that range clear the override and use the default from <c>ProjectSettings.rendering/textures/streaming/max_lod</c>; when no override is active this property returns <c>-1</c>.</para>
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
    /// <para>Overrides the memory budget for streamed textures at runtime (in megabytes). When the budget is exceeded, the system reduces texture resolution to stay within the limit. A value of <c>UINT32_MAX</c> (<c>4294967295</c>, the maximum unsigned 32-bit integer) disables the override and uses the default from <c>ProjectSettings.rendering/textures/streaming/memory_budget_mb</c>.</para>
    /// </summary>
    public uint MemoryBudgetMbOverride
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

    private static readonly System.Type CachedType = typeof(TextureStreamingInstance);

    private static readonly StringName NativeName = "TextureStreaming";

    internal TextureStreamingInstance() : this(false)
    {
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal TextureStreamingInstance(IntPtr ptr) : this(false)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: false);
        }
    }

    internal TextureStreamingInstance(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMinLodOverride, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetMinLodOverride()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind0, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMinLodOverride, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMinLodOverride(int minLod)
    {
        NativeCalls.godot_icall_1_38(MethodBind1, GodotObject.GetPtr(this), minLod);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMaxLodOverride, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetMaxLodOverride()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind2, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMaxLodOverride, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMaxLodOverride(int maxLod)
    {
        NativeCalls.godot_icall_1_38(MethodBind3, GodotObject.GetPtr(this), maxLod);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMemoryBudgetMbOverride, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public uint GetMemoryBudgetMbOverride()
    {
        uint ret = NativeCalls.godot_icall_0_235(MethodBind4, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMemoryBudgetMbOverride, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMemoryBudgetMbOverride(uint mb)
    {
        NativeCalls.godot_icall_1_234(MethodBind5, GodotObject.GetPtr(this), mb);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMemoryBudgetBytesUsed, 2455072627ul);

    /// <summary>
    /// <para>Returns the current VRAM usage of streamed textures in bytes. This represents the total memory consumed by all streamed textures at their currently loaded mipmap levels.</para>
    /// </summary>
    public ulong GetMemoryBudgetBytesUsed()
    {
        ulong ret = NativeCalls.godot_icall_0_162(MethodBind6, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.FlushTextureStreaming, 3218959716ul);

    /// <summary>
    /// <para>Forces all currently queued texture streaming operations to complete immediately, bypassing the normal gradual transition and I/O throttling. This immediately loads or unloads mipmap levels to reach the target resolution for all managed textures, then emits the <see cref="Godot.TextureStreamingInstance.FlushCompleted"/> signal. Useful during loading screens or when teleporting the player to ensure all textures are at their optimal resolution without a visible transition.</para>
    /// </summary>
    public void FlushTextureStreaming()
    {
        NativeCalls.godot_icall_0_3(MethodBind7, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
    }

    /// <summary>
    /// <para>Emitted when a texture streaming flush operation finishes, after <see cref="Godot.TextureStreamingInstance.FlushTextureStreaming()"/> has been called and all managed textures have reached their target resolutions.</para>
    /// </summary>
    public event Action FlushCompleted
    {
        add => Connect(SignalName.FlushCompleted, Callable.From(value));
        remove => Disconnect(SignalName.FlushCompleted, Callable.From(value));
    }

    protected void EmitSignalFlushCompleted()
    {
        EmitSignal(SignalName.FlushCompleted);
    }

    // ReSharper disable once InconsistentNaming
    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly StringName SignalProxyName_flush_completed = "FlushCompleted";

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
        if (signal == SignalName.FlushCompleted)
        {
            if (HasGodotClassSignal(SignalProxyName_flush_completed.NativeValue.DangerousSelfRef))
            {
                return true;
            }
        }
        return base.HasGodotClassSignal(signal);
    }

    /// <summary>
    /// Cached StringNames for the properties and fields contained in this class, for fast lookup.
    /// </summary>
    public new class PropertyName : GodotObject.PropertyName
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
    public new class MethodName : GodotObject.MethodName
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
    public new class SignalName : GodotObject.SignalName
    {
        /// <summary>
        /// Cached name for the 'flush_completed' signal.
        /// </summary>
        public static readonly StringName FlushCompleted = "flush_completed";
    }
}
