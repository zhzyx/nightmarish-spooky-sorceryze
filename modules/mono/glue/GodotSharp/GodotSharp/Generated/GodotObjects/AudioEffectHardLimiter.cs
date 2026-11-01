namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>A "limiter" disallows audio signals from exceeding a given volume threshold level in dB. Hard limiters predict volume peaks, and will smoothly apply gain reduction when a peak crosses the ceiling threshold level to prevent clipping. It preserves the waveform and prevents it from crossing the ceiling threshold level. Adding one in the Master bus is recommended as a safety measure to prevent sudden volume peaks from occurring, and to prevent distortion caused by clipping, when the volume exceeds 0 dB.</para>
/// <para>If clipping is desired, consider <see cref="Godot.AudioEffectDistortion.ModeEnum.Clip"/>.</para>
/// </summary>
public partial class AudioEffectHardLimiter : AudioEffect
{
    /// <summary>
    /// <para>Gain before limiting, in dB. Value can range from -24 to 24.</para>
    /// </summary>
    public float PreGainDb
    {
        get
        {
            return GetPreGainDb();
        }
        set
        {
            SetPreGainDb(value);
        }
    }

    /// <summary>
    /// <para>The waveform's maximum allowed value, in dB. This value can range from -24 to 0.</para>
    /// <para>The default value of -0.3 prevents potential inter-sample peaks (ISP) from crossing over 0 dB, which can cause slight distortion on some older hardware.</para>
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
    /// <para>Time it takes in seconds for the gain reduction to fully release. Value can range from 0.01 to 3.</para>
    /// </summary>
    public float Release
    {
        get
        {
            return GetRelease();
        }
        set
        {
            SetRelease(value);
        }
    }

    private static readonly System.Type CachedType = typeof(AudioEffectHardLimiter);

    private static readonly StringName NativeName = "AudioEffectHardLimiter";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public AudioEffectHardLimiter() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal AudioEffectHardLimiter(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal AudioEffectHardLimiter(bool memoryOwn) : base(memoryOwn) { }

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
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetPreGainDb, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetPreGainDb(float preGain)
    {
        NativeCalls.godot_icall_1_91(MethodBind2, GodotObject.GetPtr(this), preGain);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetPreGainDb, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetPreGainDb()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetRelease, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetRelease(float release)
    {
        NativeCalls.godot_icall_1_91(MethodBind4, GodotObject.GetPtr(this), release);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetRelease, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetRelease()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind5, GodotObject.GetPtr(this));
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
        /// Cached name for the 'pre_gain_db' property.
        /// </summary>
        public static readonly StringName PreGainDb = "pre_gain_db";
        /// <summary>
        /// Cached name for the 'ceiling_db' property.
        /// </summary>
        public static readonly StringName CeilingDb = "ceiling_db";
        /// <summary>
        /// Cached name for the 'release' property.
        /// </summary>
        public static readonly StringName Release = "release";
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
        /// Cached name for the 'set_pre_gain_db' method.
        /// </summary>
        public static readonly StringName SetPreGainDb = "set_pre_gain_db";
        /// <summary>
        /// Cached name for the 'get_pre_gain_db' method.
        /// </summary>
        public static readonly StringName GetPreGainDb = "get_pre_gain_db";
        /// <summary>
        /// Cached name for the 'set_release' method.
        /// </summary>
        public static readonly StringName SetRelease = "set_release";
        /// <summary>
        /// Cached name for the 'get_release' method.
        /// </summary>
        public static readonly StringName GetRelease = "get_release";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : AudioEffect.SignalName
    {
    }
}
