namespace Godot;

using System;
using System.ComponentModel;
using System.Diagnostics;
using Godot.NativeInterop;

#nullable disable
/// <summary>
/// <para>A "filter" controls the gain of frequencies, using <see cref="Godot.AudioEffectFilter.CutoffHz"/> as a frequency threshold. Filters can help to give room for each sound, and create interesting effects.</para>
/// <para>There are different types of filter that inherit this class:</para>
/// <para>Shelf filters: <see cref="Godot.AudioEffectLowShelfFilter"/> and <see cref="Godot.AudioEffectHighShelfFilter"/></para>
/// <para>Band-pass and notch filters: <see cref="Godot.AudioEffectBandPassFilter"/>, <see cref="Godot.AudioEffectBandLimitFilter"/>, and <see cref="Godot.AudioEffectNotchFilter"/></para>
/// <para>Low/high-pass filters: <see cref="Godot.AudioEffectLowPassFilter"/> and <see cref="Godot.AudioEffectHighPassFilter"/></para>
/// </summary>
public partial class AudioEffectFilter : AudioEffect
{
    public enum FilterDB : long
    {
        /// <summary>
        /// <para>Cutting off at 6 dB per octave. One octave is twice the frequency above <see cref="Godot.AudioEffectFilter.CutoffHz"/>, or half the frequency below <see cref="Godot.AudioEffectFilter.CutoffHz"/>.</para>
        /// </summary>
        Filter6Db = 0,
        /// <summary>
        /// <para>Cutting off at 12 dB per octave. One octave is twice the frequency above <see cref="Godot.AudioEffectFilter.CutoffHz"/>, or half the frequency below <see cref="Godot.AudioEffectFilter.CutoffHz"/>.</para>
        /// </summary>
        Filter12Db = 1,
        /// <summary>
        /// <para>Cutting off at 18 dB per octave. One octave is twice the frequency above <see cref="Godot.AudioEffectFilter.CutoffHz"/>, or half the frequency below <see cref="Godot.AudioEffectFilter.CutoffHz"/>.</para>
        /// </summary>
        Filter18Db = 2,
        /// <summary>
        /// <para>Cutting off at 24 dB per octave. One octave is twice the frequency above <see cref="Godot.AudioEffectFilter.CutoffHz"/>, or half the frequency below <see cref="Godot.AudioEffectFilter.CutoffHz"/>.</para>
        /// </summary>
        Filter24Db = 3
    }

    /// <summary>
    /// <para>Frequency threshold for the filter, in Hz. Value can range from 1 to 20500.</para>
    /// </summary>
    public float CutoffHz
    {
        get
        {
            return GetCutoff();
        }
        set
        {
            SetCutoff(value);
        }
    }

    /// <summary>
    /// <para>Gain at or directly next to the <see cref="Godot.AudioEffectFilter.CutoffHz"/> frequency threshold. Value can range from 0 to 1.</para>
    /// <para>Its exact behavior depends on the selected filter type:</para>
    /// <para>- For shelf filters, it accentuates or masks the order by increasing frequencies right next to the <see cref="Godot.AudioEffectFilter.CutoffHz"/> frequency and decreasing frequencies on the opposite side.</para>
    /// <para>- For the band-pass and notch filters, it widens or narrows the filter at the <see cref="Godot.AudioEffectFilter.CutoffHz"/> frequency threshold.</para>
    /// <para>- For low/high-pass filters, it increases or decreases frequencies at the <see cref="Godot.AudioEffectFilter.CutoffHz"/> frequency threshold.</para>
    /// </summary>
    public float Resonance
    {
        get
        {
            return GetResonance();
        }
        set
        {
            SetResonance(value);
        }
    }

    /// <summary>
    /// <para>Gain of the frequencies affected by the filter. This property is only available for <see cref="Godot.AudioEffectLowShelfFilter"/> and <see cref="Godot.AudioEffectHighShelfFilter"/>. Value can range from 0 to 4.</para>
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
    /// <para>Steepness of the cutoff curve in dB per octave (twice the frequency above <see cref="Godot.AudioEffectFilter.CutoffHz"/>, or half the frequency below <see cref="Godot.AudioEffectFilter.CutoffHz"/>), also known as the "order" of the filter. Higher orders have a more aggressive cutoff.</para>
    /// </summary>
    public AudioEffectFilter.FilterDB Db
    {
        get
        {
            return GetDb();
        }
        set
        {
            SetDb(value);
        }
    }

    private static readonly System.Type CachedType = typeof(AudioEffectFilter);

    private static readonly StringName NativeName = "AudioEffectFilter";

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly unsafe delegate* unmanaged<godot_bool, IntPtr> NativeCtor = ClassDB_get_constructor(NativeName);

    public AudioEffectFilter() : this(true)
    {
        unsafe
        {
            ConstructAndInitialize(NativeCtor, NativeName, CachedType, refCounted: true);
        }
    }

    internal AudioEffectFilter(IntPtr ptr) : this(true)
    {
        NativePtr = ptr;
        unsafe
        {
            ConstructAndInitialize(null, NativeName, CachedType, refCounted: true);
        }
    }

    internal AudioEffectFilter(bool memoryOwn) : base(memoryOwn) { }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind0 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetCutoff, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetCutoff(float freq)
    {
        NativeCalls.godot_icall_1_91(MethodBind0, GodotObject.GetPtr(this), freq);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind1 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetCutoff, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetCutoff()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind1, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind2 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetResonance, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetResonance(float amount)
    {
        NativeCalls.godot_icall_1_91(MethodBind2, GodotObject.GetPtr(this), amount);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind3 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetResonance, 1740695150ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public float GetResonance()
    {
        float ret = NativeCalls.godot_icall_0_92(MethodBind3, GodotObject.GetPtr(this));
        global::System.GC.KeepAlive(this);
        return ret;
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind4 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetGain, 373806689ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetGain(float amount)
    {
        NativeCalls.godot_icall_1_91(MethodBind4, GodotObject.GetPtr(this), amount);
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
    private static readonly IntPtr MethodBind6 = ClassDB_get_method_with_compatibility(NativeName, MethodName.SetDb, 771740901ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public void SetDb(AudioEffectFilter.FilterDB amount)
    {
        NativeCalls.godot_icall_1_38(MethodBind6, GodotObject.GetPtr(this), (int)amount);
        global::System.GC.KeepAlive(this);
    }

    [DebuggerBrowsable(DebuggerBrowsableState.Never)]
    private static readonly IntPtr MethodBind7 = ClassDB_get_method_with_compatibility(NativeName, MethodName.GetDb, 3981721890ul);

    [EditorBrowsable(EditorBrowsableState.Never)]
    public AudioEffectFilter.FilterDB GetDb()
    {
        AudioEffectFilter.FilterDB ret = (AudioEffectFilter.FilterDB)NativeCalls.godot_icall_0_39(MethodBind7, GodotObject.GetPtr(this));
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
        /// Cached name for the 'cutoff_hz' property.
        /// </summary>
        public static readonly StringName CutoffHz = "cutoff_hz";
        /// <summary>
        /// Cached name for the 'resonance' property.
        /// </summary>
        public static readonly StringName Resonance = "resonance";
        /// <summary>
        /// Cached name for the 'gain' property.
        /// </summary>
        public static readonly StringName Gain = "gain";
        /// <summary>
        /// Cached name for the 'db' property.
        /// </summary>
        public static readonly StringName Db = "db";
    }

    /// <summary>
    /// Cached StringNames for the methods contained in this class, for fast lookup.
    /// </summary>
    public new class MethodName : AudioEffect.MethodName
    {
        /// <summary>
        /// Cached name for the 'set_cutoff' method.
        /// </summary>
        public static readonly StringName SetCutoff = "set_cutoff";
        /// <summary>
        /// Cached name for the 'get_cutoff' method.
        /// </summary>
        public static readonly StringName GetCutoff = "get_cutoff";
        /// <summary>
        /// Cached name for the 'set_resonance' method.
        /// </summary>
        public static readonly StringName SetResonance = "set_resonance";
        /// <summary>
        /// Cached name for the 'get_resonance' method.
        /// </summary>
        public static readonly StringName GetResonance = "get_resonance";
        /// <summary>
        /// Cached name for the 'set_gain' method.
        /// </summary>
        public static readonly StringName SetGain = "set_gain";
        /// <summary>
        /// Cached name for the 'get_gain' method.
        /// </summary>
        public static readonly StringName GetGain = "get_gain";
        /// <summary>
        /// Cached name for the 'set_db' method.
        /// </summary>
        public static readonly StringName SetDb = "set_db";
        /// <summary>
        /// Cached name for the 'get_db' method.
        /// </summary>
        public static readonly StringName GetDb = "get_db";
    }

    /// <summary>
    /// Cached StringNames for the signals contained in this class, for fast lookup.
    /// </summary>
    public new class SignalName : AudioEffect.SignalName
    {
    }
}
