namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>A "chorus" effect creates multiple copies of the original audio (called "voices") with variations in pitch, and layers on top of the original, giving the impression that the sound comes from multiple sources. This creates spectral and spatial movement.</para>
/// <para>Each voice is played a short period of time after the original audio, controlled by <c>delay</c>. An internal low-frequency oscillator (LFO) controls their pitch, and <c>depth</c> controls the LFO's maximum amount.</para>
/// <para>In the real world, this kind of effect is found in pianos, choirs, and instrument ensembles.</para>
/// <para>This effect can also be used to widen mono audio and make digital sounds have a more natural or analog quality.</para>
/// </summary>
public partial class AudioEffectChorus : AudioEffect
{
    /// <summary>
    /// <para>The number of voices in the effect. Value can range from 1 to 4.</para>
    /// </summary>
    public int VoiceCount
    {
        get
        {
            return GetVoiceCount();
        }
        set
        {
            SetVoiceCount(value);
        }
    }

    /// <summary>
    /// <para>The volume ratio of the original audio. Value can range from 0 to 1.</para>
    /// </summary>
    public float Dry
    {
        get
        {
            return GetDry();
        }
        set
        {
            SetDry(value);
        }
    }

    /// <summary>
    /// <para>The volume ratio of all voices. Value can range from 0 to 1.</para>
    /// </summary>
    public float Wet
    {
        get
        {
            return GetWet();
        }
        set
        {
            SetWet(value);
        }
    }

    private static readonly System.Type CachedType = typeof(AudioEffectChorus);

    private static readonly StringName NativeName = "AudioEffectChorus";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public AudioEffectChorus() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal AudioEffectChorus(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal AudioEffectChorus(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVoiceCount, 1286410249ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetVoiceCount(int voices)
    {
        NativeCalls.godot_icall_1_38(MethodBind0, GodotObject.GetPtr(this), voices);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVoiceCount, 3905245786ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public int GetVoiceCount()
    {
        int ret = NativeCalls.godot_icall_0_39(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVoiceDelayMs, 1602489585ul);

    /// <summary>
    /// <para>Sets the delay of a given <paramref name="voiceIdx"/> in milliseconds, compared to the original audio. Value can range from 0 to 50.</para>
    /// </summary>
    public void SetVoiceDelayMs(int voiceIdx, float delayMs)
    {
        NativeCalls.godot_icall_2_93(MethodBind2, GodotObject.GetPtr(this), voiceIdx, delayMs);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVoiceDelayMs, 2339986948ul);

    /// <summary>
    /// <para>Returns the delay of a given <paramref name="voiceIdx"/> in milliseconds, compared to the original audio.</para>
    /// </summary>
    public float GetVoiceDelayMs(int voiceIdx)
    {
        float ret = NativeCalls.godot_icall_1_96(MethodBind3, GodotObject.GetPtr(this), voiceIdx);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVoiceRateHz, 1602489585ul);

    /// <summary>
    /// <para>Sets the rate of a given <paramref name="voiceIdx"/>'s low-frequency oscillator in Hz. Value can range from 0.1 to 20.</para>
    /// </summary>
    public void SetVoiceRateHz(int voiceIdx, float rateHz)
    {
        NativeCalls.godot_icall_2_93(MethodBind4, GodotObject.GetPtr(this), voiceIdx, rateHz);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind5 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVoiceRateHz, 2339986948ul);

    /// <summary>
    /// <para>Returns the rate of a given <paramref name="voiceIdx"/>'s low-frequency oscillator in Hz.</para>
    /// </summary>
    public float GetVoiceRateHz(int voiceIdx)
    {
        float ret = NativeCalls.godot_icall_1_96(MethodBind5, GodotObject.GetPtr(this), voiceIdx);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVoiceDepthMs, 1602489585ul);

    /// <summary>
    /// <para>Sets the depth of a given <paramref name="voiceIdx"/>'s low-frequency oscillator in milliseconds. Value can range from 0 to 20.</para>
    /// </summary>
    public void SetVoiceDepthMs(int voiceIdx, float depthMs)
    {
        NativeCalls.godot_icall_2_93(MethodBind6, GodotObject.GetPtr(this), voiceIdx, depthMs);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVoiceDepthMs, 2339986948ul);

    /// <summary>
    /// <para>Returns the depth of a given <paramref name="voiceIdx"/>'s low-frequency oscillator in milliseconds.</para>
    /// </summary>
    public float GetVoiceDepthMs(int voiceIdx)
    {
        float ret = NativeCalls.godot_icall_1_96(MethodBind7, GodotObject.GetPtr(this), voiceIdx);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind8 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVoiceLevelDb, 1602489585ul);

    /// <summary>
    /// <para>Sets the gain of a given <paramref name="voiceIdx"/> in dB. Value can range from -60 to 24.</para>
    /// </summary>
    public void SetVoiceLevelDb(int voiceIdx, float levelDb)
    {
        NativeCalls.godot_icall_2_93(MethodBind8, GodotObject.GetPtr(this), voiceIdx, levelDb);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind9 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVoiceLevelDb, 2339986948ul);

    /// <summary>
    /// <para>Returns the gain of a given <paramref name="voiceIdx"/> in dB.</para>
    /// </summary>
    public float GetVoiceLevelDb(int voiceIdx)
    {
        float ret = NativeCalls.godot_icall_1_96(MethodBind9, GodotObject.GetPtr(this), voiceIdx);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind10 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVoiceCutoffHz, 1602489585ul);

    /// <summary>
    /// <para>Sets the frequency threshold of a given <paramref name="voiceIdx"/>'s low-pass filter in Hz. Frequencies above <paramref name="cutoffHz"/> are removed from <paramref name="voiceIdx"/>. Value can range from 1 to 20500.</para>
    /// </summary>
    public void SetVoiceCutoffHz(int voiceIdx, float cutoffHz)
    {
        NativeCalls.godot_icall_2_93(MethodBind10, GodotObject.GetPtr(this), voiceIdx, cutoffHz);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind11 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVoiceCutoffHz, 2339986948ul);

    /// <summary>
    /// <para>Returns the frequency threshold of a given <paramref name="voiceIdx"/>'s low-pass filter in Hz. Frequencies above this value are removed from the voice.</para>
    /// </summary>
    public float GetVoiceCutoffHz(int voiceIdx)
    {
        float ret = NativeCalls.godot_icall_1_96(MethodBind11, GodotObject.GetPtr(this), voiceIdx);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind12 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetVoicePan, 1602489585ul);

    /// <summary>
    /// <para>Sets the pan position of a given <paramref name="voiceIdx"/>. Negative values pan the sound to the left, positive pan to the right. Value can range from -1 to 1.</para>
    /// </summary>
    public void SetVoicePan(int voiceIdx, float pan)
    {
        NativeCalls.godot_icall_2_93(MethodBind12, GodotObject.GetPtr(this), voiceIdx, pan);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind13 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetVoicePan, 2339986948ul);

    /// <summary>
    /// <para>Returns the pan position of a given <paramref name="voiceIdx"/>. Negative values mean the left channel, positive mean the right.</para>
    /// </summary>
    public float GetVoicePan(int voiceIdx)
    {
        float ret = NativeCalls.godot_icall_1_96(MethodBind13, GodotObject.GetPtr(this), voiceIdx);
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind14 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetWet, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetWet(float amount)
    {
        NativeCalls.godot_icall_1_91(MethodBind14, GodotObject.GetPtr(this), amount);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind15 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetWet, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetWet()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind15, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind16 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetDry, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetDry(float amount)
    {
        NativeCalls.godot_icall_1_91(MethodBind16, GodotObject.GetPtr(this), amount);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind17 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetDry, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetDry()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind17, GodotObject.GetPtr(this));
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
        /// Cached name for the 'voice_count' property.
        /// </summary>
        public static readonly StringName VoiceCount = "voice_count";
        /// <summary>
        /// Cached name for the 'dry' property.
        /// </summary>
        public static readonly StringName Dry = "dry";
        /// <summary>
        /// Cached name for the 'wet' property.
        /// </summary>
        public static readonly StringName Wet = "wet";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : AudioEffect.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_voice_count' method.
        /// </summary>
        public static readonly StringName SetVoiceCount = "set_voice_count";
        /// <summary>
        /// Cached name for the 'get_voice_count' method.
        /// </summary>
        public static readonly StringName GetVoiceCount = "get_voice_count";
        /// <summary>
        /// Cached name for the 'set_voice_delay_ms' method.
        /// </summary>
        public static readonly StringName SetVoiceDelayMs = "set_voice_delay_ms";
        /// <summary>
        /// Cached name for the 'get_voice_delay_ms' method.
        /// </summary>
        public static readonly StringName GetVoiceDelayMs = "get_voice_delay_ms";
        /// <summary>
        /// Cached name for the 'set_voice_rate_hz' method.
        /// </summary>
        public static readonly StringName SetVoiceRateHz = "set_voice_rate_hz";
        /// <summary>
        /// Cached name for the 'get_voice_rate_hz' method.
        /// </summary>
        public static readonly StringName GetVoiceRateHz = "get_voice_rate_hz";
        /// <summary>
        /// Cached name for the 'set_voice_depth_ms' method.
        /// </summary>
        public static readonly StringName SetVoiceDepthMs = "set_voice_depth_ms";
        /// <summary>
        /// Cached name for the 'get_voice_depth_ms' method.
        /// </summary>
        public static readonly StringName GetVoiceDepthMs = "get_voice_depth_ms";
        /// <summary>
        /// Cached name for the 'set_voice_level_db' method.
        /// </summary>
        public static readonly StringName SetVoiceLevelDb = "set_voice_level_db";
        /// <summary>
        /// Cached name for the 'get_voice_level_db' method.
        /// </summary>
        public static readonly StringName GetVoiceLevelDb = "get_voice_level_db";
        /// <summary>
        /// Cached name for the 'set_voice_cutoff_hz' method.
        /// </summary>
        public static readonly StringName SetVoiceCutoffHz = "set_voice_cutoff_hz";
        /// <summary>
        /// Cached name for the 'get_voice_cutoff_hz' method.
        /// </summary>
        public static readonly StringName GetVoiceCutoffHz = "get_voice_cutoff_hz";
        /// <summary>
        /// Cached name for the 'set_voice_pan' method.
        /// </summary>
        public static readonly StringName SetVoicePan = "set_voice_pan";
        /// <summary>
        /// Cached name for the 'get_voice_pan' method.
        /// </summary>
        public static readonly StringName GetVoicePan = "get_voice_pan";
        /// <summary>
        /// Cached name for the 'set_wet' method.
        /// </summary>
        public static readonly StringName SetWet = "set_wet";
        /// <summary>
        /// Cached name for the 'get_wet' method.
        /// </summary>
        public static readonly StringName GetWet = "get_wet";
        /// <summary>
        /// Cached name for the 'set_dry' method.
        /// </summary>
        public static readonly StringName SetDry = "set_dry";
        /// <summary>
        /// Cached name for the 'get_dry' method.
        /// </summary>
        public static readonly StringName GetDry = "get_dry";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : AudioEffect.SignalName
    {
    }
}
