namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>A "limiter" is an audio effect designed to stop audio signals from exceeding a specified volume threshold level, and usually works by decreasing the volume or soft-clipping the audio. Adding one in the Master bus is always recommended to prevent clipping when the volume goes above 0 dB.</para>
/// <para>Soft clipping starts to decrease the peaks a little below the volume threshold level and progressively increases its effect as the input volume increases such that the threshold level is never exceeded.</para>
/// <para>If hard clipping is desired, consider <see cref="Godot.AudioEffectDistortion.ModeEnum.Clip"/>.</para>
/// </summary>
[Obsolete("Use 'AudioEffectHardLimiter' instead.")]
public partial class AudioEffectLimiter : AudioEffect
{
    /// <summary>
    /// <para>The waveform's maximum allowed value, in dB. Value can range from -20 to -0.1.</para>
    /// </summary>
    public float CeilingDb
    {
        get
        {
            return GetCeilingDb();
        }
        set
        {
            SetCeilingDb(value);
        }
    }

    /// <summary>
    /// <para>The volume threshold level from which the limiter begins to be active, in dB. Value can range from -30 to 0.</para>
    /// </summary>
    public float ThresholdDb
    {
        get
        {
            return GetThresholdDb();
        }
        set
        {
            SetThresholdDb(value);
        }
    }

    /// <summary>
    /// <para>Modifies the volume of the limited waves, in dB. Value can range from 0 to 6.</para>
    /// </summary>
    public float SoftClipDb
    {
        get
        {
            return GetSoftClipDb();
        }
        set
        {
            SetSoftClipDb(value);
        }
    }

    /// <summary>
    /// <para>This property has no effect on the audio. Use <see cref="Godot.AudioEffectHardLimiter"/> instead, as this Limiter effect is deprecated.</para>
    /// </summary>
    public float SoftClipRatio
    {
        get
        {
            return GetSoftClipRatio();
        }
        set
        {
            SetSoftClipRatio(value);
        }
    }

    private static readonly System.Type CachedType = typeof(AudioEffectLimiter);

    private static readonly StringName NativeName = "AudioEffectLimiter";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public AudioEffectLimiter() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal AudioEffectLimiter(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal AudioEffectLimiter(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetCeilingDb, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetCeilingDb(float ceiling)
    {
        NativeCalls.godot_icall_1_91(MethodBind0, GodotObject.GetPtr(this), ceiling);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetCeilingDb, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetCeilingDb()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetThresholdDb, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetThresholdDb(float threshold)
    {
        NativeCalls.godot_icall_1_91(MethodBind2, GodotObject.GetPtr(this), threshold);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetThresholdDb, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetThresholdDb()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetSoftClipDb, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetSoftClipDb(float softClip)
    {
        NativeCalls.godot_icall_1_91(MethodBind4, GodotObject.GetPtr(this), softClip);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSoftClipDb, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetSoftClipDb()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind5, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetSoftClipRatio, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetSoftClipRatio(float softClip)
    {
        NativeCalls.godot_icall_1_91(MethodBind6, GodotObject.GetPtr(this), softClip);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSoftClipRatio, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetSoftClipRatio()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind7, GodotObject.GetPtr(this));
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
    public new class PropertyName : AudioEffect.PropertyName
    {
        /// <summary>
        /// Cached name for the 'ceiling_db' property.
        /// </summary>
        public static readonly StringName CeilingDb = "ceiling_db";
        /// <summary>
        /// Cached name for the 'threshold_db' property.
        /// </summary>
        public static readonly StringName ThresholdDb = "threshold_db";
        /// <summary>
        /// Cached name for the 'soft_clip_db' property.
        /// </summary>
        public static readonly StringName SoftClipDb = "soft_clip_db";
        /// <summary>
        /// Cached name for the 'soft_clip_ratio' property.
        /// </summary>
        public static readonly StringName SoftClipRatio = "soft_clip_ratio";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : AudioEffect.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_ceiling_db' method.
        /// </summary>
        public static readonly StringName SetCeilingDb = "set_ceiling_db";
        /// <summary>
        /// Cached name for the 'get_ceiling_db' method.
        /// </summary>
        public static readonly StringName GetCeilingDb = "get_ceiling_db";
        /// <summary>
        /// Cached name for the 'set_threshold_db' method.
        /// </summary>
        public static readonly StringName SetThresholdDb = "set_threshold_db";
        /// <summary>
        /// Cached name for the 'get_threshold_db' method.
        /// </summary>
        public static readonly StringName GetThresholdDb = "get_threshold_db";
        /// <summary>
        /// Cached name for the 'set_soft_clip_db' method.
        /// </summary>
        public static readonly StringName SetSoftClipDb = "set_soft_clip_db";
        /// <summary>
        /// Cached name for the 'get_soft_clip_db' method.
        /// </summary>
        public static readonly StringName GetSoftClipDb = "get_soft_clip_db";
        /// <summary>
        /// Cached name for the 'set_soft_clip_ratio' method.
        /// </summary>
        public static readonly StringName SetSoftClipRatio = "set_soft_clip_ratio";
        /// <summary>
        /// Cached name for the 'get_soft_clip_ratio' method.
        /// </summary>
        public static readonly StringName GetSoftClipRatio = "get_soft_clip_ratio";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : AudioEffect.SignalName
    {
    }
}
