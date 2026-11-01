namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>A "compressor" decreases the volume of sounds when it exceeds a certain volume threshold level.</para>
/// <para>A compressor can have many uses in a mix:</para>
/// <para>- To compress the whole volume in the Master bus (although an <see cref="Godot.AudioEffectHardLimiter"/> is probably better).</para>
/// <para>- To ensure balance of voice audio clips.</para>
/// <para>- To sidechain, using another bus as a trigger. This decreases the volume of the bus it is attached to, by using the volume from another audio bus for threshold detection. This technique is common in video game mixing to decrease the volume of music and SFX while voices are being heard. This effect is also known as "ducking".</para>
/// <para>- To accentuate transients by using a long attack, letting sounds exceed the volume threshold level for a short period before compressing them. This can be used to make SFX more punchy.</para>
/// </summary>
public partial class AudioEffectCompressor : AudioEffect
{
    /// <summary>
    /// <para>The volume level above which compression is applied to the audio, in dB. Value can range from -60 to 0.</para>
    /// </summary>
    public float Threshold
    {
        get
        {
            return GetThreshold();
        }
        set
        {
            SetThreshold(value);
        }
    }

    /// <summary>
    /// <para>Amount of compression applied to the audio once it passes the volume threshold level. The higher the ratio, the stronger the compression applied to audio signals that pass the volume threshold level. Value can range from 1 to 48.</para>
    /// </summary>
    public float Ratio
    {
        get
        {
            return GetRatio();
        }
        set
        {
            SetRatio(value);
        }
    }

    /// <summary>
    /// <para>Gain of the audio signal, in dB. Value can range from -20 to 20.</para>
    /// </summary>
    public float Gain
    {
        get
        {
            return GetGain();
        }
        set
        {
            SetGain(value);
        }
    }

    /// <summary>
    /// <para>Compressor's reaction time when the audio exceeds the volume threshold level, in microseconds. Value can range from 20 to 2000.</para>
    /// </summary>
    public float AttackUs
    {
        get
        {
            return GetAttackUs();
        }
        set
        {
            SetAttackUs(value);
        }
    }

    /// <summary>
    /// <para>Compressor's delay time to stop decreasing the volume after the it falls below the volume threshold level, in milliseconds. Value can range from 20 to 2000.</para>
    /// </summary>
    public float ReleaseMs
    {
        get
        {
            return GetReleaseMs();
        }
        set
        {
            SetReleaseMs(value);
        }
    }

    /// <summary>
    /// <para>Balance between the original audio and the compressed audio. Value can range from 0 (totally dry) to 1 (totally wet).</para>
    /// </summary>
    public float Mix
    {
        get
        {
            return GetMix();
        }
        set
        {
            SetMix(value);
        }
    }

    /// <summary>
    /// <para>Audio bus to use for the volume threshold detection.</para>
    /// </summary>
    public StringName Sidechain
    {
        get
        {
            return GetSidechain();
        }
        set
        {
            SetSidechain(value);
        }
    }

    private static readonly System.Type CachedType = typeof(AudioEffectCompressor);

    private static readonly StringName NativeName = "AudioEffectCompressor";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public AudioEffectCompressor() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal AudioEffectCompressor(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal AudioEffectCompressor(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetThreshold, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetThreshold(float threshold)
    {
        NativeCalls.godot_icall_1_91(MethodBind0, GodotObject.GetPtr(this), threshold);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetThreshold, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetThreshold()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetRatio, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetRatio(float ratio)
    {
        NativeCalls.godot_icall_1_91(MethodBind2, GodotObject.GetPtr(this), ratio);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetRatio, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetRatio()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetGain, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetGain(float gain)
    {
        NativeCalls.godot_icall_1_91(MethodBind4, GodotObject.GetPtr(this), gain);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetGain, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetGain()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind5, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetAttackUs, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetAttackUs(float attackUs)
    {
        NativeCalls.godot_icall_1_91(MethodBind6, GodotObject.GetPtr(this), attackUs);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetAttackUs, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetAttackUs()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind7, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetReleaseMs, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetReleaseMs(float releaseMs)
    {
        NativeCalls.godot_icall_1_91(MethodBind8, GodotObject.GetPtr(this), releaseMs);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetReleaseMs, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetReleaseMs()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind9, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetMix, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetMix(float mix)
    {
        NativeCalls.godot_icall_1_91(MethodBind10, GodotObject.GetPtr(this), mix);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetMix, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetMix()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind11, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetSidechain, 3304788590ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetSidechain(StringName sidechain)
    {
        NativeCalls.godot_icall_1_88(MethodBind12, GodotObject.GetPtr(this), (godot_string_name)(sidechain?.NativeValue ?? default));
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetSidechain, 2002593661ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public StringName GetSidechain()
    {
        StringName ret = NativeCalls.godot_icall_0_89(MethodBind13, GodotObject.GetPtr(this));
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
        /// Cached name for the 'threshold' property.
        /// </summary>
        public static readonly StringName Threshold = "threshold";
        /// <summary>
        /// Cached name for the 'ratio' property.
        /// </summary>
        public static readonly StringName Ratio = "ratio";
        /// <summary>
        /// Cached name for the 'gain' property.
        /// </summary>
        public static readonly StringName Gain = "gain";
        /// <summary>
        /// Cached name for the 'attack_us' property.
        /// </summary>
        public static readonly StringName AttackUs = "attack_us";
        /// <summary>
        /// Cached name for the 'release_ms' property.
        /// </summary>
        public static readonly StringName ReleaseMs = "release_ms";
        /// <summary>
        /// Cached name for the 'mix' property.
        /// </summary>
        public static readonly StringName Mix = "mix";
        /// <summary>
        /// Cached name for the 'sidechain' property.
        /// </summary>
        public static readonly StringName Sidechain = "sidechain";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : AudioEffect.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_threshold' method.
        /// </summary>
        public static readonly StringName SetThreshold = "set_threshold";
        /// <summary>
        /// Cached name for the 'get_threshold' method.
        /// </summary>
        public static readonly StringName GetThreshold = "get_threshold";
        /// <summary>
        /// Cached name for the 'set_ratio' method.
        /// </summary>
        public static readonly StringName SetRatio = "set_ratio";
        /// <summary>
        /// Cached name for the 'get_ratio' method.
        /// </summary>
        public static readonly StringName GetRatio = "get_ratio";
        /// <summary>
        /// Cached name for the 'set_gain' method.
        /// </summary>
        public static readonly StringName SetGain = "set_gain";
        /// <summary>
        /// Cached name for the 'get_gain' method.
        /// </summary>
        public static readonly StringName GetGain = "get_gain";
        /// <summary>
        /// Cached name for the 'set_attack_us' method.
        /// </summary>
        public static readonly StringName SetAttackUs = "set_attack_us";
        /// <summary>
        /// Cached name for the 'get_attack_us' method.
        /// </summary>
        public static readonly StringName GetAttackUs = "get_attack_us";
        /// <summary>
        /// Cached name for the 'set_release_ms' method.
        /// </summary>
        public static readonly StringName SetReleaseMs = "set_release_ms";
        /// <summary>
        /// Cached name for the 'get_release_ms' method.
        /// </summary>
        public static readonly StringName GetReleaseMs = "get_release_ms";
        /// <summary>
        /// Cached name for the 'set_mix' method.
        /// </summary>
        public static readonly StringName SetMix = "set_mix";
        /// <summary>
        /// Cached name for the 'get_mix' method.
        /// </summary>
        public static readonly StringName GetMix = "get_mix";
        /// <summary>
        /// Cached name for the 'set_sidechain' method.
        /// </summary>
        public static readonly StringName SetSidechain = "set_sidechain";
        /// <summary>
        /// Cached name for the 'get_sidechain' method.
        /// </summary>
        public static readonly StringName GetSidechain = "get_sidechain";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : AudioEffect.SignalName
    {
    }
}
